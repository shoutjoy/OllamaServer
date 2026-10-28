import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from app import App
from windows_desktop import APP_NAME, RUN_KEY, set_startup


@unittest.skipUnless(os.name == 'nt', 'Windows integration')
class DesktopTests(unittest.TestCase):
    def test_frozen_startup_quotes_executable_and_passes_startup_flag(self):
        import winreg
        with patch('winreg.CreateKey') as create, patch('winreg.SetValueEx') as write, \
                patch.object(sys, 'frozen', True, create=True), \
                patch.object(sys, 'executable', r'C:\Program Files\Ollama Desk.exe'):
            set_startup(True)
            create.assert_called_once_with(winreg.HKEY_CURRENT_USER, RUN_KEY)
            write.assert_called_once_with(create.return_value.__enter__.return_value,
                                          APP_NAME, 0, winreg.REG_SZ,
                                          '"C:\\Program Files\\Ollama Desk.exe" --startup')

    def test_source_startup_uses_absolute_script(self):
        with patch('winreg.CreateKey'), patch('winreg.SetValueEx') as write:
            set_startup(True)
            command = write.call_args.args[-1]
            self.assertIn(str(Path(__file__).resolve().parents[1] / 'app.py'), command)
            self.assertTrue(command.endswith(' --startup'))

    def test_disable_removes_only_our_entry_and_handles_absent_entry(self):
        with patch('winreg.CreateKey') as create, \
                patch('winreg.DeleteValue', side_effect=FileNotFoundError) as delete:
            set_startup(False)
            delete.assert_called_once_with(create.return_value.__enter__.return_value, APP_NAME)

    def test_close_hides_only_when_tray_is_available(self):
        app = Mock(tray_icon=object())
        app.tray_enabled.get.return_value = True
        App.hide_or_close(app)
        app.withdraw.assert_called_once()
        app.close.assert_not_called()
        app.tray_icon = None
        App.hide_or_close(app)
        app.close.assert_called_once()

    def test_setting_writer_preserves_tray_option(self):
        app = Mock()
        app.tray_enabled.get.return_value = True
        with tempfile.TemporaryDirectory() as directory, patch('app.DATA', Path(directory)):
            App.write_settings(app, {'theme': 'dark'})
            saved = json.loads((Path(directory) / 'settings.json').read_text('utf-8'))
            self.assertEqual(saved, {'theme': 'dark', 'tray_enabled': True})
