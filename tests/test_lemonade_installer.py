import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lemonade_installer import (LEMONADE_WINGET_ID, fastflowlm_install_args,
                                  find_lemonade_cli, lemonade_install_args)


class LemonadeInstallerTests(unittest.TestCase):
    def test_winget_command_uses_fixed_official_id(self):
        with patch('lemonade_installer.shutil.which', side_effect=lambda name: 'winget.exe' if name == 'winget.exe' else None):
            args = lemonade_install_args()
        self.assertEqual(args[:5], ['winget.exe', 'install', '--exact', '--id', LEMONADE_WINGET_ID])
        self.assertIn('--accept-package-agreements', args)

    def test_winget_is_required(self):
        with patch('lemonade_installer.shutil.which', return_value=None):
            with self.assertRaisesRegex(ValueError, 'winget'):
                lemonade_install_args()

    def test_cli_is_found_beside_server(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            server = root / 'LemonadeServer.exe'
            cli = root / 'lemonade.exe'
            server.touch()
            cli.touch()
            with patch('lemonade_installer.shutil.which', return_value=None), patch.dict(os.environ, {'LOCALAPPDATA': ''}):
                self.assertEqual(find_lemonade_cli(str(server)), str(cli))

    def test_fastflow_command_has_no_user_controlled_shell(self):
        with patch('lemonade_installer.find_lemonade_cli', return_value=r'C:\Lemonade\lemonade.exe'):
            self.assertEqual(fastflowlm_install_args(),
                             [r'C:\Lemonade\lemonade.exe', 'backends', 'install', 'flm:npu'])

    def test_fastflow_requires_lemonade(self):
        with patch('lemonade_installer.find_lemonade_cli', return_value=None):
            with self.assertRaisesRegex(ValueError, 'Lemonade CLI'):
                fastflowlm_install_args()


if __name__ == '__main__':
    unittest.main()
