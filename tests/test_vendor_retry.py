"""Manual retries without persisted attempts. All processes/ports are mocked."""
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import sitara


DONE = 'All commands from config file are executed !!!\n'


class FakeProcess:
    def __init__(self, output=DONE, code=0):
        self.stdout = io.StringIO(output)
        self.code = code

    def wait(self):
        return self.code


class VendorRetryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)

    def run_fake(self, output=DONE, code=0):
        calls = []
        def factory(command, **kwargs):
            calls.append((command, kwargs))
            return FakeProcess(output, code)
        with patch('sys.stdout', new_callable=io.StringIO):
            sitara.run_vendor(['fake-tool'], self.work, factory=factory)
        return calls

    def test_success_creates_no_receipt_log_or_archive(self):
        self.assertEqual(len(self.run_fake()), 1)
        self.assertEqual(list(self.work.iterdir()), [])

    def test_failure_creates_no_history_and_next_invocation_can_succeed(self):
        with self.assertRaises(sitara.Problem):
            self.run_fake('[ERROR] XMODEM failed\n', 1)
        self.assertEqual(list(self.work.iterdir()), [])
        self.assertEqual(len(self.run_fake()), 1)
        self.assertEqual(list(self.work.iterdir()), [])

    def test_legacy_files_are_ignored_and_preserved_unchanged(self):
        receipt = self.work/'receipt.json'
        log = self.work/'operation.log'
        receipt.write_text('{"status":"started"}\n')
        log.write_text('old failed output\n')
        before = {p.name: p.read_bytes() for p in self.work.iterdir()}
        self.run_fake()
        self.assertEqual({p.name: p.read_bytes() for p in self.work.iterdir()}, before)

    def test_invalid_legacy_receipt_does_not_block_retry(self):
        (self.work/'receipt.json').write_text('old truncated JSON')
        self.assertEqual(len(self.run_fake()), 1)

    def test_zero_exit_without_terminal_marker_is_not_success(self):
        with self.assertRaises(sitara.Problem):
            self.run_fake('Sending firmware...\n')
        self.assertEqual(list(self.work.iterdir()), [])

    def test_error_with_terminal_marker_is_not_success(self):
        with self.assertRaises(sitara.Problem):
            self.run_fake('[ERROR] flash failed\n'+DONE)

    def test_failure_never_starts_an_automatic_second_attempt(self):
        calls = []
        def factory(*args, **kwargs):
            calls.append(args)
            return FakeProcess('[ERROR] XMODEM failed\n', 1)
        with patch('sys.stdout', new_callable=io.StringIO):
            with self.assertRaises(sitara.Problem):
                sitara.run_vendor(['fake-tool'], self.work, factory=factory)
        self.assertEqual(len(calls), 1)

    def test_generic_flash_also_ignores_old_failed_receipt(self):
        (self.work/'receipt.json').write_text('{"status":"started"}')
        state = {'mode': 'ospi', 'tool': {'path': '/fake/tool'}, 'cfg': '/fake/cfg'}
        calls = []
        with patch.object(sitara, 'prepared', return_value=({}, self.work, state)), \
                patch.object(sitara, 'dependencies'), patch('sys.stdout', new_callable=io.StringIO):
            sitara.execute(self.work, 'flash', '/dev/fake', selector=lambda port: port,
                           runner=lambda cmd, cwd: calls.append((cmd, cwd)))
        self.assertEqual(len(calls), 1)

    def test_project_lock_still_blocks_simultaneous_operations(self):
        with sitara.operation_lock(self.work):
            with self.assertRaises(sitara.Problem):
                with sitara.operation_lock(self.work):
                    self.fail('Concurrent operation must not start')


if __name__ == '__main__':
    unittest.main()
