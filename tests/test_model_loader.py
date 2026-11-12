import unittest
from unittest.mock import Mock
from core import PERFORMANCE_DEFAULTS
from model_loader import run_ollama_model


class ModelLoaderTests(unittest.TestCase):
    def test_preload_uses_chat_options_without_cli_or_ps_roundtrip(self):
        client = Mock(safe_draft_models=set())
        client.post.return_value = {'done': True}
        settings = dict(PERFORMANCE_DEFAULTS, context_length=2048, num_gpu=2)
        self.assertFalse(run_ollama_model(None, client, 'small:1b', settings, Mock()))
        path, data = client.post.call_args.args
        self.assertEqual(path, '/api/generate')
        self.assertNotIn('prompt', data)
        self.assertFalse(data['stream'])
        self.assertEqual(data['options']['num_ctx'], 2048)
        self.assertEqual(data['options']['num_gpu'], 2)
        self.assertEqual(data['keep_alive'], '30m')
        client.get.assert_not_called()

    def test_incomplete_response_fails(self):
        client = Mock(safe_draft_models=set())
        client.post.return_value = {'done': False}
        with self.assertRaisesRegex(RuntimeError, '완료'):
            run_ollama_model(None, client, 'small', PERFORMANCE_DEFAULTS, Mock())

    def test_zero_keepalive_cannot_report_loaded(self):
        client = Mock()
        with self.assertRaises(ValueError):
            run_ollama_model(None, client, 'small', {'keep_alive': '0'}, Mock())
        client.post.assert_not_called()
