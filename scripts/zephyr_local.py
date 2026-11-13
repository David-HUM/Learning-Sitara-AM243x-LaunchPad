"""Build the local Zephyr copy; only the explicit flash action opens UART.

Host-specific absolute paths live in ignored .zephyr.local.json and the ignored
Uniflash cfg, not in reusable source or documentation. TI tools are never edited.
"""
import argparse
import configparser
import io
import json
import os
from pathlib import Path
import shlex
import shutil
import struct
import subprocess
import sys
import tempfile

import sitara
import hola_sbl


ROOT = Path(__file__).resolve().parents[1]
BOARD = 'lp_am243/am2434/r5f0_0'
CFG = Path('tools/sbls-am243x-lp/zephyr_hellw_sbl_ospi.cfg')
SETTINGS = '.zephyr.local.json'
APPS = {
    'hello_world': {
        'directory': 'apps/hello_world',
        'cfg': Path('apps/hello_world/build/flash.cfg'),
        'message': b'Hello World!', 'recipe': 'zephyr',
        'copy_writer': False,
    },
    'hola_zephyr': {
        'directory': 'apps/hola_zephyr',
        'cfg': Path('apps/hola_zephyr/build/flash.cfg'),
        'message': b'hola soy zephyr\n', 'recipe': 'hola', 'copy_writer': True,
        'overlay': 'app.overlay',
        'mpu_compat': 'mpu_dt_compat.h',
        'extra_inputs': ('Kconfig', 'src/early_uart_trace.S', 'src/boot_trace.c',
                         'early_uart_trace.ld'),
        'zephyr_inputs': ('kernel/init.c', 'arch/arm/core/cortex_a_r/prep_c.c',
                          'drivers/interrupt_controller/intc_vim.c',
                          'arch/arm/core/cortex_a_r/irq_init.c',
                          'soc/ti/k3/common/cortex_r/soc.c',
                          'arch/arm/core/cortex_a_r/reset.S',
                          'drivers/pinctrl/pinctrl_ti_k3.c'),
    },
}


