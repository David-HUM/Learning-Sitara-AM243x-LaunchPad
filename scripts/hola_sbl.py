"""App-local SBL build and RAM contract. This module never opens hardware.

TI sources are copied into hola_zephyr/build/sbl, with their original notices.
Only the two SRAM assignments are changed in the staged SysConfig source.
The SDK, its prebuilt directory and the Hello World app are never overwritten.
"""
import io
import json
from pathlib import Path
import re
import shutil
import subprocess

import sitara


EXAMPLE = Path('examples/drivers/boot/sbl_ospi/am243x-lp/r5fss0-0_nortos')
SDK_INPUTS = (
    EXAMPLE/'main.c', EXAMPLE/'example.syscfg', EXAMPLE/'ti-arm-clang/makefile',
    Path('imports.mak'), Path('devconfig/devconfig.mak'), Path('.metadata/product.json'),
    Path('source/kernel/nortos/lib/nortos.am243x.r5f.ti-arm-clang.release.lib'),
    Path('source/drivers/lib/drivers.am243x.r5f.ti-arm-clang.nortos.release.lib'),
    Path('source/board/lib/board.am243x.r5f.ti-arm-clang.nortos.release.lib'),
    Path('source/sysconfig/board/.meta/flash/v0/flash_v0.syscfg.js'),
    Path('source/sysconfig/board/.meta/flash/templates/v0/flash_open_close_config.c.xdt'),
    Path('source/drivers/sciclient/soc/am64x_am243x/sysfw-hs-fs-enc.bin'),
    Path('source/drivers/sciclient/soc/am64x_am243x/sysfw-hs-fs-enc-cert.bin'),
    Path('source/drivers/sciclient/sciclient_default_boardcfg/am243x/boardcfg_blob.bin'),
    Path('source/security/security_common/tools/boot/signing/rom_image_gen.py'),
)
SBL_RAM_START, APP_RAM_START = 0x70000000, 0x70080000
SCRATCH_START = 0x70180000


def paths(p):
    if p['app_name'] != 'hola_zephyr':
        raise sitara.Problem('El SBL aislado pertenece sólo a hola_zephyr.')
    stage = p['build']/'sbl'
    tool = stage/'ti-arm-clang'
    return dict(sdk=p['root']/'mcu_plus_sdk', stage=stage, tool=tool,
                layout=p['app']/'bootloader/ram-layout.json',
                elf=tool/'sbl_ospi.release.out', binary=tool/'sbl_ospi.release.bin',
                image=tool/'sbl_ospi.release.hs_fs.tiimage',
                map=tool/'sbl_ospi.release.map', receipt=stage/'verification.json')


def source_files(p):
    q = paths(p)
    files = {'sdk:'+name.as_posix(): q['sdk']/name for name in SDK_INPUTS}
    files.update(layout=q['layout'], adapter=Path(__file__).resolve())
    return files


def hashes(files):
    return {name: sitara.digest(path) for name, path in files.items()}


def corrected_config(original, layout):
    expected = {'msram_code_start': '0x70000100', 'msram_code_size': '0x5ff00',
                'msram_stacks_start': '0x70060000', 'msram_stacks_size': '0x20000'}
    if layout != expected:
        raise sitara.Problem('El layout SBL no es el contrato revisado para esta app.')
    fields = ((4, 'manualStartAddress', '0x70000100', layout['msram_code_start']),
              (4, 'size', '0x6ff00', layout['msram_code_size']),
              (5, 'manualStartAddress', '0x70070000', layout['msram_stacks_start']),
              (5, 'size', '0x20000', layout['msram_stacks_size']))
    for index, field, before, after in fields:
        pattern = (r'(region1\.memory_region\['+str(index)+r'\]\.'+field
                   +r'\s*=\s*)(0x[0-9a-fA-F]+)(\s*;)')
        matches = list(re.finditer(pattern, original))
        if len(matches) != 1 or matches[0].group(2).lower() not in (before, after):
            raise sitara.Problem('SysConfig TI distinto al revisado: '+str(index)+'.'+field)
        original = re.sub(pattern, lambda m: m.group(1)+after+m.group(3), original)
    return original


def elf_ranges(path, *, sections=False):
    from elftools.common.exceptions import ELFError
    from elftools.elf.elffile import ELFFile
    try:
        elf = ELFFile(io.BytesIO(Path(path).read_bytes()))
        if elf['e_machine'] != 'EM_ARM' or elf.elfclass != 32 or not elf.little_endian:
            raise sitara.Problem('El contrato de RAM requiere ELF ARM32 little-endian.')
        if sections:
            ranges = [(s.name, s['sh_addr'], s['sh_addr']+s['sh_size'])
                      for s in elf.iter_sections() if s['sh_flags'] & 2 and s['sh_size']]
        else:
            ranges = [('PT_LOAD', s['p_paddr'], s['p_paddr']+s['p_memsz'])
                      for s in elf.iter_segments() if s['p_type'] == 'PT_LOAD' and s['p_memsz']]
        if not ranges or any(a < 0 or b <= a or b > 0x100000000 for _, a, b in ranges):
            raise sitara.Problem('ELF sin rangos de memoria válidos: '+str(path))
        return ranges
    except ELFError as error:
        raise sitara.Problem('ELF de memoria no válido: '+str(error)) from error


