import io
import threading
import unittest
from unittest.mock import patch

from core import CatalogParser, Client, fetch_tags, model_name


class CoreTests(unittest.TestCase):
    def test_catalog_ignores_navigation_and_deduplicates(self):
        parser = CatalogParser()
        parser.feed('<a href="/login">Login</a><a href="/library/gemma3"><b>gemma3</b> Fast &amp; small 1b</a>'
                    '<a href="/library/gemma3">duplicate</a><a href="/library/gemma3/tags">tags</a>')
        self.assertEqual(parser.models, [('gemma3', 'gemma3 Fast & small 1b')])

    def test_model_names_reject_shell_and_whitespace(self):
        self.assertEqual(model_name(' org/model:1b-q4 '), 'org/model:1b-q4')
        for bad in ('', 'x;whoami', '--help', 'a b', 'x\ncommand'):
            with self.assertRaises(ValueError):
                model_name(bad)

    def test_stream_progress_and_completion(self):
        stream = io.BytesIO(b'{"status":"pulling","total":100,"completed":50}\n\n{"status":"success"}\n')
        with patch('core.open_url', return_value=stream):
            items = list(Client().stream('/api/pull', {'model': 'x'}))
        self.assertEqual(items[0]['completed'], 50)
        self.assertEqual(items[-1]['status'], 'success')

    def test_stream_server_error(self):
        with patch('core.open_url', return_value=io.BytesIO(b'{"error":"model not found"}\n')):
            with self.assertRaisesRegex(RuntimeError, 'model not found'):
                list(Client().stream('/api/pull', {'model': 'x'}))

    def test_stream_cancel(self):
        cancel = threading.Event()
        cancel.set()
        with patch('core.open_url', return_value=io.BytesIO(b'{"status":"pulling"}\n')):
            with self.assertRaisesRegex(RuntimeError, '취소'):
                list(Client().stream('/api/pull', {}, cancel))

    def test_tags_filter_other_models(self):
        html = b'<a href="/library/gemma3:1b">1b</a><a href="/library/gemma3:1b">1b</a><a href="/library/other:7b">7b</a>'
        with patch('core.open_url', return_value=io.BytesIO(html)):
            self.assertEqual(fetch_tags('gemma3'), ['1b'])


if __name__ == '__main__':
    unittest.main()
