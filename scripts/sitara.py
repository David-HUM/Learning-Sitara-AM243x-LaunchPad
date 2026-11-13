"""LP-AM243 launch adapter. SDK sources are read, never edited or imported.

Only flash/boot open hardware. config/check/plan work with files; ports only
enumerates metadata. Local paths, generated aliases and builds stay gitignored.
"""
import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from uuid import UUID, uuid4


ROOT = Path(__file__).resolve().parents[1]
SETTINGS = '.sitara.local.json'
FIELDS = ('SDK_INSTALL_PATH', 'APP_IMAGE', 'APP_XIP', 'UART_PORT', 'PARTITION_IMAGES')
MODES = {
    'ospi': 'Flash QSPI/OSPI por UART: SBL OSPI + aplicación.',
    'uart': 'Carga temporal en RAM por UART; no escribe la flash.',
    'null': 'Graba sólo SBL NULL por UART para inicialización y depuración posterior.',
    'dfu': 'Flash QSPI/OSPI por USB DFU; no utiliza un puerto ACM.',
    'ospi-multipartition': 'Flash por UART con particiones e imágenes declaradas explícitamente.',
}
SLOTS = {0x80000, 0x100000, 0x180000, 0x200000, 0x280000}
SERIAL_DEPS = ('serial', 'xmodem', 'tqdm')


