import unittest
from types import SimpleNamespace
from unittest.mock import patch

from bashbot.command.exec import ExecCommand
from bashbot.core.settings import settings
from bashbot.terminal.terminal import Terminal, TerminalStartupError


class RuntimeGuardTests(unittest.TestCase):
    def test_terminal_open_reports_missing_forkpty(self):
        fake_os = SimpleNamespace(path=SimpleNamespace(exists=lambda _: True))
        terminal = Terminal('test', sh_path='/bin/bash')

        with patch('bashbot.terminal.terminal.os', fake_os):
            with self.assertRaisesRegex(TerminalStartupError, 'forkpty'):
                terminal.open()

    def test_exec_reports_missing_shell(self):
        singleton = settings()
        original_config = singleton.config
        singleton.config = {
            'terminal': {
                'shell_path': 'definitely-not-a-real-shell',
                'exec_timeout': 1,
                'user': {
                    'login_as_other_user': False,
                },
            },
        }

        try:
            output = ExecCommand._execute('echo hello')
        finally:
            singleton.config = original_config

        self.assertIn('Shell path does not exist', output)

    def test_exec_formats_empty_and_failed_output(self):
        self.assertEqual(ExecCommand._format_result('', 0), '(no output)')

        output = ExecCommand._format_result('problem', 7)

        self.assertIn('problem', output)
        self.assertIn('Command exited with status 7', output)

    def test_exec_formats_timeout_output(self):
        output = ExecCommand._format_result('partial', None, timed_out_after=3)

        self.assertIn('partial', output)
        self.assertIn('Command timed out after 3 seconds', output)

    def test_terminal_close_without_process_is_safe(self):
        terminal = Terminal('test', sh_path='/bin/bash')

        terminal.close()

        self.assertEqual(terminal.state.name, 'CLOSED')


if __name__ == '__main__':
    unittest.main()
