import json
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from unittest.mock import Mock, patch
from CHAT import serve_ollama_say as bridge


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.client = Mock()
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), bridge.Handler)
        self.base = 'http://127.0.0.1:' + str(self.server.server_port)
        for patcher in (patch.object(bridge, 'PORT', self.server.server_port),
                        patch.object(bridge, 'selected_client', return_value=self.client)):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(2)

    def request(self, path, data=None, method=None, origin='https://mdproviewer.vercel.app'):
        body = None if data is None else json.dumps(data).encode()
        return self.opener.open(urllib.request.Request(self.base + path, body, method=method,
            headers={'Origin': origin, 'Content-Type': 'application/json',
                     'Access-Control-Request-Private-Network': 'true'}), timeout=4)

    def test_preflight_allows_mdpro_and_rejects_untrusted_origin(self):
        with self.request('/api/chat', method='OPTIONS') as response:
            self.assertEqual(response.status, 204)
            self.assertEqual(response.headers['Access-Control-Allow-Origin'], 'https://mdproviewer.vercel.app')
            self.assertEqual(response.headers['Access-Control-Allow-Private-Network'], 'true')
        with self.assertRaises(urllib.error.HTTPError) as error:
            self.request('/api/chat', method='OPTIONS', origin='https://evil.example')
        self.assertEqual(error.exception.code, 403)

    def test_nonstream_preload_and_show_match_mdpro_contract(self):
        self.client.post.return_value = {'done': True, 'model': 'small'}
        with self.request('/api/generate', {'model': 'small', 'prompt': '', 'stream': False,
                'options': {'num_ctx': 8192}, 'keep_alive': '10m'}) as response:
            self.assertTrue(json.load(response)['done'])
            self.assertIn('application/json', response.headers['Content-Type'])
        path, payload = self.client.post.call_args.args
        self.assertEqual(path, '/api/generate')
        self.assertEqual(payload['options']['num_ctx'], 8192)
        self.assertEqual(payload['keep_alive'], '10m')
        with self.request('/api/show', {'model': 'small'}) as response:
            self.assertEqual(response.status, 200)
        self.client.post.assert_called_with('/api/show', {'model': 'small'})

    def test_stream_preserves_unicode_and_reports_midstream_failure(self):
        def stream(*args):
            yield {'message': {'content': '한글'}}
            raise RuntimeError('upstream disconnected')
        self.client.stream.side_effect = stream
        with self.request('/ollama/api/chat', {'model': 'small', 'stream': True}) as response:
            items = [json.loads(line) for line in response]
            self.assertEqual(items[0]['message']['content'], '한글')
            self.assertEqual(items[1]['error'], 'upstream disconnected')

    def test_first_failure_is_502_and_mutation_routes_are_unavailable(self):
        self.client.stream.side_effect = RuntimeError('model unavailable')
        with self.assertRaises(urllib.error.HTTPError) as error:
            self.request('/api/chat', {'model': 'small'})
        self.assertEqual(error.exception.code, 502)
        with self.assertRaises(urllib.error.HTTPError) as error:
            self.request('/api/delete', {'model': 'small'})
        self.assertEqual(error.exception.code, 404)
