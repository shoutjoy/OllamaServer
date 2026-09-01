import unittest
from unittest.mock import patch
from types import SimpleNamespace
import serve_ollama_say as app


class LocalBridgeTests(unittest.TestCase):
    @patch.object(app.subprocess, 'run')
    @patch.object(app.shutil, 'which', return_value='ollama.exe')
    def test_all_models_without_filtering(self, which, run):
        run.return_value = SimpleNamespace(returncode=0, stdout='NAME ID SIZE MODIFIED\na:latest 1 1GB today\nembed:latest 2 2GB today\n', stderr='')
        self.assertEqual(app.list_models(), {'models': [{'name': 'a:latest'}, {'name': 'embed:latest'}]})
        self.assertEqual(run.call_args.args[0], ['ollama.exe', 'list'])

    @patch.object(app.subprocess, 'run')
    @patch.object(app.shutil, 'which', return_value='ollama.exe')
    def test_command_error_is_reported(self, which, run):
        run.return_value = SimpleNamespace(returncode=1, stdout='', stderr='server unavailable')
        with self.assertRaisesRegex(RuntimeError, 'server unavailable'):
            app.list_models()

    def test_loopback_origin_only(self):
        handler = object.__new__(app.Handler)
        handler.headers = {'Host': '127.0.0.1:8767', 'Origin': 'https://untrusted.example'}
        self.assertFalse(handler.allowed())
        handler.headers['Origin'] = 'http://127.0.0.1:8767'
        self.assertTrue(handler.allowed())
        handler.headers['Host'] = 'untrusted.example:8767'
        self.assertFalse(handler.allowed())


if __name__ == '__main__':
    unittest.main()