def parameters(root=ROOT, app='hello_world'):
    if app not in APPS:
        raise sitara.Problem('Aplicación no admitida. Usa hello_world o hola_zephyr.')
    profile = APPS[app]
    root = root.resolve()
    settings = root/SETTINGS
    if settings.is_symlink():
        raise sitara.Problem('La configuración local no puede ser un enlace.')
    values = json.loads(settings.read_text())
    if set(values) != {'python', 'zephyr_sdk', 'ti_sdk', 'modules'}:
        raise sitara.Problem('Revisa los campos de .zephyr.local.json.')
    paths = {}
    for key in ('python', 'zephyr_sdk', 'ti_sdk'):
        path = Path(values[key])
        if not path.is_absolute():
            raise sitara.Problem(f'{key} debe contener una ruta absoluta local.')
        # Keep the venv executable path: resolving its symlink loses the venv.
        if not path.exists():
            raise sitara.Problem(f'No existe {key}: {path}')
        paths[key] = path
    modules = values['modules']
    if not isinstance(modules, list) or not modules:
        raise sitara.Problem('Declara explícitamente los módulos locales.')
    for module in modules:
        if not Path(module).is_absolute() or not Path(module).is_dir():
            raise sitara.Problem(f'Módulo no disponible: {module}')
    paths.update(root=root, source=root/'zephyr', build=root/profile['directory']/'build',
                 cfg=root/profile['cfg'], settings=settings, modules=modules,
                 app_name=app, recipe=profile['recipe'], message=profile['message'],
                 copy_writer=profile['copy_writer'])
    paths['app'] = root/profile['directory']
    paths['overlay'] = paths['app']/profile['overlay'] if profile.get('overlay') else None
    if paths['overlay'] is not None and not paths['overlay'].is_file():
        raise sitara.Problem(f'Falta el overlay de la aplicación {app}.')
    paths['mpu_compat'] = paths['app']/profile['mpu_compat'] if profile.get('mpu_compat') else None
    if paths['mpu_compat'] is not None and not paths['mpu_compat'].is_file():
        raise sitara.Problem(f'Falta la cabecera de compatibilidad MPU de {app}.')
    paths['extra_inputs'] = {f'app:{name}': paths['app']/name
                             for name in profile.get('extra_inputs', ())}
    paths['zephyr_inputs'] = {f'zephyr:{name}': paths['source']/name
                              for name in profile.get('zephyr_inputs', ())}
    for path in paths['extra_inputs'].values():
        if not path.is_file():
            raise sitara.Problem(f'Falta un archivo de la aplicación: {path.name}')
    for path in paths['zephyr_inputs'].values():
        if not path.is_file():
            raise sitara.Problem(f'Falta un archivo Zephyr requerido: {path}')
    paths['boot'] = paths['build']/'boot-image'
    paths['elf'] = paths['build']/'zephyr/zephyr.elf'
    paths['mcelf'] = paths['boot']/f'{app}.mcelf'
    paths['signed'] = paths['boot']/f'{app}.mcelf.hs_fs'
    paths['verification'] = paths['boot']/'verification.json'
    paths['compiled'] = paths['boot']/'compiled.json'
    paths['generator'] = paths['ti_sdk']/'tools/boot/multicore-elf/genimage_am64x.py'
    signing = paths['ti_sdk']/'source/security/security_common/tools/boot/signing'
    paths['signer'] = signing/'appimage_x509_cert_gen.py'
    paths['key'] = signing/'app_degenerateKey.pem'
    paths['writer'] = paths['ti_sdk']/'tools/boot/sbl_prebuilt/am243x-lp/sbl_uart_uniflash.release.hs_fs.tiimage'
    paths['tool'] = paths['ti_sdk']/'tools/boot/uart_uniflash.py'
    if paths['copy_writer']:
        # Use the locally built flash writer and original SDK tool from the
        # guide's successful MCU+ SDK checkout. Packaging remains on the
        # configured 12.01 SDK, just like the existing Hello World pipeline.
        flash_sdk = root/'mcu_plus_sdk'
        paths['writer_source'] = flash_sdk/'tools/boot/sbl_prebuilt/am243x-lp/sbl_uart_uniflash.release.hs_fs.tiimage'
        paths['writer'] = paths['build']/paths['writer_source'].name
        paths['tool'] = flash_sdk/'tools/boot/uart_uniflash.py'
    for name in ('generator', 'signer', 'key', 'writer', 'tool'):
        if name == 'writer' and paths['copy_writer']:
            name = 'writer_source'
        if not paths[name].is_file():
            raise sitara.Problem(f'Falta el archivo del SDK: {paths[name]}')
    for file in ('CMakeLists.txt', 'prj.conf', 'src/main.c'):
        if not (paths['app']/file).is_file():
            raise sitara.Problem(f'Falta un archivo de la aplicación {app}: {file}')
    return paths


def cfg_content(p):
    # The independent app follows the guide literally: the flash writer is
    # copied next to its cfg; run Uniflash with the build as working directory.
    writer = p['writer'].name if p['copy_writer'] else str(p['writer'])
    return ('# Configuración local generada: sólo aplicación; conserva el SBL OSPI.\n'
            f'--flash-writer={shlex.quote(writer)}\n'
            f'--file={shlex.quote(str(p["signed"]))} --operation=flash --flash-offset=0x80000\n'
            f'--file={shlex.quote(str(p["signed"]))} --operation=flashverify --flash-offset=0x80000\n')


def write_cfg(p):
    if p['cfg'].is_symlink():
        raise sitara.Problem('El cfg local no puede ser un enlace.')
    content = cfg_content(p)
    if p['cfg'].exists() and p['cfg'].read_text() == content:
        return
    p['cfg'].parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.zephyr-cfg-', dir=p['cfg'].parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            stream.write(content)
        os.replace(temporary, p['cfg'])
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def copy_writer(p):
    if not p['copy_writer']:
        return
    if p['writer'].is_symlink():
        raise sitara.Problem('La copia del flash writer no puede ser un enlace.')
    if (p['writer'].exists()
            and sitara.digest(p['writer']) == sitara.digest(p['writer_source'])):
        return
    shutil.copy2(p['writer_source'], p['writer'])
    print('Flash writer copiado al directorio de trabajo:', p['writer'])


