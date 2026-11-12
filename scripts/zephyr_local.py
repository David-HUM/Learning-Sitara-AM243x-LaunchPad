"""Build the local Zephyr copy; only the explicit flash action opens UART.

Host-specific absolute paths live in ignored .zephyr.local.json and the ignored
Uniflash cfg, not in reusable source or documentation. TI tools are never edited.
"""
import argparse
import io
import json
import os
from pathlib import Path
import shlex
import struct
import subprocess
import sys
import tempfile

import sitara


ROOT = Path(__file__).resolve().parents[1]
BOARD = 'lp_am243/am2434/r5f0_0'
CFG = Path('tools/sbls-am243x-lp/zephyr_hellw_sbl_ospi.cfg')
SETTINGS = '.zephyr.local.json'


def parameters(root=ROOT):
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
    paths.update(root=root, source=root/'zephyr', build=root/'build/zephyr_hello',
                 cfg=root/CFG, settings=settings, modules=modules)
    paths['app'] = paths['source']/'samples/hello_world'
    paths['boot'] = paths['build']/'boot-image'
    paths['elf'] = paths['build']/'zephyr/zephyr.elf'
    paths['mcelf'] = paths['boot']/'hello_world.mcelf'
    paths['signed'] = paths['boot']/'hello_world.mcelf.hs_fs'
    paths['verification'] = paths['boot']/'verification.json'
    paths['generator'] = paths['ti_sdk']/'tools/boot/multicore-elf/genimage_am64x.py'
    signing = paths['ti_sdk']/'source/security/security_common/tools/boot/signing'
    paths['signer'] = signing/'appimage_x509_cert_gen.py'
    paths['key'] = signing/'app_degenerateKey.pem'
    paths['writer'] = paths['ti_sdk']/'tools/boot/sbl_prebuilt/am243x-lp/sbl_uart_uniflash.release.hs_fs.tiimage'
    paths['tool'] = paths['ti_sdk']/'tools/boot/uart_uniflash.py'
    for name in ('generator', 'signer', 'key', 'writer', 'tool'):
        if not paths[name].is_file():
            raise sitara.Problem(f'Falta el archivo del SDK: {paths[name]}')
    for file in ('CMakeLists.txt', 'prj.conf', 'src/main.c'):
        if not (paths['app']/file).is_file():
            raise sitara.Problem(f'Falta el ejemplo local: {file}')
    return paths


