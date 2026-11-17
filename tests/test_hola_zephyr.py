"""Independent-app tests: synthetic images, mocked UART and a host C harness.

The host sleep is mocked. It checks the program's text and requested 3000 ms,
not Zephyr scheduling, UART hardware or actual wall-clock accuracy on the board.
"""
import io
import json
from pathlib import Path
import shlex
import shutil
import struct
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import test_zephyr_local as fixtures
import sbl_fixtures

local = fixtures.local
sitara = fixtures.sitara
PROJECT = Path(__file__).resolve().parents[1]


class HolaZephyrTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.LocalZephyrTests(methodName='runTest')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.root
        self.hello = self.fixture.p
        app = self.root/'apps/hola_zephyr'
        (app/'src').mkdir(parents=True)
        for name in ('CMakeLists.txt', 'prj.conf', 'src/main.c', 'app.overlay', 'mpu_dt_compat.h',
                     'Kconfig', 'src/early_uart_trace.S', 'src/boot_trace.c',
                     'early_uart_trace.ld'):
            shutil.copy2(PROJECT/'apps/hola_zephyr'/name, app/name)
        kernel_init = self.root/'zephyr/kernel/init.c'
        kernel_init.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(PROJECT/'zephyr/kernel/init.c', kernel_init)
        prep_c = self.root/'zephyr/arch/arm/core/cortex_a_r/prep_c.c'
        prep_c.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(PROJECT/'zephyr/arch/arm/core/cortex_a_r/prep_c.c', prep_c)
        reset_asm = self.root/'zephyr/arch/arm/core/cortex_a_r/reset.S'
        shutil.copy2(PROJECT/'zephyr/arch/arm/core/cortex_a_r/reset.S', reset_asm)
        vim_init = self.root/'zephyr/drivers/interrupt_controller/intc_vim.c'
        vim_init.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(PROJECT/'zephyr/drivers/interrupt_controller/intc_vim.c', vim_init)
        pinctrl_init = self.root/'zephyr/drivers/pinctrl/pinctrl_ti_k3.c'
        shutil.copy2(PROJECT/'zephyr/drivers/pinctrl/pinctrl_ti_k3.c', pinctrl_init)
        irq_init = self.root/'zephyr/arch/arm/core/cortex_a_r/irq_init.c'
        shutil.copy2(PROJECT/'zephyr/arch/arm/core/cortex_a_r/irq_init.c', irq_init)
        soc_init = self.root/'zephyr/soc/ti/k3/common/cortex_r/soc.c'
        soc_init.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(PROJECT/'zephyr/soc/ti/k3/common/cortex_r/soc.c', soc_init)
        for key in ('writer', 'tool'):
            original = self.hello[key]
            destination = self.root/'mcu_plus_sdk'/original.relative_to(self.hello['ti_sdk'])
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(b'locally built SDK '+key.encode())
        self.p = local.parameters(self.root, 'hola_zephyr')
        self.fixture.p = self.p
        self.p['boot'].mkdir(parents=True)
        self.p['elf'].parent.mkdir(parents=True)
        self.fixture.cache()
        self.fixture.images(message=b'hola soy zephyr\n')
        with patch('sys.stdout', new_callable=io.StringIO):
            local.copy_writer(self.p)
        local.write_cfg(self.p)
        sbl_fixtures.prepare(self.p)
        self.fixture.ready()

    def checking(self):
        return self.fixture.checking()

    def test_app_is_outside_vendor_tree_and_build_is_separate(self):
        self.assertEqual(self.p['app'], self.root/'apps/hola_zephyr')
        self.assertEqual(self.p['source'], self.root/'zephyr')
        self.assertEqual(self.p['build'], self.root/'apps/hola_zephyr/build')
        self.assertNotEqual(self.p['cfg'], self.hello['cfg'])
        self.assertNotEqual(self.p['signed'], self.hello['signed'])

    def test_unknown_app_is_rejected(self):
        with self.assertRaises(sitara.Problem):
            local.parameters(self.root, '../other-app')

    def test_hola_payload_passes_without_hello_world_string(self):
        self.assertNotIn(b'Hello World!', self.p['mcelf'].read_bytes())
        self.checking()

    def test_hello_world_payload_is_not_accepted_as_hola(self):
        self.fixture.images()
        with self.assertRaises(sitara.Problem):
            local.image_integrity(self.p)

    def test_ti_absent_section_table_with_stale_index_is_read_without_image_edits(self):
        self.fixture.images(message=b'hola soy zephyr\n'+b'\xff'*1600)
        data = bytearray(self.p['mcelf'].read_bytes())
        struct.pack_into('<H', data, 46, 40)  # Original ELF32 e_shentsize.
        struct.pack_into('<H', data, 50, 30)  # TI's unreset e_shstrndx.
        self.p['mcelf'].write_bytes(data)
        signed = b'\x30\x03abc'+data
        self.p['signed'].write_bytes(signed)
        local.image_integrity(self.p)
        self.assertEqual(self.p['mcelf'].read_bytes(), data)
        self.assertEqual(self.p['signed'].read_bytes(), signed)

    def test_malformed_mcelf_is_rejected_with_controlled_error(self):
        self.p['mcelf'].write_bytes(b'not an ELF')
        with self.assertRaises(sitara.Problem):
            local.image_integrity(self.p)

    def test_other_apps_receipt_is_rejected(self):
        receipt = json.loads(self.p['verification'].read_text())
        receipt['app'] = 'hello_world'
        sitara.atomic_json(self.p['verification'], receipt)
        with self.assertRaises(sitara.Problem):
            self.checking()

    def test_legacy_hello_receipt_is_still_supported(self):
        receipt = json.loads(self.hello['verification'].read_text())
        receipt.pop('app')
        sitara.atomic_json(self.hello['verification'], receipt)
        with patch.object(sitara, 'dependencies'), patch('sys.stdout', new_callable=io.StringIO):
            local.check(self.hello)

    def test_cfg_uses_copied_writer_and_only_application_partition(self):
        lines = [shlex.split(line) for line in local.cfg_content(self.p).splitlines()[1:]]
        self.assertEqual(lines[0], ['--flash-writer='+self.p['writer'].name])
        for line, operation in zip(lines[1:], ('flash', 'flashverify')):
            self.assertIn('--file='+str(self.p['signed']), line)
            self.assertIn('--operation='+operation, line)
            self.assertIn('--flash-offset=0x80000', line)
        self.assertEqual(len(lines), 3)
        self.assertNotIn('flash-phy-tuning-data', local.cfg_content(self.p))

    def test_writer_is_an_independent_copy_from_local_sdk(self):
        self.assertEqual(self.p['writer'].parent, self.p['build'])
        self.assertFalse(self.p['writer'].is_symlink())
        self.assertEqual(self.p['writer'].read_bytes(), self.p['writer_source'].read_bytes())
        self.assertEqual(self.p['tool'], self.root/'mcu_plus_sdk/tools/boot/uart_uniflash.py')

    def test_changed_copied_writer_is_rejected(self):
        self.p['writer'].write_bytes(b'wrong writer')
        with self.assertRaises(sitara.Problem):
            self.checking()

    def test_newly_rebuilt_writer_requires_explicit_app_build(self):
        self.p['writer_source'].write_bytes(b'newly rebuilt local writer')
        with self.assertRaises(sitara.Problem):
            self.checking()
        with patch('sys.stdout', new_callable=io.StringIO):
            local.copy_writer(self.p)
        self.assertEqual(self.p['writer'].read_bytes(), b'newly rebuilt local writer')
        # A copy alone must not reset the verified build receipt.
        with self.assertRaises(sitara.Problem):
            self.checking()

    def test_writer_symlink_is_rejected(self):
        self.p['writer'].unlink()
        self.p['writer'].symlink_to(self.p['writer_source'])
        with self.assertRaises(sitara.Problem):
            local.copy_writer(self.p)

    def test_cmake_change_requires_rebuild(self):
        (self.p['app']/'CMakeLists.txt').write_text('changed build description')
        with self.assertRaises(sitara.Problem):
            self.checking()

    def test_overlay_change_requires_rebuild(self):
        self.p['overlay'].write_text('changed memory mapping')
        with self.assertRaises(sitara.Problem):
            self.checking()

    def test_missing_overlay_is_rejected(self):
        self.p['overlay'].unlink()
        with self.assertRaises(sitara.Problem):
            local.parameters(self.root, 'hola_zephyr')

    def test_mpu_compat_change_requires_rebuild(self):
        self.p['mpu_compat'].write_text('changed MPU conversion')
        with self.assertRaises(sitara.Problem):
            self.checking()

    def test_trace_source_change_requires_rebuild(self):
        (self.p['app']/'src/early_uart_trace.S').write_text('changed trace')
        with self.assertRaises(sitara.Problem):
            self.checking()

    def test_trace_linker_change_requires_rebuild(self):
        (self.p['app']/'early_uart_trace.ld').write_text('changed vector layout')
        with self.assertRaises(sitara.Problem):
            self.checking()

    def test_trace_kconfig_change_requires_rebuild(self):
        (self.p['app']/'Kconfig').write_text('changed trace configuration')
        with self.assertRaises(sitara.Problem):
            self.checking()

    def test_instrumented_zephyr_kernel_change_requires_rebuild(self):
        (self.p['source']/'kernel/init.c').write_text('changed kernel startup')
        with self.assertRaises(sitara.Problem):
            self.checking()

    def test_instrumented_prep_c_change_requires_rebuild(self):
        path = self.p['source']/'arch/arm/core/cortex_a_r/prep_c.c'
        path.write_text('changed architecture startup')
        with self.assertRaises(sitara.Problem):
            self.checking()

    def test_instrumented_reset_change_requires_rebuild(self):
        path = self.p['source']/'arch/arm/core/cortex_a_r/reset.S'
        path.write_text('changed architecture reset')
        with self.assertRaises(sitara.Problem):
            self.checking()

    def test_instrumented_vim_init_change_requires_rebuild(self):
        path = self.p['source']/'drivers/interrupt_controller/intc_vim.c'
        path.write_text('changed VIM interrupt startup')
        with self.assertRaises(sitara.Problem):
            self.checking()

    def test_instrumented_pinctrl_init_change_requires_rebuild(self):
        path = self.p['source']/'drivers/pinctrl/pinctrl_ti_k3.c'
        path.write_text('changed pinctrl startup')
        with self.assertRaises(sitara.Problem):
            self.checking()

    def test_instrumented_irq_init_change_requires_rebuild(self):
        path = self.p['source']/'arch/arm/core/cortex_a_r/irq_init.c'
        path.write_text('changed ARM interrupt startup')
        with self.assertRaises(sitara.Problem):
            self.checking()

    def test_instrumented_soc_irq_init_change_requires_rebuild(self):
        path = self.p['source']/'soc/ti/k3/common/cortex_r/soc.c'
        path.write_text('changed SoC interrupt startup')
        with self.assertRaises(sitara.Problem):
            self.checking()

    def test_boot_trace_change_requires_rebuild(self):
        (self.p['app']/'src/boot_trace.c').write_text('changed boot trace')
        with self.assertRaises(sitara.Problem):
            self.checking()

    def test_build_preserves_hello_world_and_never_opens_uart(self):
        before = local.snapshots(self.hello)
        calls = []
        with patch.object(sitara, 'select_port', side_effect=AssertionError('UART forbidden')):
            with patch('sys.stdout', new_callable=io.StringIO):
                local.build(self.p, runner=lambda cmd, **kw: calls.append((cmd, kw)))
        self.assertEqual(len(calls), 3)
        self.assertEqual(calls[0][0][1:4], ['-m', 'west', 'build'])
        self.assertIn(str(self.p['app']), calls[0][0])
        self.assertIn('-DDTC_OVERLAY_FILE='+str(self.p['overlay']), calls[0][0])
        self.assertIn('--core-img=4:'+str(self.p['elf']), calls[1][0])
        self.assertEqual(local.snapshots(self.hello), before)
        self.checking()

    def test_check_never_opens_uart(self):
        with patch.object(sitara, 'select_port', side_effect=AssertionError('UART forbidden')):
            self.checking()

    def test_flash_uses_own_cfg_tool_and_working_directory(self):
        calls = []
        with patch.object(sitara, 'dependencies'), patch('sys.stdout', new_callable=io.StringIO):
            local.flash(self.p, '/dev/fake', selector=lambda port: port,
                        vendor=lambda cmd, cwd: calls.append((cmd, cwd)))
        command, cwd = calls[0]
        self.assertEqual(command[1], str(self.p['tool']))
        self.assertEqual(command[-1], '--cfg='+str(self.p['cfg']))
        self.assertEqual(cwd, self.p['writer'].parent)

    def test_old_failed_attempt_does_not_block_new_explicit_flash(self):
        sitara.atomic_json(self.p['build']/'receipt.json', {'status': 'started'})
        calls = []
        with patch.object(sitara, 'dependencies'), patch('sys.stdout', new_callable=io.StringIO):
            local.flash(self.p, '/dev/fake', selector=lambda port: port,
                        vendor=lambda cmd, cwd: calls.append((cmd, cwd)))
        self.assertEqual(len(calls), 1)


class HolaProgramTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('cc'), 'Host C compiler unavailable')
    def test_mpu_compat_sets_separate_r5_size_without_corrupting_attributes(self):
        with tempfile.TemporaryDirectory(prefix='hola-mpu-') as directory:
            root = Path(directory)
            include = root/'include/zephyr/arch/arm/mpu'
            include.mkdir(parents=True)
            (include/'arm_mpu.h').write_text('''
#include <stdint.h>
#define CONFIG_ARMV7_R 1
#define CONFIG_CPU_AARCH32_CORTEX_R 1
struct attr { uint32_t rasr; };
struct arm_mpu_region {
    uint32_t base; const char *name; uint32_t size; struct attr attr;
};
''')
            source = root/'test.c'
            source.write_text('''
#include "mpu_dt_compat.h"
static uint32_t size_to_mpu_rasr_size(uint32_t size) {
    uint32_t bits = 0;
    while (size > 1) { bits++; size >>= 1; }
    return (bits - 1) << 1;
}
#define TEST_ATTR(size) { 0x100 | (size) }
int main(void) {
    struct arm_mpu_region region =
        ARM_MPU_REGION_INIT("ATCM", 0, 32768, TEST_ATTR);
    return !(region.base == 0 && region.size == 28 && region.attr.rasr == 0x100);
}
''')
            executable = root/'test-mpu'
            subprocess.run([shutil.which('cc'), '-std=c11', '-Wall', '-Wextra', '-Werror',
                            '-I'+str(root/'include'), '-I'+str(PROJECT/'apps/hola_zephyr'),
                            str(source), '-o', str(executable)], check=True, capture_output=True)
            subprocess.run([str(executable)], check=True, timeout=5)

    @unittest.skipUnless(shutil.which('cc'), 'Host C compiler unavailable')
    def test_actual_main_prints_three_times_and_requests_three_second_sleeps(self):
        with tempfile.TemporaryDirectory(prefix='hola-program-') as directory:
            root = Path(directory)
            (root/'include/zephyr/sys').mkdir(parents=True)
            (root/'include/zephyr/kernel.h').write_text(
                '#define K_SECONDS(s) ((s) * 1000)\nvoid k_sleep(int ms);\n')
            (root/'include/zephyr/sys/printk.h').write_text(
                'int printk(const char *format, ...);\n')
            stub = root/'stubs.c'
            stub.write_text('''
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
int printk(const char *format, ...) {
    va_list args; va_start(args, format);
    int count = vprintf(format, args); va_end(args); return count;
}
void k_sleep(int ms) {
    static int sleeps;
    if (ms != 3000) exit(2);
    if (++sleeps == 3) exit(0);
}
''')
            executable = root/'test-hola'
            subprocess.run([shutil.which('cc'), '-std=c11', '-Wall', '-Wextra', '-Werror',
                            '-I'+str(root/'include'), str(PROJECT/'apps/hola_zephyr/src/main.c'),
                            str(stub), '-o', str(executable)], check=True, capture_output=True)
            result = subprocess.run([str(executable)], check=True, text=True,
                                    capture_output=True, timeout=5)
            self.assertEqual(result.stdout, 'hola soy zephyr\n'*3)


if __name__ == '__main__':
    unittest.main()