def cache_values(p):
    file = p['build']/'CMakeCache.txt'
    if not file.exists():
        return {}
    return {line.split(':', 1)[0]: line.split('=', 1)[1]
            for line in file.read_text().splitlines()
            if ':' in line and '=' in line and not line.startswith(('#', '//'))}


def verify_cache(p, *, required=True):
    values = cache_values(p)
    if not values and not required:
        return
    expected = {'ZEPHYR_BASE': str(p['source']), 'APPLICATION_SOURCE_DIR': str(p['app']),
                'CMAKE_HOME_DIRECTORY': str(p['app']), 'BOARD': BOARD,
                'ZEPHYR_SDK_INSTALL_DIR': str(p['zephyr_sdk'])}
    for key, value in expected.items():
        if not required and key not in values:
            continue  # An interrupted configure can be resumed, not erased.
        if values.get(key) != value:
            raise sitara.Problem(f'Caché ajeno o incompleto: {key}. No se borra ni reutiliza.')


def image_integrity(p):
    from elftools.common.exceptions import ELFError
    from elftools.elf.elffile import ELFFile

    def loads(elf):
        return [(s['p_vaddr'], s['p_paddr'], s['p_filesz'], s['p_memsz'], s.data())
                for s in elf.iter_segments() if s['p_type'] == 'PT_LOAD']

    data = p['mcelf'].read_bytes()
    readable = data
    # MCU+ SDK 12.01 modules_am64/elf.py removes the section table, setting
    # e_shoff/e_shnum to zero but retaining e_shstrndx from the input ELF.
    # pyelftools then reads unrelated payload bytes as a string-table header.
    # Normalize ONLY that absent-table index in a parser-only memory copy.
    # The generated/signed image and all compared PT_LOAD bytes stay intact.
    if (len(data) >= 52 and data[:7] == b'\x7fELF\x01\x01\x01'
            and struct.unpack_from('<I', data, 32)[0] == 0
            and struct.unpack_from('<H', data, 48)[0] == 0):
        readable = bytearray(data)
        struct.pack_into('<H', readable, 50, 0)
    try:
        original = ELFFile(io.BytesIO(p['elf'].read_bytes()))
        converted = ELFFile(io.BytesIO(readable))
    except ELFError as error:
        raise sitara.Problem(f'ELF/MCELF no válido: {error}') from error
    if not converted.num_segments() or converted.get_segment(0)['p_type'] != 'PT_NOTE':
        raise sitara.Problem('El primer segmento MCELF debe ser PT_NOTE para este SBL.')
    if original['e_entry'] != 0 or converted['e_entry'] != 0:
        raise sitara.Problem('La entrada esperada para este build es 0x0.')
    if (original['e_machine'] != 'EM_ARM' or converted['e_machine'] != 'EM_ARM'
            or loads(original) != loads(converted)):
        raise sitara.Problem('Los segmentos ELF no se conservaron en MCELF.')
    notes = {}
    for segment in converted.iter_segments():
        if segment['p_type'] != 'PT_NOTE':
            continue
        raw, offset = segment.data(), 0
        while offset + 12 <= len(raw):
            namesz, descsz, typ = struct.unpack_from('<III', raw, offset)
            offset += 12 + ((namesz + 3) & ~3)
            if offset + descsz > len(raw):
                raise sitara.Problem('Nota MCELF truncada.')
            notes[typ] = raw[offset:offset+descsz]
            offset += (descsz + 3) & ~3
    if (notes.get(0xbbbb7777) != bytes([4])*len(loads(converted))
            or notes.get(0xcccc9999) != struct.pack('<II', 4, 0)):
        raise sitara.Problem('MCELF no corresponde al core 4 con entrada cero.')
    signed = p['signed'].read_bytes()
    if len(signed) < 4 or signed[0] != 0x30:
        raise sitara.Problem('Falta el certificado DER de la imagen firmada.')
    length = signed[1]
    if length & 0x80:
        count = length & 0x7f
        if count == 0 or count > 4 or len(signed) < 2 + count:
            raise sitara.Problem('Longitud DER no válida.')
        cert_size = 2 + count + int.from_bytes(signed[2:2+count], 'big')
    else:
        cert_size = 2 + length
    if signed[cert_size:] != data:
        raise sitara.Problem('El payload firmado no coincide con el MCELF.')
    if not 0 < len(signed) <= 0x80000:
        raise sitara.Problem('La aplicación supera la ranura de 0x80000 bytes.')
    if p['message'] not in data:
        raise sitara.Problem(f'No se encontró el mensaje de {p["app_name"]} en la imagen.')


