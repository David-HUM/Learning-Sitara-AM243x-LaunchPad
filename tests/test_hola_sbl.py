"""RAM contract tests include allocated NOBITS stacks, not just file bytes."""
import io
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

import sbl_fixtures
import test_hola_zephyr
import hola_sbl


class MemoryContractTests(unittest.TestCase):
    def setUp(self):
        self.fixture = test_hola_zephyr.HolaZephyrTests(methodName='runTest')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.p = self.fixture.p
        self.q = hola_sbl.paths(self.p)

    def test_corrected_pair_is_disjoint(self):
        report = hola_sbl.check_pair(self.p)
        self.assertFalse(report['overlap'])
        self.assertTrue(any(name == '.stack' for name, _, _ in report['sbl_allocated']))

    def test_original_sdk_stack_is_rejected_even_without_file_bytes(self):
        self.q['elf'].write_bytes(sbl_fixtures.sbl_elf(stack=0x7007f300))
        with self.assertRaisesRegex(hola_sbl.sitara.Problem, 'invade'):
            hola_sbl.validate_ram(self.q['elf'], self.p['elf'])

    def test_irq_stack_reaches_reserved_app_ram_even_if_main_stack_fits(self):
        self.q['elf'].write_bytes(sbl_fixtures.sbl_elf(stack=0x7007b100))
        with self.assertRaisesRegex(hola_sbl.sitara.Problem, 'invade'):
            hola_sbl.validate_ram(self.q['elf'], self.p['elf'])

    def test_explicit_application_load_overlap_is_rejected(self):
        self.p['elf'].write_bytes(sbl_fixtures.base.elf_file([(1, 0x70070000, b'app', 0x100)]))
        with self.assertRaisesRegex(hola_sbl.sitara.Problem, 'Solapamiento'):
            hola_sbl.validate_ram(self.q['elf'], self.p['elf'])

    def test_scratch_buffer_does_not_falsely_overlap_lower_app_ram(self):
        self.q['elf'].write_bytes(sbl_fixtures.sbl_elf(extra=(0x70180000, 0x40000)))
        self.assertFalse(hola_sbl.validate_ram(self.q['elf'], self.p['elf'])['overlap'])

    def test_changed_sbl_binary_blocks_pair_and_regular_app_check(self):
        self.q['image'].write_bytes(b'changed image')
        with self.assertRaises(hola_sbl.sitara.Problem):
            hola_sbl.check_pair(self.p)
        with self.assertRaises(hola_sbl.sitara.Problem):
            self.fixture.checking()

    def test_changed_sbl_source_requires_rebuild(self):
        source = self.q['sdk']/hola_sbl.EXAMPLE/'main.c'
        source.write_text('different source')
        with self.assertRaises(hola_sbl.sitara.Problem):
            hola_sbl.check_pair(self.p)

    def test_mpu_disabled_in_generated_config_is_rejected(self):
        (self.p['build']/'zephyr/.config').write_text('# CONFIG_ARM_MPU is not set\n')
        with self.assertRaisesRegex(hola_sbl.sitara.Problem, 'CONFIG_ARM_MPU'):
            hola_sbl.check_pair(self.p)

    def test_failed_sbl_receipt_blocks_even_previously_existing_outputs(self):
        self.q['receipt'].write_text(json.dumps({'status': 'building'}))
        with self.assertRaises(hola_sbl.sitara.Problem):
            hola_sbl.check_pair(self.p)

    def test_oversized_sbl_cannot_reach_application_flash_slot(self):
        self.q['image'].write_bytes(bytes(0x80000))
        receipt = json.loads(self.q['receipt'].read_text())
        receipt['outputs'] = hola_sbl.hashes(hola_sbl.artifacts(self.p))
        self.q['receipt'].write_text(json.dumps(receipt))
        with self.assertRaisesRegex(hola_sbl.sitara.Problem, 'partición'):
            hola_sbl.check_pair(self.p)

    def buildable_source(self):
        source = self.q['sdk']/hola_sbl.EXAMPLE/'example.syscfg'
        source.write_text('''region1.memory_region[4].manualStartAddress = 0x70000100;
region1.memory_region[4].size = 0x6FF00;
region1.memory_region[5].manualStartAddress = 0x70070000;
region1.memory_region[5].size = 0x20000;
''')
        return source

    def test_build_never_publishes_into_sdk_prebuilt_directory(self):
        source = self.buildable_source()
        before = source.read_bytes()
        calls = []
        with patch('sys.stdout', new_callable=io.StringIO):
            hola_sbl.build(self.p, runner=lambda cmd, **kw: calls.append((cmd, kw)))
        self.assertEqual(source.read_bytes(), before)
        self.assertIn('SBL_PREBUILT_PATH='+str(self.q['stage']/'artifacts'), calls[0][0])
        self.assertIn('MCU_PLUS_SDK_PATH='+str(self.q['sdk']), calls[0][0])
        self.assertNotIn('flash', calls[0][0])
        self.assertIn('0x70060000', (self.q['stage']/'example.syscfg').read_text())

    def test_failed_build_invalidates_old_sbl_receipt(self):
        self.buildable_source()
        def failed(cmd, **kw):
            raise subprocess.CalledProcessError(1, cmd)
        with self.assertRaises(subprocess.CalledProcessError):
            hola_sbl.build(self.p, runner=failed)
        self.assertEqual(json.loads(self.q['receipt'].read_text())['status'], 'building')
        with self.assertRaises(hola_sbl.sitara.Problem):
            hola_sbl.check_pair(self.p)

    def test_hello_world_does_not_acquire_a_hola_sbl_dependency(self):
        with self.assertRaises(hola_sbl.sitara.Problem):
            hola_sbl.paths(self.fixture.hello)
        self.fixture.test_legacy_hello_receipt_is_still_supported()


class ConfigPatchTests(unittest.TestCase):
    def test_only_the_reviewed_ram_assignments_change(self):
        original = '''region1.memory_region[4].manualStartAddress = 0x70000100;
region1.memory_region[4].size = 0x6FF00;
region1.memory_region[5].manualStartAddress = 0x70070000;
region1.memory_region[5].size = 0x20000;
flash1.protocol = "do-not-change";
'''
        path = Path(__file__).resolve().parents[1]/'apps/hola_zephyr/bootloader/ram-layout.json'
        result = hola_sbl.corrected_config(original, json.loads(path.read_text()))
        self.assertIn('size = 0x5ff00;', result)
        self.assertIn('manualStartAddress = 0x70060000;', result)
        self.assertIn('flash1.protocol = "do-not-change";', result)
        with self.assertRaises(hola_sbl.sitara.Problem):
            hola_sbl.corrected_config(original.replace('0x70070000', '0x70100000'), json.loads(path.read_text()))


if __name__ == '__main__':
    unittest.main()