def validate_ram(sbl_elf, app_elf=None):
    """Include SHF_ALLOC NOBITS: stacks/BSS do not need bytes in the file."""
    sbl = elf_ranges(sbl_elf, sections=True)
    for required in ('.bss', '.stack', '.irqstack'):
        if not any(name == required for name, _, _ in sbl):
            raise sitara.Problem('El ELF SBL no describe '+required)
    for name, start, end in sbl:
        if SBL_RAM_START <= start < SCRATCH_START and end > APP_RAM_START:
            raise sitara.Problem(f'SBL invade la RAM reservada a Zephyr: {name} '
                                 f'[{start:#x}, {end:#x}). Límite {APP_RAM_START:#x}.')
    app = elf_ranges(app_elf) if app_elf is not None else []
    for name, start, end in sbl:
        for _, app_start, app_end in app:
            if max(start, app_start) < min(end, app_end):
                raise sitara.Problem(f'Solapamiento SBL/{Path(app_elf).name}: '
                                     f'{name} [{start:#x}, {end:#x}) con '
                                     f'[{app_start:#x}, {app_end:#x}).')
    return {'sbl_allocated': sbl, 'application_loads': app,
            'reserved_application_start': APP_RAM_START, 'overlap': False}


def artifacts(p):
    q = paths(p)
    return {key: q[key] for key in ('elf', 'binary', 'image', 'map')}


def build(p, *, runner=subprocess.run):
    q = paths(p)
    for path in (p['build'], q['stage'], q['tool'], q['stage']/'artifacts'):
        if path.is_symlink():
            raise sitara.Problem('El directorio del SBL no puede ser un enlace: '+str(path))
        path.mkdir(parents=True, exist_ok=True)
    before = hashes(source_files(p))
    for output in (*artifacts(p).values(), q['tool']/'generated', q['tool']/'obj',
                   q['tool']/'tiboot3.bin'):
        if output.is_symlink():
            raise sitara.Problem('Una salida temporal del SBL es un enlace: '+str(output))
    sitara.atomic_json(q['receipt'], {'status': 'building'})
    layout = json.loads(q['layout'].read_text())
    content = corrected_config((q['sdk']/EXAMPLE/'example.syscfg').read_text(), layout)
    destinations = ((q['sdk']/EXAMPLE/'main.c', q['stage']/'main.c'),
                    (q['sdk']/EXAMPLE/'ti-arm-clang/makefile', q['tool']/'makefile'))
    for source, destination in destinations:
        if destination.is_symlink():
            raise sitara.Problem('Una fuente temporal del SBL es un enlace.')
        shutil.copy2(source, destination)
    staged_cfg = q['stage']/'example.syscfg'
    if staged_cfg.is_symlink():
        raise sitara.Problem('El SysConfig temporal es un enlace.')
    staged_cfg.write_text(content)
    command = ['make', '-C', str(q['tool']), 'all', 'DEVICE=am243x', 'PROFILE=release',
               'MCU_PLUS_SDK_PATH='+str(q['sdk']), 'PYTHON='+str(p['python']),
               'SBL_PREBUILT_PATH='+str(q['stage']/'artifacts')]
    runner(command, cwd=p['root'], check=True)
    if before != hashes(source_files(p)):
        raise sitara.Problem('Las fuentes o bibliotecas TI cambiaron durante el build SBL.')
    if not 0 < q['image'].stat().st_size < 0x80000:
        raise sitara.Problem('La imagen SBL no cabe antes de la partición de aplicación.')
    report = validate_ram(q['elf'])
    sitara.atomic_json(q['receipt'], {'status': 'built', 'inputs': before,
                       'outputs': hashes(artifacts(p)), 'ram': report,
                       'hardware_validation': 'not performed'})
    print('SBL aislado compilado:', q['image'])
    print('Código, BSS y pilas debajo de 0x70080000. No se grabó ni copió al SDK.')


def check_pair(p):
    q = paths(p)
    if not q['receipt'].is_file():
        raise sitara.Problem('Falta el SBL corregido. Ejecuta just build-sbl en hola_zephyr.')
    receipt = json.loads(q['receipt'].read_text())
    if (receipt.get('status') != 'built' or receipt.get('inputs') != hashes(source_files(p))
            or receipt.get('outputs') != hashes(artifacts(p))):
        raise sitara.Problem('El SBL o sus entradas cambiaron. Repite just build-sbl.')
    if not 0 < q['image'].stat().st_size < 0x80000:
        raise sitara.Problem('La imagen SBL invade la partición de aplicación.')
    config = p['build']/'zephyr/.config'
    if 'CONFIG_ARM_MPU=y' not in config.read_text().splitlines():
        raise sitara.Problem('hola_zephyr requiere CONFIG_ARM_MPU=y en el build generado.')
    return validate_ram(q['elf'], p['elf'])


def describe(report):
    for name, start, end in report['sbl_allocated']:
        if name in ('.bss', '.stack', '.irqstack', '.fiqstack', '.svcstack',
                    '.abortstack', '.undefinedstack'):
            print(f'SBL {name}: [{start:#010x}, {end:#010x})')
    for _, start, end in report['application_loads']:
        print(f'Zephyr PT_LOAD: [{start:#010x}, {end:#010x})')
    print('Sin solapamiento entre el SBL corregido y la aplicación local.')
