import os
import shutil
import sys
import threading
import unittest
from unittest.mock import patch

from install_commands import COMMANDS, install_args
from install_terminal import InstallTerminalRunner


class InstallCommandTests(unittest.TestCase):
    def test_wrong_platform_rejected(self):
        with patch('install_commands.platform.system', return_value='Windows'):
            with self.assertRaises(ValueError):
                install_args('Linux')

    def test_windows_fixed_command(self):
        with patch('install_commands.platform.system', return_value='Windows'), \
             patch('install_commands.shutil.which', return_value='powershell.exe'):
            args = install_args('Windows')
        self.assertIn(COMMANDS['Windows'], args[-1])
        self.assertIn('Env:OLLAMA_UNINSTALL', args[-1])
        self.assertIn('exit 1', args[-1])
        self.assertEqual(args[0], 'powershell.exe')

    def test_unix_pipefail(self):
        for system in ('Linux', 'Darwin'):
            with patch('install_commands.platform.system', return_value=system), \
                 patch('install_commands.shutil.which', side_effect=lambda name: '/usr/bin/' + name):
                self.assertEqual(install_args(system), ['/usr/bin/bash', '-o', 'pipefail', '-c', COMMANDS[system]])

    def test_missing_shell(self):
        with patch('install_commands.platform.system', return_value='Windows'), \
             patch('install_commands.shutil.which', return_value=None):
            with self.assertRaises(ValueError):
                install_args('Windows')

    @unittest.skipUnless(os.name == 'nt' and shutil.which('powershell.exe'), 'Windows PowerShell only')
    def test_real_powershell_output_and_input_without_install(self):
        runner = InstallTerminalRunner()
        output, results = [], []
        ready = threading.Event()
        def receive(chunk):
            output.append(chunk)
            if 'READY' in ''.join(output):
                ready.set()
        # Use the same invocation/encoding wrapper, substituting harmless I/O.
        args = install_args('Windows')
        args[-1] = args[-1].replace(COMMANDS['Windows'], "Write-Output 'READY'; $v=[Console]::ReadLine(); Write-Output $v")
        thread = threading.Thread(target=lambda: results.append(runner.run(args, receive)), daemon=True)
        thread.start()
        try:
            self.assertTrue(ready.wait(5))
            runner.send('terminal-test')
            thread.join(5)
            self.assertFalse(thread.is_alive())
            self.assertEqual(results, [0])
            self.assertIn('terminal-test', ''.join(output))
        finally:
            runner.stop()
            thread.join(3)

    def test_stop_running_installer_transport(self):
        runner = InstallTerminalRunner()
        ready = threading.Event()
        thread = threading.Thread(target=lambda: runner.run(
            [sys.executable, '-u', '-c', "import time; print('READY'); time.sleep(60)"],
            lambda chunk: ready.set()), daemon=True)
        thread.start()
        try:
            self.assertTrue(ready.wait(5))
        finally:
            runner.stop()
            thread.join(5)
        self.assertFalse(thread.is_alive())

    def test_stop_before_launch(self):
        runner = InstallTerminalRunner()
        runner.stop()
        self.assertEqual(runner.run(['not-an-executable'], lambda _: None), -1)
