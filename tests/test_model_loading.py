import tkinter as tk
import unittest
from tkinter import ttk
from unittest.mock import Mock

from app import App


class ModelLoadingTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.closed = False
        self.root.model_loading = None
        self.root.model_loading_timer = None
        self.root.model_loading_text = tk.StringVar(self.root)
        self.root.model_loading_bar = ttk.Progressbar(self.root)
        self.root.tick_model_loading = lambda: App.tick_model_loading(self.root)

    def tearDown(self):
        if self.root.model_loading is not None:
            App.finish_model_loading(self.root, self.root.model_loading[0], False)
        self.root.destroy()

    def test_animation_elapsed_time_completion_and_retry(self):
        App.begin_model_loading(self.root, 'chat', 'test-model')
        self.root.update()
        self.assertEqual(str(self.root.model_loading_bar['mode']), 'indeterminate')
        self.assertIn('test-model', self.root.model_loading_text.get())
        self.assertIn('0초', self.root.model_loading_text.get())
        self.assertIsNotNone(self.root.model_loading_timer)
        App.finish_model_loading(self.root, 'server', True)
        self.assertIsNotNone(self.root.model_loading)
        App.finish_model_loading(self.root, 'chat', True)
        self.assertEqual(self.root.model_loading_bar['value'], 100)
        self.assertIn('준비 완료', self.root.model_loading_text.get())
        self.assertIsNone(self.root.model_loading_timer)
        App.begin_model_loading(self.root, 'chat', 'retry-model')
        App.finish_model_loading(self.root, 'chat', False)
        self.assertEqual(self.root.model_loading_bar['value'], 0)
        self.assertIn('실패', self.root.model_loading_text.get())


class ChatLoadingTests(unittest.TestCase):
    def make_app(self):
        app = Mock()
        app.busy = set()
        app.online = True
        app.history = []
        app.performance = {}
        app.model_profiles = {}
        app.selected.get.return_value = 'test-model'
        app.prompt.get.return_value = 'hello'
        app.emit.side_effect = lambda callback, *args: callback(*args)
        app.job.side_effect = lambda key, work, done: done(work())
        return app

    def test_empty_chunk_keeps_loading_until_thinking(self):
        app = self.make_app()

        def stream(*args):
            app.begin_model_loading.assert_called_once_with('chat', 'test-model')
            yield {'message': {'content': ''}}
            app.finish_model_loading.assert_not_called()
            yield {'message': {'thinking': 'reasoning'}}
            app.finish_model_loading.assert_called_once_with('chat', True)
            yield {'message': {'content': 'hello'}, 'done': True}

        app.client.stream.side_effect = stream
        App.send(app)
        app.finish_model_loading.assert_called_once_with('chat', True)

    def test_load_failure_stops_animation_and_restores_model_picker(self):
        app = self.make_app()
        app.client.stream.side_effect = RuntimeError('load failed')
        with self.assertRaisesRegex(RuntimeError, 'load failed'):
            App.send(app)
        app.finish_model_loading.assert_called_once_with('chat', False)
        self.assertEqual(app.models.configure.call_args.args, ({'state': 'readonly'},))


if __name__ == '__main__':
    unittest.main()