def cfg_content(p):
    return ('# Configuración local generada: sólo aplicación; conserva el SBL OSPI.\n'
            f'--flash-writer={shlex.quote(str(p["writer"]))}\n'
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
    from elftools.elf.elffile import ELFFile

    def loads(elf):
        return [(s['p_vaddr'], s['p_paddr'], s['p_filesz'], s['p_memsz'], s.data())
                for s in elf.iter_segments() if s['p_type'] == 'PT_LOAD']

    original = ELFFile(io.BytesIO(p['elf'].read_bytes()))
    data = p['mcelf'].read_bytes()
    converted = ELFFile(io.BytesIO(data))
    if converted.get_segment(0)['p_type'] != 'PT_NOTE':
        raise sitara.Problem('El primer segmento MCELF debe ser PT_NOTE para este SBL.')
    if original['e_entry'] != 0 or converted['e_entry'] != 0:
        raise sitara.Problem('La entrada esperada para este build es 0x0.')
    if original['e_machine'] != 'EM_ARM' or loads(original) != loads(converted):
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
    if b'Hello World!' not in data:
        raise sitara.Problem('No se encontró el saludo del ejemplo.')


def snapshots(p):
    files = {key: p[key] for key in ('settings', 'elf', 'mcelf', 'signed', 'cfg',
                                   'writer', 'tool', 'generator', 'signer')}
    files.update(main=p['app']/'src/main.c', prj=p['app']/'prj.conf')
    return {name: sitara.digest(path) for name, path in files.items()}


def build(p, *, runner=subprocess.run):
    verify_cache(p, required=False)
    p['boot'].mkdir(parents=True, exist_ok=True)
    sitara.atomic_json(p['verification'], {'status': 'building'})
    env = os.environ.copy()
    for name in ('BOARD', 'CONF_FILE', 'EXTRA_CONF_FILE', 'DTC_OVERLAY_FILE',
                 'ZEPHYR_MODULES', 'EXTRA_ZEPHYR_MODULES', 'ZEPHYR_EXTRA_MODULES'):
        env.pop(name, None)
    env.update(ZEPHYR_BASE=str(p['source']), ZEPHYR_SDK_INSTALL_DIR=str(p['zephyr_sdk']),
               ZEPHYR_TOOLCHAIN_VARIANT='zephyr', PYTHONDONTWRITEBYTECODE='1')
    commands = [
        ['cmake', '-S', str(p['app']), '-B', str(p['build']), '-G', 'Ninja',
         '-DBOARD='+BOARD, '-DZEPHYR_BASE='+str(p['source']),
         '-DZephyr_DIR='+str(p['source']/'share/zephyr-package/cmake'),
         '-DZEPHYR_SDK_INSTALL_DIR='+str(p['zephyr_sdk']), '-DZEPHYR_TOOLCHAIN_VARIANT=zephyr',
         '-DPython3_EXECUTABLE='+str(p['python']), '-DZEPHYR_MODULES='+';'.join(p['modules']),
         '-DCONF_FILE='+str(p['app']/'prj.conf'), '-DEXTRA_CONF_FILE=', '-DDTC_OVERLAY_FILE='],
        ['cmake', '--build', str(p['build'])],
        [str(p['python']), str(p['generator']), '--core-img=4:'+str(p['elf']),
         '--output='+str(p['mcelf'])],
        [str(p['python']), str(p['signer']), '--bin', str(p['mcelf']), '--authtype', '1',
         '--key', str(p['key']), '--output', str(p['signed'])],
    ]
    print('Fuente local:', p['source'], '\nBuild fijo:', p['build'], flush=True)
    for command in commands:
        runner(command, cwd=p['boot'], env=env, check=True)
    verify_cache(p)
    image_integrity(p)
    write_cfg(p)
    sitara.atomic_json(p['verification'], {'status': 'ready', 'board': BOARD,
                       'hashes': snapshots(p), 'hardware_validation': 'not performed'})
    print('Compilado, empaquetado y firmado:', p['signed'])
    print('CFG actualizado:', p['cfg'])
    print('No se abrió UART ni se grabó la placa.')


def check(p):
    receipt = json.loads(p['verification'].read_text())
    if receipt.get('status') != 'ready':
        raise sitara.Problem('Build incompleto: ejecuta just build-zephyr.')
    verify_cache(p)
    if p['cfg'].is_symlink() or p['cfg'].read_text() != cfg_content(p):
        raise sitara.Problem('El cfg cambió o no es el de esta copia. Ejecuta just build-zephyr.')
    if receipt.get('hashes') != snapshots(p):
        raise sitara.Problem('Cambiaron archivos desde el build: ejecuta just build-zephyr.')
    image_integrity(p)
    sitara.dependencies('ospi')
    print('Verificado: fuente local, segmentos, core 4, entrada 0, payload y hashes.')
    print('Aplicación:', p['signed'])
    print('Uniflash:', p['tool'], '\nCFG:', p['cfg'])
    print('Sólo flash y flashverify en 0x80000. No se regraba el SBL ni se usa XIP.')
    print('No se abrió ningún puerto; no es una prueba de arranque ni autenticación en placa.')
    return receipt


def flash(p, port='', *, selector=None, vendor=None):
    receipt = p['build']/'receipt.json'
    if receipt.exists() and json.loads(receipt.read_text()).get('status') != 'completed':
        raise sitara.Problem('Intento anterior incierto: revisa operation.log y la placa antes de repetir.')
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
    parser.add_argument('action', choices=('build', 'check', 'flash'))
    parser.add_argument('--port', default='')
    args = parser.parse_args(argv)
    if args.port and args.action != 'flash':
        parser.error('--port sólo se admite con flash')
    try:
        p = parameters()
        if args.action == 'check':
            check(p)
        else:
            with sitara.operation_lock(ROOT):
                if args.action == 'build':
                    build(p)
                else:
                    flash(p, args.port)
    except (sitara.Problem, OSError, ValueError, subprocess.CalledProcessError) as error:
        print('ERROR:', error, file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
