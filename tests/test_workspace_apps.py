"""Workspace/app contract tests. No downloads, installs, serial or board access."""
import configparser
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import test_zephyr_local as fixtures

local = fixtures.local
sitara = fixtures.sitara
PROJECT = Path(__file__).resolve().parents[1]


class AppWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.LocalZephyrTests(methodName='runTest')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root, self.p = self.fixture.root, self.fixture.p
        self.ready = self.fixture.ready
        self.checking = self.fixture.checking

    def test_compile_only_runs_west_and_cannot_flash_old_package(self):
        calls = []
        with patch('sys.stdout', new_callable=io.StringIO):
            local.compile_app(self.p, runner=lambda cmd, **kw: calls.append((cmd, kw)))
        self.assertEqual(len(calls), 1)
        command, options = calls[0]
        self.assertEqual(command[:4], [str(self.p['python']), '-m', 'west', 'build'])
        self.assertIn('--pristine=never', command)
        self.assertEqual(options['cwd'], self.root)
        self.assertEqual(json.loads(self.p['compiled'].read_text())['status'], 'compiled')
        self.assertEqual(json.loads(self.p['verification'].read_text())['status'], 'building')
        with self.assertRaises(sitara.Problem):
            self.checking()

    def test_package_requires_a_successful_compile_record(self):
        with self.assertRaises(FileNotFoundError):
            local.package_app(self.p, runner=lambda *a, **kw: self.fail('Must not run tools'))

    def test_package_rejects_sources_edited_after_compile(self):
        with patch('sys.stdout', new_callable=io.StringIO):
            local.compile_app(self.p, runner=lambda *a, **kw: None)
        (self.p['app']/'src/main.c').write_text('new source')
        with self.assertRaises(sitara.Problem):
            local.package_app(self.p, runner=lambda *a, **kw: self.fail('Must not run tools'))

    def test_package_rejects_an_elf_from_another_build(self):
        with patch('sys.stdout', new_callable=io.StringIO):
            local.compile_app(self.p, runner=lambda *a, **kw: None)
        self.p['elf'].write_bytes(b'other ELF')
        with self.assertRaises(sitara.Problem):
            local.package_app(self.p, runner=lambda *a, **kw: self.fail('Must not run tools'))

    def test_build_inputs_changed_during_compile_are_rejected(self):
        def mutate(*a, **kw):
            (self.p['app']/'prj.conf').write_text('changed while compiling')
        with patch('sys.stdout', new_callable=io.StringIO), self.assertRaises(sitara.Problem):
            local.compile_app(self.p, runner=mutate)

    def test_changed_app_header_invalidates_prepared_image(self):
        header = self.p['app']/'src/driver.h'
        header.write_text('first')
        self.ready()
        header.write_text('second')
        with self.assertRaises(sitara.Problem):
            self.checking()

    def test_build_outputs_are_not_source_inputs(self):
        before = local.source_hashes(self.p)
        (self.p['build']/'generated.c').write_text('generated')
        self.assertEqual(local.source_hashes(self.p), before)

    def test_serial_requires_an_explicit_authorized_visible_port(self):
        with self.assertRaises(sitara.Problem):
            local.serial_console(self.p, '', runner=lambda *a, **kw: self.fail('UART forbidden'))
        with patch.object(sitara, 'enumerate_ports', return_value=[]), self.assertRaises(sitara.Problem):
            local.serial_console(self.p, '/dev/not-present', runner=lambda *a, **kw: self.fail('UART forbidden'))

    def test_serial_does_not_use_flash_probe_or_auto_select(self):
        calls = []
        with patch.object(sitara, 'enumerate_ports', return_value=[{'device': '/dev/fake', 'eligible': True}]), \
                patch.object(sitara, 'select_port', side_effect=AssertionError('ROM probing forbidden')), \
                patch('sys.stdout', new_callable=io.StringIO):
            local.serial_console(self.p, '/dev/fake', runner=lambda cmd, **kw: calls.append(cmd))
        self.assertEqual(calls[0][1:3], ['-m', 'serial.tools.miniterm'])
        self.assertEqual(calls[0][-2:], ['/dev/fake', '115200'])


class WorkspaceLayoutTests(unittest.TestCase):
    def test_justfiles_select_distinct_apps_without_implicit_flashing(self):
        for name in ('hello_world', 'hola_zephyr'):
            text = (PROJECT/'apps'/name/'justfile').read_text()
            self.assertIn('build --app '+name, text)
            self.assertIn('package --app '+name, text)
            self.assertIn('flash port:', text)
            self.assertNotIn('rm -rf', text)

    def test_active_manifest_is_application_owned(self):
        config = configparser.ConfigParser()
        config.read(PROJECT/'.west/config')
        self.assertEqual(config['manifest']['path'], 'apps')
        self.assertEqual(config['manifest']['file'], 'west.yml')

    def test_manifest_only_uses_pinned_dependency_revisions(self):
        import yaml
        manifest = yaml.safe_load((PROJECT/'apps/west.yml').read_text())['manifest']
        zephyr = next(p for p in manifest['projects'] if p['name'] == 'zephyr')
        self.assertEqual(zephyr['west-commands'], 'scripts/west-commands.yml')
        names = set()
        for project in manifest['projects']:
            self.assertRegex(project['revision'], r'^[0-9a-f]{40}$')
            self.assertNotIn(project['name'], names)
            self.assertFalse(Path(project['path']).is_absolute())
            names.add(project['name'])
        self.assertTrue({'zephyr', 'cmsis', 'cmsis_6', 'hal_ti', 'mcupsdk-core', 'mcupsdk-sysconfig'} <= names)


if __name__ == '__main__':
    unittest.main()