class Problem(ValueError):
    pass


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def atomic_json(path, value):
    if path.is_symlink():
        raise Problem('La configuración local no puede ser un enlace simbólico.')
    fd, temporary = tempfile.mkstemp(prefix='.sitara-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def cache(root):
    path = root/'.sitara'
    if path.is_symlink():
        raise Problem('.sitara no puede apuntar fuera del proyecto mediante un enlace.')
    path.mkdir(mode=0o700, exist_ok=True)
    return path


@contextmanager
def operation_lock(root):
    lock = cache(root)/'operation.lock'
    fd = os.open(lock, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise Problem('Ya hay otra operación de este adaptador en el proyecto.') from None
        yield
    finally:
        os.close(fd)


def settings(root, environment=None):
    env = os.environ if environment is None else environment
    path = root/SETTINGS
    if path.is_symlink():
        raise Problem('No se sigue un enlace para la configuración local.')
    value = json.loads(path.read_text()) if path.exists() else {}
    if not isinstance(value, dict):
        raise Problem('La configuración local debe ser un objeto JSON.')
    if set(value)-set(FIELDS)-{'profile', 'workspace'}:
        raise Problem('Hay campos desconocidos en la configuración local; no se descartan ni sobrescriben automáticamente.')
    for field in FIELDS:
        if field in env:
            value[field] = json.loads(env[field]) if field == 'PARTITION_IMAGES' else env[field]
    return value


def file_path(value, label, root):
    if not isinstance(value, str) or not value or '<' in value:
        raise Problem(f'Completa {label} en {SETTINGS} o mediante export.')
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = root/path
    path = path.resolve(strict=True)
    if not path.is_file() or not path.stat().st_size:
        raise Problem(f'{label} debe apuntar a un archivo existente y no vacío.')
    return path


def sdk_path(value, root):
    if value:
        path = Path(value).expanduser()
        path = (path if path.is_absolute() else root/path).resolve()
    else:
        matches = [p for p in (Path.home()/'ti').glob('mcu_plus_sdk_am243x_*')
                   if (p/'tools/boot/sbl_prebuilt/am243x-lp').is_dir()]
        if len(matches) != 1:
            raise Problem('Indica SDK_INSTALL_PATH; no se elegirá un SDK entre varios.')
        path = matches[0].resolve()
    if not (path/'tools/boot/sbl_prebuilt/am243x-lp').is_dir():
        raise Problem('SDK sin directorio de bootloaders para am243x-lp.')
    return path


def configuration(mode, values, root):
    """Build a portable plan without writing files or calling any SDK code."""
    if mode == 'qspi':
        mode = 'ospi'
    if mode not in MODES:
        raise Problem('Modo desconocido. Consulta just modes.')
    sdk = sdk_path(values.get('SDK_INSTALL_PATH'), root)
    boot = sdk/'tools/boot'
    prebuilt = boot/'sbl_prebuilt/am243x-lp'
    images = {}

    def add(alias, value, label):
        images[alias] = file_path(str(value) if value else '', label, root)
        return alias

    def application(alias, value):
        name = add(alias, value, 'APP_IMAGE o PARTITION_IMAGES')
        if not str(images[name]).endswith('.mcelf.hs_fs'):
            raise Problem('Esta configuración requiere una aplicación .mcelf.hs_fs del mismo SDK.')
        return name

    script = 'uart_bootloader.py' if mode == 'uart' else ('usb_dfu_uniflash.py' if mode == 'dfu' else 'uart_uniflash.py')
    tool = file_path(str(boot/script), 'Herramienta TI', root)
    source = tool.read_text()
    if mode == 'uart' and not all(token in source for token in ('am64x_am243x', 'xmodem_send_segments', '--soc')):
        raise Problem('Este SDK no muestra el protocolo MCELF UART requerido; no se asume compatibilidad.')
    if mode != 'uart' and '--cfg' not in source:
        raise Problem('Interfaz --cfg no reconocida en la herramienta TI.')
    if mode == 'uart':
        if values.get('APP_XIP'):
            raise Problem('El perfil UART directo no acepta APP_XIP en este adaptador.')
        add('sbl-uart.tiimage', prebuilt/'sbl_uart.release.hs_fs.tiimage', 'SBL UART')
        application('application.mcelf.hs_fs', values.get('APP_IMAGE'))
        lines = ['--soc=am64x_am243x', '--bootloader=sbl-uart.tiimage',
                 '--file=application.mcelf.hs_fs']
    else:
        writer = 'sbl_dfu_uniflash' if mode == 'dfu' else 'sbl_uart_uniflash'
        add('flash-writer.tiimage', prebuilt/(writer+'.release.hs_fs.tiimage'), 'Flash writer')
        sbl = 'sbl_null' if mode == 'null' else ('sbl_ospi_multi_partition' if mode == 'ospi-multipartition' else 'sbl_ospi')
        add('bootloader.tiimage', prebuilt/(sbl+'.release.hs_fs.tiimage'), 'SBL')
        if images['bootloader.tiimage'].stat().st_size > 0x80000:
            raise Problem('El SBL supera el espacio reservado antes de la aplicación.')
        lines = ['--flash-writer=flash-writer.tiimage']
        if mode in ('ospi', 'dfu'):
            lines.append('--operation=flash-phy-tuning-data')
        lines.append('--file=bootloader.tiimage --operation=flash --flash-offset=0x0')
        if mode == 'ospi-multipartition':
            partitions = values.get('PARTITION_IMAGES', [])
            if not isinstance(partitions, list) or not partitions:
                raise Problem('Declara PARTITION_IMAGES; no se copia APP_IMAGE a todas las particiones.')
            used, used_images = set(), set()
            for i, part in enumerate(partitions):
                if not isinstance(part, dict) or set(part) != {'image', 'offset'}:
                    raise Problem('Cada partición requiere image y offset.')
                offset = int(str(part['offset']), 0)
                if offset not in SLOTS or offset in used:
                    raise Problem('Offset repetido o fuera de las cinco particiones de la plantilla TI.')
                alias = application(f'partition-{i}.mcelf.hs_fs', part['image'])
                image = images[alias]
                if image in used_images or image.stat().st_size > 0x80000:
                    raise Problem('Imagen repetida o mayor que el espacio de su partición.')
                used.add(offset)
                used_images.add(image)
                lines.append(f'--file={alias} --operation=flash --flash-offset={offset:#x}')
            if values.get('APP_XIP'):
                raise Problem('APP_XIP no está implementado para multipartición.')
        elif mode != 'null':
            application('application.mcelf.hs_fs', values.get('APP_IMAGE'))
            lines.append('--file=application.mcelf.hs_fs --operation=flash --flash-offset=0x80000')
            if values.get('APP_XIP'):
                if 'flash-mcelf-xip' not in source:
                    raise Problem('La herramienta TI no reconoce flash-mcelf-xip.')
                add('application.mcelf_xip', values['APP_XIP'], 'APP_XIP')
                if not str(images['application.mcelf_xip']).endswith('.mcelf_xip'):
                    raise Problem('APP_XIP debe ser la imagen .mcelf_xip del mismo proyecto.')
                lines.append('--file=application.mcelf_xip --operation=flash-mcelf-xip')
    return dict(mode=mode, sdk=sdk, tool=tool, images=images,
                content='\n'.join(lines)+'\n', cfg='boot.cfg' if mode == 'uart' else 'flash.cfg')


def configure(root, mode, environment=None):
    if mode not in MODES and mode != 'qspi':
        raise Problem('Modo desconocido. Consulta just modes.')
    values = settings(root, environment)
    if (not (root/SETTINGS).exists() and not values.get('APP_IMAGE')
            and mode not in ('null', 'ospi-multipartition')):
        template = json.loads((root/'sitara.local.example.json').read_text())
        template.update({key: value for key, value in values.items() if key in FIELDS})
        atomic_json(root/SETTINGS, template)
        raise Problem(f'Se creó {SETTINGS}. Completa APP_IMAGE y SDK_INSTALL_PATH y repite just config.')
    plan = configuration(mode, values, root)
    work = cache(root)/str(uuid4())
    work.mkdir(mode=0o700)
    snapshots = {}
    for alias, target in plan['images'].items():
        (work/alias).symlink_to(target)
        snapshots[alias] = dict(path=str(target), sha256=digest(target))
    (work/plan['cfg']).write_text(plan['content'])
    state = dict(mode=plan['mode'], workspace=str(work.relative_to(root)), cfg=plan['cfg'],
                 cfg_sha256=digest(work/plan['cfg']), images=snapshots,
                 tool=dict(path=str(plan['tool']), sha256=digest(plan['tool'])),
                 python=str(Path(sys.executable).resolve()))
    atomic_json(work/'manifest.json', state)
    saved = {key: values[key] for key in FIELDS if key in values}
    saved['SDK_INSTALL_PATH'] = str(plan['sdk'])
    saved['profile'] = plan['mode']
    saved['workspace'] = state['workspace']
    atomic_json(root/SETTINGS, saved)
    print(f'Perfil {plan["mode"]} preparado. Configuración y enlaces en {state["workspace"]}.')
    print('No se compiló, abrió ningún dispositivo ni grabó la placa.')
    return state


def prepared(root):
    values = settings(root, {})  # Execution uses the prepared snapshot, not new environment overrides.
    relative = Path(values.get('workspace', ''))
    if relative.is_absolute() or len(relative.parts) != 2 or relative.parts[0] != '.sitara':
        raise Problem('No hay un perfil preparado. Ejecuta just config.')
    try:
        if str(UUID(relative.parts[1])) != relative.parts[1]:
            raise ValueError
    except ValueError:
        raise Problem('Identificador de preparación no válido; repite just config.') from None
    work = root/relative
    if (root/'.sitara').is_symlink() or work.is_symlink():
        raise Problem('El área preparada no puede ser un enlace simbólico.')
    manifest = work/'manifest.json'
    if manifest.is_symlink():
        raise Problem('Manifest redirigido; prepara de nuevo el perfil.')
    state = json.loads(manifest.read_text())
    if state.get('workspace') != str(relative) or state.get('mode') != values.get('profile'):
        raise Problem('Perfil inconsistente; repite just config.')
    if state.get('mode') not in MODES or state.get('cfg') != ('boot.cfg' if state['mode']=='uart' else 'flash.cfg'):
        raise Problem('Manifest de perfil no válido.')
    cfg = work/state['cfg']
    if cfg.is_symlink() or digest(cfg) != state['cfg_sha256']:
        raise Problem('La configuración generada cambió; repite just config. No se graba un cfg arbitrario.')
    for alias, snapshot in state['images'].items():
        if Path(alias).name != alias:
            raise Problem('Alias de imagen no válido.')
        link = work/alias
        if not link.is_symlink() or str(link.resolve(strict=True)) != snapshot['path'] or digest(link) != snapshot['sha256']:
            raise Problem('Una imagen o enlace cambió; repite just config antes de continuar.')
    tool = Path(state['tool']['path'])
    if digest(tool) != state['tool']['sha256'] or str(Path(sys.executable).resolve()) != state['python']:
        raise Problem('Cambió la herramienta TI o el intérprete Python; repite just config.')
    return values, work, state


def dependencies(mode):
    required = () if mode == 'dfu' else SERIAL_DEPS + (() if mode == 'uart' else ('elftools',))
    missing = [module for module in required if importlib.util.find_spec(module) is None]
    if mode == 'dfu' and not shutil.which('dfu-util'):
        missing.append('dfu-util')
    if missing:
        raise Problem('Faltan dependencias en el intérprete/entorno actual: '+', '.join(missing)+'. No se instalan automáticamente.')


def serial_tools():
    try:
        import serial
        from serial.tools import list_ports
    except ImportError:
        raise Problem('Falta pyserial en el Python que ejecuta just. No se cambian permisos ni se instala automáticamente.') from None
    return serial, list_ports


def enumerate_ports():
    _, listing = serial_tools()
    # Metadata only: no Serial instance, read, write or modem-line operation.
    found = {}
    for item in listing.comports(include_links=True):
        device = str(item.device)
        if not re.fullmatch(r'/dev/tty(?:ACM|USB)\d+', os.path.realpath(device)):
            continue
        identity = os.path.realpath(device)
        text = ' '.join(str(getattr(item, k, '') or '') for k in ('product', 'description', 'manufacturer'))
        eligible = item.vid == 0x0451 and (item.pid == 0xBEF3 or 'xds110' in text.casefold())
        found.setdefault(identity, dict(device=device, vid=item.vid, pid=item.pid, eligible=eligible))
    return sorted(found.values(), key=lambda item: item['device'])


def readiness(port, *, timeout=6.0, factory=None, clock=time.monotonic):
    """Read only the periodic ROM XMODEM CRC request. Never transmit a probe."""
    if factory is None:
        factory = serial_tools()[0].Serial
    connection = factory(port=None, baudrate=115200, timeout=0.2, exclusive=True,
                         rtscts=False, dsrdtr=False, xonxoff=False)
    try:
        # Set before open; some drivers may still pulse lines while opening.
        connection.dtr = False
        connection.rts = False
        connection.port = port
        connection.open()
        until = clock()+timeout
        data = bytearray()
        while clock() < until:
            data.extend(connection.read(64))
            if len(data) > 256:
                return False
            if data and re.search(rb'[^C\s\x00]', data):
                return False  # Logs/application output are not ROM readiness.
            if bytes(data).count(b'C') >= 2:
                return True
        return False
    finally:
        connection.close()


def select_port(explicit='', *, candidates=None, probe=None):
    candidates = enumerate_ports() if candidates is None else candidates
    probe = readiness if probe is None else probe
    if explicit:
        matching = [p for p in candidates if os.path.realpath(p['device']) == os.path.realpath(explicit)]
        if len(matching) != 1:
            raise Problem('El puerto indicado no aparece como dispositivo serie disponible.')
        candidates = matching
    else:
        candidates = [p for p in candidates if p['eligible']]
    ready, errors = [], []
    for item in candidates:
        try:
            if probe(item['device']):
                ready.append(item['device'])
        except (OSError, RuntimeError) as error:
            errors.append(type(error).__name__)
    if errors:
        raise Problem('No se pudo comprobar todos los candidatos (ocupado/permisos/driver). Cierra la terminal o indica un único puerto; no se elige otro silenciosamente.')
    if len(ready) != 1:
        raise Problem('No hay un único puerto listo en modo UART ROM. Usa just ports, configura UART BOOT y reinicia; si hay varios, indica el puerto.')
    return ready[0]


def dfu_ready(*, runner=subprocess.run):
    result = runner(['dfu-util', '-l'], text=True, capture_output=True, timeout=10)
    if result.returncode:
        raise Problem('No se pudo enumerar DFU. Revisa permisos y conexión; no se cambia el sistema.')
    devices = {}
    for line in result.stdout.splitlines():
        match = re.search(r'Found DFU:\s*\[([0-9a-fA-F]{4}):([0-9a-fA-F]{4})\]', line)
        if not match:
            continue
        path = re.search(r'path="([^"]+)"', line)
        if not path:
            raise Problem('No se puede distinguir la identidad física del dispositivo DFU.')
        devices[path[1]] = match[1].lower()
    if len(devices) != 1 or next(iter(devices.values()), '') != '0451':
        raise Problem('Conecta un único dispositivo DFU, de TI, y selecciona DFU BOOT. No se elegirá uno arbitrariamente.')


def vendor_command(state, port=''):
    command = [sys.executable, state['tool']['path']]
    if state['mode'] != 'dfu':
        command += ['-p', port]
    return command + ['--cfg='+state['cfg']]


def run_vendor(command, work, *, factory=subprocess.Popen):
    """One attempt per invocation, terminal output only, no persisted history.

    Legacy receipts/logs are ignored, not changed or deleted. The caller holds
    the project operation lock and validates readiness before each invocation.
    """
    errors, completed = False, False
    process = None
    try:
        process = factory(command, cwd=work, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, text=True, errors='replace', start_new_session=True)
        for line in process.stdout:
            print(line, end='', flush=True)
            errors |= bool(re.search(r'\bERROR\b|\bFAILED\b', line, re.I))
            completed |= 'All commands from config file are executed' in line
        code = process.wait()
        if code or errors or not completed:
            raise Problem('La herramienta TI no confirmó una finalización completa. Puedes reintentar ejecutando el mismo comando. No hay reintento automático.')
    except KeyboardInterrupt:
        if process is not None and process.poll() is None:
            os.killpg(process.pid, signal.SIGINT)
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGTERM)
                process.wait()
        raise Problem('Operación interrumpida; el dispositivo puede haber quedado parcial. Puedes volver a ejecutar el comando para reintentar.') from None
    print('Herramienta TI finalizada sin errores reportados. Esto no certifica el arranque físico de la aplicación.')


def execute(root, action, explicit='', *, selector=None, dfu=None, runner=None):
    values, work, state = prepared(root)
    if (action == 'boot') != (state['mode'] == 'uart'):
        raise Problem('Usa just boot para uart y just flash para los perfiles que escriben flash.')
    dependencies(state['mode'])
    if state['mode'] == 'dfu':
        if explicit:
            raise Problem('DFU no utiliza un puerto ACM; no pases un puerto a just flash.')
        (dfu or dfu_ready)()
        port = ''
    else:
        print('Esperando ROM UART a 115200: abrir el puerto puede afectar DTR/RTS. No se envían bytes de prueba.', flush=True)
        port = (selector or select_port)(explicit or os.environ.get('UART_PORT') or values.get('UART_PORT', ''))
    # Catch files rebuilt or edited while the user was selecting/waiting for a port.
    _, _, current = prepared(root)
    if current != state:
        raise Problem('Cambió el perfil durante la selección; se cancela sin ejecutar TI.')
    print('Perfil:', state['mode'], '|', 'carga RAM' if action == 'boot' else 'ESCRITURA DE FLASH', '| puerto:', port or 'USB DFU')
    (runner or run_vendor)(vendor_command(state, port), work)


def main(argv=None, *, root=ROOT):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('info', 'modes', 'config', 'check', 'ports', 'plan', 'flash', 'boot'))
    parser.add_argument('mode', nargs='?', default='ospi')
    parser.add_argument('--port', default='')
    args = parser.parse_args(argv)
    try:
        if args.action == 'info':
            values = settings(root, {})
            print('Perfil:', values.get('profile', 'sin preparar'))
            print('just modes | just config <modo> | just check | just ports | just plan | just flash [puerto] | just boot [puerto] | just test')
        elif args.action == 'modes':
            for mode, description in MODES.items():
                print(f'{mode}: {description}')
            print('qspi es alias de ospi. Los interruptores físicos se configuran manualmente.')
        elif args.action == 'ports':
            for item in enumerate_ports():
                identity = f'{item["vid"]:04x}:{item["pid"]:04x}' if item['vid'] is not None and item['pid'] is not None else 'sin ID USB'
                print(item['device'], identity, 'candidato XDS110' if item['eligible'] else 'sólo selección explícita')
        elif args.action in ('config', 'flash', 'boot'):
            with operation_lock(root):
                if args.action == 'config':
                    configure(root, args.mode)
                else:
                    execute(root, args.action, args.port)
        else:
            _, _, state = prepared(root)
            if args.action == 'check':
                dependencies(state['mode'])
                print('Perfil, enlaces, imágenes y dependencias comprobados. No se abrió ningún dispositivo.')
                print('La extensión y las interfaces no prueban firma, compatibilidad binaria ni arranque real.')
            else:
                print('Perfil:', state['mode'], '| acción:', 'boot' if state['mode']=='uart' else 'flash')
                print('Herramienta:', Path(state['tool']['path']).name)
                print('Configuración:', state['workspace']+'/'+state['cfg'])
                print('Interruptores:', 'DFU BOOT' if state['mode']=='dfu' else 'UART BOOT', 'antes de iniciar.')
                if state['mode'] == 'null':
                    print('Sólo SBL NULL: la aplicación se carga después con el depurador.')
                elif state['mode'] != 'uart':
                    print('Después de grabar, apagar y seleccionar arranque desde QSPI/OSPI.')
        return 0
    except (Problem, OSError, ValueError, KeyError, TypeError, ImportError) as error:
        # Avoid leaking local paths through FileNotFoundError text into shared docs.
        message = str(error) if isinstance(error, Problem) else f'{type(error).__name__}: revisa configuración, archivos y permisos locales.'
        print('No se completó:', message, file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
