"""Synthetic files/subprocesses only. These tests never open hardware."""
import io
import json
from pathlib import Path
import shlex
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import zephyr_local as local
import sitara


def note(name, typ, data):
    return (struct.pack('<III', len(name), len(data), typ)
            + name + bytes((-len(name)) % 4) + data + bytes((-len(data)) % 4))


def elf_file(segments):
    offset = 52 + 32*len(segments)
    headers, chunks = [], []
    for kind, addr, data, memory in segments:
        headers.append(struct.pack('<IIIIIIII', kind, offset, addr, addr,
                                   len(data), memory, 7, 4))
        chunks.append(data)
        offset += len(data)
    ident = b'\x7fELF\x01\x01\x01' + bytes(9)
    header = struct.pack('<16sHHIIIIIHHHHHH', ident, 2, 40, 1, 0, 52, 0,
                         0x5000400, 52, 32, len(segments), 0, 0, 0)
    return header + b''.join(headers) + b''.join(chunks)


class LocalZephyrTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='sitara test ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        sdk = self.root/'ti-sdk'
        py = self.root/'venv/bin/python'
        py.parent.mkdir(parents=True)
        py.write_text('synthetic executable')
        zsdk = self.root/'zephyr-sdk'
        zsdk.mkdir()
        module = self.root/'cmsis'
        module.mkdir()
        settings = {'python': str(py), 'zephyr_sdk': str(zsdk),
                    'ti_sdk': str(sdk), 'modules': [str(module)]}
        (self.root/local.SETTINGS).write_text(json.dumps(settings))
        app = self.root/'apps/hello_world'
        (app/'src').mkdir(parents=True)
        for name in ('CMakeLists.txt', 'prj.conf', 'src/main.c'):
            (app/name).write_text('synthetic source')
        (self.root/'zephyr/kernel').mkdir(parents=True)
        (self.root/'zephyr/kernel/init.c').write_text('synthetic kernel init')
        (self.root/'zephyr/arch/arm/core/cortex_a_r').mkdir(parents=True)
        (self.root/'zephyr/arch/arm/core/cortex_a_r/prep_c.c').write_text(
            'synthetic architecture preparation')
        (self.root/'zephyr/arch/arm/core/cortex_a_r/reset.S').write_text(
            'synthetic architecture reset')
        (self.root/'zephyr/drivers/interrupt_controller').mkdir(parents=True)
        (self.root/'zephyr/drivers/interrupt_controller/intc_vim.c').write_text(
            'synthetic VIM interrupt initialization')
        (self.root/'zephyr/drivers/pinctrl').mkdir(parents=True)
        (self.root/'zephyr/drivers/pinctrl/pinctrl_ti_k3.c').write_text(
            'synthetic TI K3 pinctrl initialization')
        (self.root/'zephyr/arch/arm/core/cortex_a_r/irq_init.c').write_text(
            'synthetic ARM IRQ initialization')
        (self.root/'zephyr/soc/ti/k3/common/cortex_r').mkdir(parents=True)
        (self.root/'zephyr/soc/ti/k3/common/cortex_r/soc.c').write_text(
            'synthetic SoC IRQ initialization')
        for name in ('tools/boot/multicore-elf/genimage_am64x.py',
                     'source/security/security_common/tools/boot/signing/appimage_x509_cert_gen.py',
                     'source/security/security_common/tools/boot/signing/app_degenerateKey.pem',
                     'tools/boot/sbl_prebuilt/am243x-lp/sbl_uart_uniflash.release.hs_fs.tiimage',
                     'tools/boot/uart_uniflash.py'):
            path = sdk/name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'synthetic SDK file')
        self.p = local.parameters(self.root)
        self.p['boot'].mkdir(parents=True)
        self.p['elf'].parent.mkdir(parents=True)
        self.cache()
        self.images()
        local.write_cfg(self.p)
        self.ready()

    def cache(self, **updates):
        values = {'ZEPHYR_BASE': str(self.p['source']),
                  'APPLICATION_SOURCE_DIR': str(self.p['app']),
                  'CMAKE_HOME_DIRECTORY': str(self.p['app']), 'BOARD': local.BOARD,
                  'ZEPHYR_SDK_INSTALL_DIR': str(self.p['zephyr_sdk'])}
        values.update(updates)
        (self.p['build']/'CMakeCache.txt').write_text(
            ''.join(f'{k}:STRING={v}\n' for k, v in values.items()))

    def images(self, core=4, message=b'Hello World! synthetic'):
        loads = [(1, 0, bytes(60), 60), (1, 0x70080000, message, max(64, len(message)))]
        self.p['elf'].write_bytes(elf_file(loads))
        notes = note(b'Segment Map ', 0xbbbb7777, bytes([core, core]))
        notes += note(b'Entry Points ', 0xcccc9999, struct.pack('<II', core, 0))
        data = elf_file([(4, 0, notes, len(notes))] + loads)
        self.p['mcelf'].write_bytes(data)
        # Synthetic DER envelope, not an authentic certificate.
        self.p['signed'].write_bytes(b'\x30\x03abc' + data)

    def ready(self):
        sitara.atomic_json(self.p['verification'], {'status': 'ready',
                           'app': self.p['app_name'], 'hashes': local.snapshots(self.p)})

    def checking(self):
        with patch.object(sitara, 'dependencies'), patch('sys.stdout', new_callable=io.StringIO):
            return local.check(self.p)

    def test_paths_use_local_source_and_fixed_build(self):
        self.assertEqual(self.p['source'], self.root/'zephyr')
        self.assertEqual(self.p['build'], self.root/'apps/hello_world/build')
        self.assertEqual(self.p['python'], self.root/'venv/bin/python')

    def test_settings_require_absolute_paths(self):
        value = json.loads((self.root/local.SETTINGS).read_text())
        value['ti_sdk'] = 'relative-sdk'
        (self.root/local.SETTINGS).write_text(json.dumps(value))
        with self.assertRaises(sitara.Problem):
            local.parameters(self.root)

    def test_missing_module_is_not_downloaded(self):
        value = json.loads((self.root/local.SETTINGS).read_text())
        value['modules'] = [str(self.root/'missing')]
        (self.root/local.SETTINGS).write_text(json.dumps(value))
        with self.assertRaises(sitara.Problem):
            local.parameters(self.root)

    def test_cfg_quotes_absolute_paths_with_spaces(self):
        lines = local.cfg_content(self.p).splitlines()[1:]
        self.assertEqual(shlex.split(lines[0]), ['--flash-writer='+str(self.p['writer'])])
        self.assertEqual(shlex.split(lines[1])[0], '--file='+str(self.p['signed']))
        self.assertIn('--operation=flashverify', lines[2])
        self.assertNotIn('flash-offset=0x0', '\n'.join(lines))
        self.assertNotIn('$', '\n'.join(lines))

    def test_valid_image_and_check_never_touch_uart(self):
        with patch.object(sitara, 'select_port', side_effect=AssertionError('UART forbidden')):
            self.checking()

    def test_foreign_cache_rejected(self):
        self.cache(ZEPHYR_BASE='/old/workspace/zephyr')
        with self.assertRaises(sitara.Problem):
            self.checking()

    def test_partial_local_configure_can_be_resumed(self):
        (self.p['build']/'CMakeCache.txt').write_text(
            'CMAKE_HOME_DIRECTORY:INTERNAL='+str(self.p['app'])+'\n')
        local.verify_cache(self.p, required=False)
        with self.assertRaises(sitara.Problem):
            local.verify_cache(self.p)

    def test_wrong_board_rejected(self):
        self.cache(BOARD='other_board')
        with self.assertRaises(sitara.Problem):
            self.checking()

    def test_changed_signed_image_rejected(self):
        with self.p['signed'].open('ab') as stream:
            stream.write(b'changed')
        with self.assertRaises(sitara.Problem):
            self.checking()

    def test_changed_main_rejected(self):
        (self.p['app']/'src/main.c').write_text('changed source')
        with self.assertRaises(sitara.Problem):
            self.checking()

    def test_changed_settings_rejected(self):
        with (self.root/local.SETTINGS).open('a') as stream:
            stream.write('\n')
        with self.assertRaises(sitara.Problem):
            self.checking()

    def test_changed_cfg_rejected(self):
        self.p['cfg'].write_text('--file=/wrong/image\n')
        with self.assertRaises(sitara.Problem):
            self.checking()

    def test_cfg_symlink_rejected(self):
        self.p['cfg'].unlink()
        self.p['cfg'].symlink_to(self.root/'elsewhere')
        with self.assertRaises(sitara.Problem):
            local.write_cfg(self.p)

    def test_wrong_core_rejected(self):
        self.images(core=5)
        with self.assertRaises(sitara.Problem):
            local.image_integrity(self.p)

    def test_signed_raw_elf_is_not_accepted_as_mcelf(self):
        self.p['signed'].write_bytes(b'\x30\x03abc' + self.p['elf'].read_bytes())
        with self.assertRaises(sitara.Problem):
            local.image_integrity(self.p)

    def test_changed_loadable_code_rejected(self):
        self.p['mcelf'].write_bytes(self.p['mcelf'].read_bytes().replace(b'Hello World!', b'Wrong World!'))
        with self.assertRaises(sitara.Problem):
            local.image_integrity(self.p)

    def test_malformed_certificate_rejected(self):
        self.p['signed'].write_bytes(b'not a certificate')
        with self.assertRaises(sitara.Problem):
            local.image_integrity(self.p)

    def test_ordinary_elf_is_not_accepted_as_mcelf(self):
        self.p['mcelf'].write_bytes(self.p['elf'].read_bytes())
        with self.assertRaises(sitara.Problem):
            local.image_integrity(self.p)

    def test_oversized_image_rejected(self):
        data = self.p['mcelf'].read_bytes() + bytes(0x80000)
        self.p['mcelf'].write_bytes(data)
        self.p['signed'].write_bytes(b'\x30\x03abc' + data)
        with self.assertRaises(sitara.Problem):
            local.image_integrity(self.p)

    def test_incomplete_build_not_flashable(self):
        sitara.atomic_json(self.p['verification'], {'status': 'building'})
        with self.assertRaises(sitara.Problem):
            self.checking()

    def test_failed_build_invalidates_previous_receipt(self):
        def failure(command, **kwargs):
            raise subprocess.CalledProcessError(1, command)
        with self.assertRaises(subprocess.CalledProcessError):
            local.build(self.p, runner=failure)
        self.assertEqual(json.loads(self.p['verification'].read_text())['status'], 'building')

    def test_build_commands_explicitly_use_local_source(self):
        calls = []
        def runner(command, **kwargs):
            calls.append((command, kwargs))
        with patch.object(sitara, 'select_port', side_effect=AssertionError('UART forbidden')):
            with patch('sys.stdout', new_callable=io.StringIO):
                local.build(self.p, runner=runner)
        self.assertEqual(len(calls), 3)
        self.assertEqual(calls[0][0][1:4], ['-m', 'west', 'build'])
        self.assertIn('-DZEPHYR_BASE='+str(self.p['source']), calls[0][0])
        self.assertIn('-DPython3_EXECUTABLE='+str(self.p['python']), calls[0][0])
        self.assertEqual(calls[0][1]['env']['ZEPHYR_BASE'], str(self.p['source']))
        self.assertIn('--core-img=4:'+str(self.p['elf']), calls[1][0])
        self.assertEqual(json.loads(self.p['verification'].read_text())['status'], 'ready')

    def test_old_exports_do_not_select_old_source_or_image(self):
        calls = []
        with patch.dict('os.environ', {'ZEPHYR_BASE': '/old/source',
                                      'ZEPHYR_SDK_INSTALL_DIR': '/old/sdk',
                                      'ZEPHYR_MODULES': '/old/modules',
                                      'BOARD': 'old_board', 'CONF_FILE': '/old/conf',
                                      'APP_IMAGE': '/old/image'}):
            with patch('sys.stdout', new_callable=io.StringIO):
                local.build(self.p, runner=lambda command, **kw: calls.append((command, kw)))
        self.assertEqual(calls[0][1]['env']['ZEPHYR_BASE'], str(self.p['source']))
        self.assertNotIn('BOARD', calls[0][1]['env'])
        self.assertNotIn('ZEPHYR_MODULES', calls[0][1]['env'])
        self.assertNotIn('CONF_FILE', calls[0][1]['env'])
        self.assertIn('--bin', calls[2][0])
        self.assertIn(str(self.p['mcelf']), calls[2][0])

    def test_flash_only_calls_mocked_vendor_with_expected_cfg(self):
        calls = []
        with patch.object(sitara, 'dependencies'), patch('sys.stdout', new_callable=io.StringIO):
            local.flash(self.p, '/dev/fake', selector=lambda port: port,
                        vendor=lambda command, cwd: calls.append((command, cwd)))
        self.assertEqual(calls[0][0][-3:], ['-p', '/dev/fake', '--cfg='+str(self.p['cfg'])])
        self.assertEqual(calls[0][1], self.p['build'])

    def test_old_uncertain_receipt_does_not_block_explicit_retry(self):
        sitara.atomic_json(self.p['build']/'receipt.json', {'status': 'started'})
        calls = []
        with patch.object(sitara, 'dependencies'), patch('sys.stdout', new_callable=io.StringIO):
            local.flash(self.p, '/dev/fake', selector=lambda port: port,
                        vendor=lambda cmd, cwd: calls.append((cmd, cwd)))
        self.assertEqual(len(calls), 1)

    def test_change_while_selecting_port_blocks_vendor(self):
        def select(port):
            self.p['signed'].write_bytes(b'changed during selection')
            return port
        with patch.object(sitara, 'dependencies'), patch('sys.stdout', new_callable=io.StringIO):
            with self.assertRaises(sitara.Problem):
                local.flash(self.p, '/dev/fake', selector=select,
                            vendor=lambda *args: self.fail('must not flash'))


if __name__ == '__main__':
    unittest.main()
