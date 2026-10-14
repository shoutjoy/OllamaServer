import io
import json
import unittest
from unittest.mock import Mock, patch

from core import Client, BASE_URL, LEMONADE_URL, model_placement
from app import App
from CHAT import serve_ollama_say as chat
from console_runner import ConsoleRunner


class NpuTests(unittest.TestCase):
    def test_engine_routes_and_rejects_arbitrary_destinations(self):
        self.assertEqual(Client().base_url, BASE_URL)
        self.assertEqual(Client('lemonade').base_url, LEMONADE_URL)
        self.assertEqual(Client('http://evil.example').base_url, BASE_URL)
        with patch.object(chat, 'SETTINGS') as settings:
            settings.read_text.return_value = '{"engine":"lemonade"}'
            self.assertEqual(chat.selected_client().base_url, LEMONADE_URL)

    def test_npu_load_precedes_stream_and_preserves_input(self):
        client = Client('lemonade')
        request = {'model': 'qwen3-it-4b-FLM:latest', 'think': False,
                   'options': {'num_ctx': 8192, 'num_predict': 64, 'num_gpu': 0}}
        response = io.BytesIO(b'{"message":{"content":"ok"},"done":true}\n')
        with patch.object(client, 'post') as load, patch('core.open_url', return_value=response) as connect:
            self.assertTrue(list(client.stream('/api/chat', request))[-1]['done'])
            load.assert_called_once_with('/api/v1/load', {
                'model_name': 'qwen3-it-4b-FLM', 'ctx_size': 8192,
                'flm_args': '--pmode turbo', 'save_options': True})
            sent = connect.call_args.args[1]
            self.assertNotIn('think', sent)
            self.assertNotIn('num_gpu', sent['options'])
            self.assertEqual(sent['options']['num_predict'], 64)
            self.assertEqual(connect.call_args.args[0], LEMONADE_URL + '/api/chat')
        self.assertEqual(request['options']['num_gpu'], 0)

    def test_load_error_does_not_generate(self):
        client = Client('lemonade')
        with patch.object(client, 'post', side_effect=RuntimeError('NPU unavailable')), patch('core.open_url') as connect:
            with self.assertRaisesRegex(RuntimeError, 'NPU unavailable'):
                list(client.stream('/api/chat', {'model': 'qwen3-it-4b-FLM:latest'}))
            connect.assert_not_called()

    def test_ollama_request_unchanged(self):
        data = {'model': 'gemma3:1b', 'think': False, 'options': {'num_gpu': 0}}
        self.assertIs(Client().prepare_chat(data), data)

    def test_catalog_only_offers_npu_chat_models(self):
        app = Mock()
        app.client.get.return_value = {'data': [
            {'id': 'qwen-FLM', 'recipe': 'flm', 'labels': ['chat'], 'size': 3},
            {'id': 'embed-FLM', 'recipe': 'flm', 'labels': ['embeddings']},
            {'id': 'whisper-FLM', 'recipe': 'flm', 'labels': ['transcription']},
            {'id': 'qwen-GGUF', 'recipe': 'llamacpp', 'labels': ['chat']}]}
        self.assertEqual(App.npu_catalog(app, 'QWEN'), [('qwen-FLM', 'FastFlowLM · NPU · 3 GB')])

    def test_npu_start_loads_downloaded_model_without_spawning(self):
        app = Mock()
        app.client.get.side_effect = [{'version': 'test'}, {'models': [
            {'name': 'qwen3-it-4b-FLM:latest', 'details': {'family': 'flm'}}]}]
        app.selected.get.return_value = 'gemma3:1b'
        with patch('app.subprocess.Popen') as spawn:
            result = App.start_npu_server_worker(app, 'LemonadeServer.exe', {'context_length': 8192})
        spawn.assert_not_called()
        app.client.prepare_chat.assert_called_once_with({
            'model': 'qwen3-it-4b-FLM:latest', 'options': {'num_ctx': 8192}})
        self.assertIn('NPU', result)

    def test_zero_vram_is_reported_as_npu_for_flm(self):
        text = model_placement([{'name': 'qwen-FLM:latest', 'size': 0, 'size_vram': 0,
                                'details': {'family': 'flm'}}])
        self.assertIn('NPU', text)
        self.assertNotIn('CPU 배치', text)

    def test_console_host_matches_engine(self):
        runner = ConsoleRunner(LEMONADE_URL)
        process = Mock()
        process.stdout.fileno.return_value = 1
        process.wait.return_value = 0
        with patch('console_runner.subprocess.Popen', return_value=process) as spawn, patch('console_runner.os.read', return_value=b''):
            runner.run(['ollama', 'list'], lambda text: None)
        self.assertEqual(spawn.call_args.kwargs['env']['OLLAMA_HOST'], LEMONADE_URL)


if __name__ == '__main__':
    unittest.main()
