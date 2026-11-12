import io
import unittest
from unittest.mock import patch
from core import Client

CRASH = RuntimeError('HTTP 500: Gemma4Assistant requires ctx_other: error loading model: vector')


class RecoveryTests(unittest.TestCase):
    def test_post_recovers_once_and_future_calls_preserve_safe_setting(self):
        client = Client()
        request = {'model': 'gemma4:e4b', 'options': {'num_ctx': 4096}}
        with patch('core.open_url', side_effect=[CRASH, io.BytesIO(b'{"done":true}'), io.BytesIO(b'{"done":true}')]) as connect:
            client.post('/api/generate', request)
            client.post('/api/generate', request)
            for call in connect.call_args_list[1:]:
                self.assertEqual(call.args[1]['options'], {'num_ctx': 4096, 'draft_num_predict': 0})
        self.assertEqual(request['options'], {'num_ctx': 4096})

    def test_stream_recovers_before_content_only(self):
        client = Client()
        request = {'model': 'gemma4:e4b', 'stream': True}
        with patch('core.open_url', side_effect=[CRASH, io.BytesIO(b'{"message":{"content":"OK"},"done":true}\n')]) as connect:
            self.assertEqual(list(client.stream('/api/chat', request))[0]['message']['content'], 'OK')
            self.assertEqual(connect.call_count, 2)
        client = Client()
        body = b'{"message":{"content":"partial"}}\n' + ('{"error":"' + str(CRASH) + '"}\n').encode()
        with patch('core.open_url', return_value=io.BytesIO(body)) as connect:
            with self.assertRaises(RuntimeError):
                list(client.stream('/api/chat', request))
            self.assertEqual(connect.call_count, 1)

    def test_unrelated_failure_and_failed_retry_stop(self):
        for error in (RuntimeError('out of memory'), CRASH):
            with self.subTest(error=error), patch('core.open_url', side_effect=error) as connect:
                with self.assertRaises(RuntimeError):
                    Client().post('/api/generate', {'model': 'gemma4:e4b'})
                self.assertEqual(connect.call_count, 2 if error is CRASH else 1)
