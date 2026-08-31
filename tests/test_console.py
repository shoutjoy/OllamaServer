import sys
import threading
import unittest

from console_runner import ConsoleRunner


class ConsoleTests(unittest.TestCase):
    def test_real_process_input_and_unicode_output(self):
        runner = ConsoleRunner()
        ready = threading.Event()
        output = []
        result = []
        def receive(chunk):
            output.append(chunk)
            if 'READY' in ''.join(output):
                ready.set()
        args = [sys.executable, '-u', '-c',
                "import sys; sys.stdout.reconfigure(encoding='utf-8'); sys.stdin.reconfigure(encoding='utf-8'); print('READY'); print(input())"]
        thread = threading.Thread(target=lambda: result.append(runner.run(args, receive)), daemon=True)
        thread.start()
        try:
            self.assertTrue(ready.wait(5))
            runner.send('한글 입력 테스트')
            thread.join(5)
            self.assertFalse(thread.is_alive())
            self.assertEqual(result, [0])
            self.assertIn('한글 입력 테스트', ''.join(output))
        finally:
            runner.stop()
            thread.join(3)

    def test_stop_running_process(self):
        runner = ConsoleRunner()
        ready = threading.Event()
        thread = threading.Thread(target=lambda: runner.run(
            [sys.executable, '-u', '-c', "import time; print('READY'); time.sleep(60)"],
            lambda chunk: ready.set()), daemon=True)
        thread.start()
        try:
            self.assertTrue(ready.wait(5))
        finally:
            runner.stop()
            thread.join(5)
        self.assertFalse(thread.is_alive())
        self.assertIsNone(runner.process)

    def test_stop_before_process_creation(self):
        runner = ConsoleRunner()
        runner.stop()
        self.assertEqual(runner.run(['does-not-exist'], lambda _: None), -1)