def snapshots(p):
    files = {key: p[key] for key in ('settings', 'elf', 'mcelf', 'signed', 'cfg',
                                   'writer', 'tool', 'generator', 'signer')}
    files.update(main=p['app']/'src/main.c', prj=p['app']/'prj.conf')
    if p['copy_writer']:
        files.update(cmake=p['app']/'CMakeLists.txt', writer_source=p['writer_source'])
    if p['overlay'] is not None:
        files['overlay'] = p['overlay']
    if p['mpu_compat'] is not None:
        files['mpu_compat'] = p['mpu_compat']
    files.update(p['extra_inputs'])
    files.update(p['zephyr_inputs'])
    files.update({f'source:{name}': path for name, path in source_files(p).items()})
    if p['app_name'] == 'hola_zephyr':
        files.update({'sbl:'+name: path for name, path in hola_sbl.artifacts(p).items()})
        files['sbl:receipt'] = hola_sbl.paths(p)['receipt']
        files.update({'sbl-input:'+name: path for name, path in hola_sbl.source_files(p).items()})
    return {name: sitara.digest(path) for name, path in files.items()}


def source_files(p):
    """Include every app build input, without hashing generated build trees."""
    files = {'settings': p['settings']}
    manifest = p['root']/'apps/west.yml'
    if manifest.is_file():
        files['manifest'] = manifest
    for path in p['app'].rglob('*'):
        relative = path.relative_to(p['app'])
        if any(part in ('build', 'build-debug', '.git', '__pycache__') for part in relative.parts):
            continue
        if path.is_file() and (path.suffix in ('.c', '.h', '.S', '.ld', '.overlay', '.conf')
                               or path.name in ('CMakeLists.txt', 'Kconfig')):
            files[relative.as_posix()] = path
    files.update(p['zephyr_inputs'])
    return files


def source_hashes(p):
    return {name: sitara.digest(path) for name, path in source_files(p).items()}


def compile_app(p, *, runner=subprocess.run):
    """west owns compilation; no package tools, downloads or UART here."""
    verify_cache(p, required=False)
    p['boot'].mkdir(parents=True, exist_ok=True)
    sitara.atomic_json(p['verification'], {'status': 'building'})
    inputs = source_hashes(p)
    env = os.environ.copy()
    for name in ('BOARD', 'CONF_FILE', 'EXTRA_CONF_FILE', 'DTC_OVERLAY_FILE',
                 'ZEPHYR_MODULES', 'EXTRA_ZEPHYR_MODULES', 'ZEPHYR_EXTRA_MODULES'):
        env.pop(name, None)
    env.update(ZEPHYR_BASE=str(p['source']), ZEPHYR_SDK_INSTALL_DIR=str(p['zephyr_sdk']),
               ZEPHYR_TOOLCHAIN_VARIANT='zephyr', PYTHONDONTWRITEBYTECODE='1')
    command = [str(p['python']), '-m', 'west', 'build',
         '-b', BOARD, '-d', str(p['build']), '--pristine=never', str(p['app']), '--',
         '-GNinja', '-DZEPHYR_BASE='+str(p['source']),
         '-DZephyr_DIR='+str(p['source']/'share/zephyr-package/cmake'),
         '-DZEPHYR_SDK_INSTALL_DIR='+str(p['zephyr_sdk']), '-DZEPHYR_TOOLCHAIN_VARIANT=zephyr',
         '-DPython3_EXECUTABLE='+str(p['python']), '-DZEPHYR_MODULES='+';'.join(p['modules']),
         '-DCONF_FILE='+str(p['app']/'prj.conf'), '-DEXTRA_CONF_FILE=',
         '-DDTC_OVERLAY_FILE='+(str(p['overlay']) if p['overlay'] is not None else '')]
    print('west build:', p['app'], '\nDirectorio:', p['build'], flush=True)
    runner(command, cwd=p['root'], env=env, check=True)
    verify_cache(p)
    if not p['elf'].is_file():
        raise sitara.Problem('west terminó sin generar el ELF de la aplicación.')
    if source_hashes(p) != inputs:
        raise sitara.Problem('Las fuentes cambiaron durante el build. Repite just build.')
    sitara.atomic_json(p['compiled'], {'status': 'compiled', 'app': p['app_name'],
                       'inputs': inputs, 'elf': sitara.digest(p['elf'])})
    print('ELF compilado. Ejecuta just package desde la app; no se abrió UART.')


