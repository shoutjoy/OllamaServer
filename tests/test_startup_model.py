import unittest
from unittest.mock import Mock, patch

from app import App, DEFAULT_MODELS
from core import PERFORMANCE_DEFAULTS


class StartupModelTests(unittest.TestCase):
    def setUp(self):
        loader = patch('app.run_ollama_model', return_value=False)
        self.loader = loader.start()
        self.addCleanup(loader.stop)
        finder = patch('app.find_ollama', return_value='ollama.exe')
        finder.start()
        self.addCleanup(finder.stop)

    def make_app(self, engine='ollama'):
        app = Mock()
        app.closed = False
        app.busy = set()
        app.engine = app.client.engine = engine
        app.performance = {}
        app.model_profiles = {}
        app.safe_draft_models = set()
        app.load_model.side_effect = lambda **kwargs: App.load_model(app, **kwargs)
        app.startup_model_pending = True
        app.selected.get.return_value = DEFAULT_MODELS[engine]
        app.client.get.side_effect = [ {'version': 'test'},
            {'models': [{'name': DEFAULT_MODELS[engine]}]}, {'models': []} ]
        app.client.post.return_value = {'done': True}
        app.emit.side_effect = lambda fn, *args: fn(*args)
        app.job.side_effect = lambda key, work, done: done(work())
        return app

    def test_default_preload_has_no_prompt_and_uses_saved_options(self):
        app = self.make_app()
        App.load_startup_model(app)
        app.selected.set.assert_called_once_with('gemma4:e4b')
        self.assertEqual(self.loader.call_args.args[2], 'gemma4:e4b')
        self.assertIn('keep_alive', self.loader.call_args.args[3])
        self.assertFalse(app.startup_model_pending)
        app.finish_model_loading.assert_called_once_with('startup', True)

    def test_missing_model_fails_without_download_or_other_model(self):
        app = self.make_app()
        app.client.get.side_effect = [{'version': 'test'}, {'models': [{'name': 'other'}]}, {'models': []}]
        with self.assertRaisesRegex(RuntimeError, '설치되어 있지 않습니다'):
            App.load_startup_model(app)
        app.client.post.assert_not_called()
        app.finish_model_loading.assert_called_once_with('startup', False)
        self.assertFalse(app.startup_model_pending)

    def test_lemonade_loads_e4b_without_flm_preload(self):
        app = self.make_app('lemonade')
        App.load_startup_model(app)
        app.client.post.assert_called_once_with('/api/v1/load', {
            'model_name': 'Gemma-4-E4B-it-GGUF', 'ctx_size': PERFORMANCE_DEFAULTS['context_length']})
        app.start_npu_server_worker.assert_not_called()

    def test_busy_startup_waits_before_loading(self):
        app = self.make_app()
        app.busy = {'chat'}
        App.load_startup_model(app)
        app.after.assert_called_once_with(250, app.load_startup_model)
        app.client.post.assert_not_called()

    def test_offline_ollama_starts_before_loading(self):
        app = self.make_app()
        app.client.get.side_effect = [OSError('offline'), {'models': [{'name': 'gemma4:e4b'}]}, {'models': []}]
        with patch('app.find_ollama', return_value='ollama.exe'):
            App.load_startup_model(app)
        app.start_server_worker.assert_called_once()
        self.loader.assert_called_once()

    def test_startup_keeps_external_model_without_preload(self):
        app = self.make_app()
        running = [{'name': 'other-model', 'context_length': 8192}]
        app.client.get.side_effect = [{'version': 'test'}, {'models': []}, {'models': running}]
        App.load_startup_model(app)
        self.loader.assert_not_called()
        app.keep_running_models.assert_called_once_with(running)
        self.assertFalse(app.startup_model_pending)

    def test_startup_uses_saved_model(self):
        app = self.make_app()
        app.selected.get.return_value = 'saved:1b'
        app.client.get.side_effect = [{'version': 'test'}, {'models': [{'name': 'saved:1b'}]}, {'models': []}]
        App.load_startup_model(app)
        self.assertEqual(self.loader.call_args.args[2], 'saved:1b')

    def test_manual_load_uses_selected_model(self):
        app = self.make_app()
        app.selected.get.return_value = 'qwen3.5:9b'
        app.client.get.side_effect = [{'version': 'test'}, {'models': [{'name': 'qwen3.5:9b'}]}]
        App.load_model(app)
        self.assertEqual(self.loader.call_args.args[2], 'qwen3.5:9b')
        app.load_model_button.configure.assert_any_call({'state': 'normal'})


if __name__ == '__main__':
    unittest.main()
