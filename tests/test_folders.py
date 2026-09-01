import os
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from app import App
from core import models_directory


class FolderTests(unittest.TestCase):
    def test_default_models_directory(self):
        with patch.dict(os.environ, {'OLLAMA_MODELS': ''}):
            self.assertEqual(models_directory(), Path.home() / '.ollama' / 'models')

    def test_custom_models_directory(self):
        with patch.dict(os.environ, {'OLLAMA_MODELS': '"C:/Custom Models"'}):
            self.assertEqual(models_directory(), Path('C:/Custom Models').resolve())

    def test_open_install_folder(self):
        app = Mock()
        with patch('app.find_ollama', return_value='C:/Ollama/ollama.exe'), \
             patch('app.Path.is_dir', return_value=True), patch('app.os.startfile', create=True) as opener:
            App.open_ollama_folder(app, 'install')
            opener.assert_called_once_with(str(Path('C:/Ollama').resolve()))

    def test_open_models_folder(self):
        app = Mock()
        with patch('app.models_directory', return_value=Path('C:/Model Files')), \
             patch('app.Path.is_dir', return_value=True), patch('app.os.startfile', create=True) as opener:
            App.open_ollama_folder(app, 'models')
            opener.assert_called_once_with(str(Path('C:/Model Files')))

    def test_missing_folder_does_not_open(self):
        with patch('app.Path.is_dir', return_value=False), \
             patch('app.messagebox.showinfo') as info, patch('app.os.startfile', create=True) as opener:
            App.open_ollama_folder(Mock(), 'models')
            info.assert_called_once()
            opener.assert_not_called()

    def test_missing_installation(self):
        with patch('app.find_ollama', return_value=None), patch('app.messagebox.showinfo') as info:
            App.open_ollama_folder(Mock(), 'install')
            info.assert_called_once()

    def test_open_failure_is_reported(self):
        with patch('app.Path.is_dir', return_value=True), \
             patch('app.os.startfile', create=True, side_effect=OSError('denied')), \
             patch('app.messagebox.showerror') as error:
            App.open_ollama_folder(Mock(), 'models')
            error.assert_called_once()
