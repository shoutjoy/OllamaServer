import tempfile
import io
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import open_webui_runner as runner


class OpenWebUITests(unittest.TestCase):
    def test_install_failure_streams_output_and_reports_log(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            python = root / 'venv' / ('Scripts/python.exe' if runner.os.name == 'nt' else 'bin/python')
            python.parent.mkdir(parents=True)
            python.touch()
            process = Mock()
            process.stdout = io.StringIO('download failed\n')
            process.wait.return_value = 1
            notify = Mock()
            with patch.object(runner, 'find_uv', return_value='uv'), patch.object(runner.subprocess, 'Popen', return_value=process):
                with self.assertRaisesRegex(RuntimeError, 'install.log'):
                    runner.install(root, notify)
            notify.assert_any_call('download failed')
            self.assertIn('download failed', (root / 'install.log').read_text('utf-8'))

    def test_existing_server_does_not_install_or_spawn(self):
        with patch.object(runner, 'ready', return_value=True), patch.object(runner, 'install') as install, patch.object(runner.subprocess, 'Popen') as spawn:
            self.assertEqual(runner.start('unused'), runner.URL)
        install.assert_not_called()
        spawn.assert_not_called()

    def test_occupied_port_is_reported_without_spawning(self):
        with patch.object(runner, 'ready', return_value=False), patch.object(runner.socket, 'create_connection'), patch.object(runner.subprocess, 'Popen') as spawn:
            with self.assertRaisesRegex(RuntimeError, '8080'):
                runner.start('unused')
        spawn.assert_not_called()

    def test_failed_process_reports_log_and_uses_local_ollama(self):
        with tempfile.TemporaryDirectory() as folder:
            executable = runner.executable(folder)
            executable.parent.mkdir(parents=True)
            executable.touch()
            process = Mock()
            process.poll.return_value = 1
            with patch.object(runner, 'ready', return_value=False), patch.object(runner.socket, 'create_connection', side_effect=OSError), patch.object(runner.subprocess, 'Popen', return_value=process) as spawn:
                with self.assertRaisesRegex(RuntimeError, 'server.log'):
                    runner.start(folder)
            args, kwargs = spawn.call_args
            self.assertIn('127.0.0.1', args[0])
            self.assertEqual(kwargs['env']['OLLAMA_BASE_URL'], 'http://127.0.0.1:11434')
            self.assertEqual(kwargs['env']['DATA_DIR'], str((Path(folder) / 'data').resolve()))