def package_app(p, *, runner=subprocess.run):
    """Only package an ELF verified against its compiled inputs."""
    verify_cache(p)
    compiled = json.loads(p['compiled'].read_text())
    inputs = source_hashes(p)
    if (compiled.get('status') != 'compiled' or compiled.get('app') != p['app_name']
            or compiled.get('inputs') != inputs
            or compiled.get('elf') != sitara.digest(p['elf'])):
        raise sitara.Problem('El ELF o sus fuentes cambiaron. Ejecuta just build antes de package.')
    if p['app_name'] == 'hola_zephyr':
        hola_sbl.check_pair(p)
    sitara.atomic_json(p['verification'], {'status': 'packaging'})
    commands = [
        [str(p['python']), str(p['generator']), '--core-img=4:'+str(p['elf']),
         '--output='+str(p['mcelf'])],
        [str(p['python']), str(p['signer']), '--bin', str(p['mcelf']), '--authtype', '1',
         '--key', str(p['key']), '--output', str(p['signed'])],
    ]
    for command in commands:
        runner(command, cwd=p['boot'], check=True)
    if source_hashes(p) != inputs or compiled['elf'] != sitara.digest(p['elf']):
        raise sitara.Problem('Las fuentes o el ELF cambiaron durante el empaquetado.')
    verify_cache(p)
    image_integrity(p)
    copy_writer(p)
    write_cfg(p)
    sitara.atomic_json(p['verification'], {'status': 'ready', 'board': BOARD, 'app': p['app_name'],
                       'hashes': snapshots(p), 'hardware_validation': 'not performed'})
    print('Compilado, empaquetado y firmado:', p['signed'])
    print('CFG actualizado:', p['cfg'])
    print('No se abrió UART ni se grabó la placa.')


def build(p, *, runner=subprocess.run):
    """Compatibility pipeline used by the existing root build aliases."""
    compile_app(p, runner=runner)
    package_app(p, runner=runner)


def workspace(p, *, runner=subprocess.run):
    """Inspect only: never init/update, overwrite .west or reset dependencies."""
    config = configparser.ConfigParser()
    config.read(p['root']/'.west/config')
    if (config.get('manifest', 'path', fallback='') != 'apps'
            or config.get('manifest', 'file', fallback='west.yml') != 'west.yml'):
        raise sitara.Problem('El workspace no usa apps/west.yml. No se modifica automáticamente.')
    manifest = p['root']/'apps/west.yml'
    if not manifest.is_file():
        raise sitara.Problem('Falta apps/west.yml.')
    runner([str(p['python']), '-m', 'west', 'list',
            '-f', '{name}: {path} @ {revision}'], cwd=p['root'], check=True)
    print('Inspección del manifiesto. No se descargó ni actualizó ninguna dependencia.')


def serial_console(p, port, *, runner=subprocess.run):
    if not port:
        raise sitara.Problem('Indica --port; serial abre el dispositivo sólo de forma explícita.')
    if port not in {item['device'] for item in sitara.enumerate_ports() if item['eligible']}:
        raise sitara.Problem('El puerto solicitado no aparece entre los dispositivos serie actuales.')
    print('Abriendo consola serie 115200 8N1. No se graba flash.', flush=True)
    runner([str(p['python']), '-m', 'serial.tools.miniterm',
            '--dtr', '0', '--rts', '0', port, '115200'], check=True)


