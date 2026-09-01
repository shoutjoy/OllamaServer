import io
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from app import App
from installer_download import DownloadCancelled, download_installer


class InstallerTests(unittest.TestCase):
    def transfer(self, cancel_at=None, length=6):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'OllamaSetup.exe'
            cancel = threading.Event()
            response = io.BytesIO(b'abcdef')
            response.headers = {'Content-Length': str(length)}
            def progress(count, total):
                if cancel_at:
                    cancel.set()
            with patch('installer_download.open_url', return_value=response):
                if cancel_at:
                    with self.assertRaises(DownloadCancelled):
                        download_installer(target, cancel, progress)
                    self.assertFalse(target.exists())
                elif length != 6:
                    with self.assertRaises(RuntimeError):
                        download_installer(target, cancel, progress)
                    self.assertFalse(target.exists())
                else:
                    download_installer(target, cancel, progress)
                    self.assertEqual(target.read_bytes(), b'abcdef')
            self.assertFalse(target.with_suffix('.download').exists())
            self.assertTrue(response.closed)

    def test_complete(self):
        self.transfer()

    def test_cancel_cleans_partial(self):
        self.transfer(cancel_at=True)

    def test_incomplete_cleans_partial(self):
        self.transfer(length=10)

    def test_cancel_before_connect(self):
        cancel = threading.Event()
        cancel.set()
        with tempfile.TemporaryDirectory() as directory, patch('installer_download.open_url') as connect:
            with self.assertRaises(DownloadCancelled):
                download_installer(Path(directory) / 'OllamaSetup.exe', cancel, Mock())
            connect.assert_not_called()

    def test_stop_does_not_launch(self):
        app = Mock(closed=False, installer_cancel=threading.Event())
        App.stop_installer_download(app)
        with patch('app.subprocess.Popen') as launch:
            App.launch_installer(app, Path('OllamaSetup.exe'), [])
            launch.assert_not_called()

    def test_launch_disables_stop(self):
        app = Mock(closed=False, installer_cancel=threading.Event())
        with patch('app.subprocess.Popen') as launch:
            processes = []
            App.launch_installer(app, Path('OllamaSetup.exe'), processes)
            self.assertEqual(processes, [launch.return_value])
            app.stop_download_button.configure.assert_called_once_with(state='disabled')

    def test_open_download_folder(self):
        with tempfile.TemporaryDirectory() as directory:
            app = Mock(installer_path=Path(directory) / 'downloads' / 'OllamaSetup.exe')
            with patch('app.os.startfile', create=True) as opener:
                App.open_download_folder(app)
                opener.assert_called_once_with(str(app.installer_path.parent))
                self.assertTrue(app.installer_path.parent.is_dir())
