"""Synthetic ELF sections and build receipts, never real firmware/signatures."""
import json
from pathlib import Path
import struct

import test_zephyr_local as base
import hola_sbl


def sbl_elf(*, stack=0x7006f300, extra=None):
    data = bytearray(base.elf_file([(1, 0x70000100, b'SBL!', 4)]))
    names = b'\0.text\0.bss\0.stack\0.irqstack\0.shstrtab\0'
    name_offset = len(data)
    data.extend(names)
    data.extend(bytes((-len(data)) % 4))
    section_offset = len(data)
    specs = [('', 0, 0, 0, 0, 0),
             ('.text', 1, 6, 0x70000100, 84, 4),
             ('.bss', 8, 3, 0x70060000, 0, 0xf300),
             ('.stack', 8, 3, stack, 0, 0x4000),
             ('.irqstack', 8, 3, stack+0x4000, 0, 0x1000),
             ('.shstrtab', 3, 0, 0, name_offset, len(names))]
    if extra:
        # Reuse a known section name for a synthetic allocated scratch range.
        specs.append(('.bss', 8, 3, extra[0], 0, extra[1]))
    for name, kind, flags, address, offset, size in specs:
        index = names.index(name.encode()+b'\0') if name else 0
        data.extend(struct.pack('<IIIIIIIIII', index, kind, flags, address,
                                offset, size, 0, 0, 4, 0))
    struct.pack_into('<I', data, 32, section_offset)
    struct.pack_into('<HHH', data, 46, 40, len(specs), 5)
    return bytes(data)


def prepare(p):
    q = hola_sbl.paths(p)
    q['tool'].mkdir(parents=True, exist_ok=True)
    q['layout'].parent.mkdir(parents=True, exist_ok=True)
    actual_layout = Path(__file__).resolve().parents[1]/'apps/hola_zephyr/bootloader/ram-layout.json'
    q['layout'].write_bytes(actual_layout.read_bytes())
    for key, file in hola_sbl.source_files(p).items():
        if key.startswith('sdk:') and not file.exists():
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_bytes(b'synthetic SDK input')
    q['elf'].write_bytes(sbl_elf())
    q['binary'].write_bytes(b'Synthetic SBL raw bytes')
    q['image'].write_bytes(b'\x30\x03abcSynthetic SBL - not a real signature')
    q['map'].write_text('synthetic map, not actual linker evidence')
    (p['build']/'zephyr/.config').write_text('CONFIG_ARM_MPU=y\n')
    base.sitara.atomic_json(q['receipt'], {
        'status': 'built', 'inputs': hola_sbl.hashes(hola_sbl.source_files(p)),
        'outputs': hola_sbl.hashes(hola_sbl.artifacts(p)),
        'hardware_validation': 'not performed',
    })
    return q