def check(p):
    receipt = json.loads(p['verification'].read_text())
    if receipt.get('app', 'hello_world') != p['app_name']:
        raise sitara.Problem('El recibo pertenece a otra aplicación.')
    rebuild = f'just build-{p["recipe"]}'
    if receipt.get('status') != 'ready':
        raise sitara.Problem(f'Build incompleto: ejecuta {rebuild}.')
    verify_cache(p)
    if p['app_name'] == 'hola_zephyr':
        hola_sbl.check_pair(p)
    if p['cfg'].is_symlink() or p['cfg'].read_text() != cfg_content(p):
        raise sitara.Problem(f'El cfg cambió o no es el de esta aplicación. Ejecuta {rebuild}.')
    if p['copy_writer'] and (p['writer'].is_symlink()
            or sitara.digest(p['writer']) != sitara.digest(p['writer_source'])):
        raise sitara.Problem(f'La copia del flash writer cambió: ejecuta {rebuild}.')
    if receipt.get('hashes') != snapshots(p):
        raise sitara.Problem(f'Cambiaron archivos desde el build: ejecuta {rebuild}.')
    image_integrity(p)
    sitara.dependencies('ospi')
    print('Verificado: fuente local, segmentos, core 4, entrada 0, payload y hashes.')
    print('Aplicación:', p['signed'])
    if p['copy_writer']:
        print('Flash writer local copiado y verificado:', p['writer'])
    if p['app_name'] == 'hola_zephyr':
        print('Par local SBL/Zephyr sin solapamiento; MPU habilitada.')
        print('SBL corregido:', hola_sbl.paths(p)['image'])
        print('No se comprobó si ese SBL está instalado en la placa.')
    print('Uniflash:', p['tool'], '\nCFG:', p['cfg'])
    print('Sólo flash y flashverify en 0x80000. No se regraba el SBL ni se usa XIP.')
    print('No se abrió ningún puerto; no es una prueba de arranque ni autenticación en placa.')
    return receipt


def flash(p, port='', *, selector=None, vendor=None):
    before = check(p)
    print('ESCRITURA DE FLASH: aplicación en 0x80000. Requiere SBL OSPI existente.', flush=True)
    print('Selecciona UART BOOT, reinicia y cierra la terminal serie. Se abrirá UART.', flush=True)
    selected = (selector or sitara.select_port)(port)
    if check(p) != before:
        raise sitara.Problem('La preparación cambió durante la selección del puerto.')
    command = [sys.executable, str(p['tool']), '-p', selected, '--cfg='+str(p['cfg'])]
    (vendor or sitara.run_vendor)(command, p['build'])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('build', 'package', 'pipeline', 'check', 'flash',
                                           'serial', 'workspace', 'apps', 'build-sbl', 'check-boot'))
    parser.add_argument('--app', choices=tuple(APPS), default='hello_world')
    parser.add_argument('--port', default='')
    args = parser.parse_args(argv)
    if args.port and args.action not in ('flash', 'serial'):
        parser.error('--port sólo se admite con flash o serial')
    try:
        if args.action == 'apps':
            for name, profile in APPS.items():
                print(name, '->', profile['directory'])
            return 0
        p = parameters(app=args.app)
        if args.action == 'check':
            check(p)
        elif args.action == 'workspace':
            workspace(p)
        elif args.action == 'check-boot':
            result = hola_sbl.check_pair(p)
            hola_sbl.describe(result)
            print('Par local correcto. No se ha leído ni verificado el SBL instalado.')
        else:
            with sitara.operation_lock(ROOT):
                if args.action == 'build':
                    compile_app(p)
                elif args.action == 'build-sbl':
                    hola_sbl.build(p)
                elif args.action == 'package':
                    package_app(p)
                elif args.action == 'pipeline':
                    build(p)
                elif args.action == 'serial':
                    serial_console(p, args.port)
                else:
                    flash(p, args.port)
    except (sitara.Problem, OSError, ValueError, subprocess.CalledProcessError) as error:
        print('ERROR:', error, file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
