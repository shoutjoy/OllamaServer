import unittest
from unittest.mock import Mock, patch
from core import running_model_change
from app import App


class ModelSyncTests(unittest.TestCase):
    def test_new_model_and_reused_loaded_model(self):
        candidate, snapshot = running_model_change({}, [{'name': 'a:1b', 'expires_at': '1'}])
        self.assertEqual(candidate, 'a:1b')
        candidate, snapshot = running_model_change(snapshot, [
            {'name': 'a:1b', 'expires_at': '1'}, {'name': 'b:1b', 'expires_at': '2'}])
        self.assertEqual(candidate, 'b:1b')
        candidate, _ = running_model_change(snapshot, [
            {'name': 'a:1b', 'expires_at': '3'}, {'name': 'b:1b', 'expires_at': '2'}])
        self.assertEqual(candidate, 'a:1b')

    def test_unchanged_empty_and_ambiguous_do_not_select(self):
        for previous, models in [({'a': '1'}, [{'name': 'a', 'expires_at': '1'}]),
                                 ({'a': '1'}, []),
                                 ({}, [{'name': 'a'}, {'name': 'b'}])]:
            self.assertIsNone(running_model_change(previous, models)[0])

    def test_ui_sync_and_chat_guard(self):
        app = Mock()
        app.online = True
        app.running_models_snapshot = {'a': '1'}
        app.selected.get.return_value = 'a'
        app.busy = set()
        result = ('test', [{'name': 'a'}, {'name': 'b'}], [{'name': 'b', 'expires_at': '2'}])
        App.refreshed(app, result)
        app.selected.set.assert_called_once_with('b')
        app.select_model.assert_called_once_with()
        app.selected.set.reset_mock()
        app.running_models_snapshot = {'a': '1'}
        app.busy = {'chat'}
        App.refreshed(app, result)
        app.selected.set.assert_not_called()
        self.assertEqual(app.running_models_snapshot, {'a': '1'})

    def test_ps_failure_does_not_mark_server_offline(self):
        app = Mock()
        app.engine = 'ollama'
        app.busy = set()
        app.client.get.side_effect = [{'version': 'test'}, {'models': [{'name': 'a'}]}, OSError('ps unavailable')]
        app.job.side_effect = lambda key, work, done, **kw: done(work())
        with patch('app.find_ollama', return_value='ollama'):
            App.refresh(app)
        app.refreshed.assert_called_once_with(('test', [{'name': 'a'}], None))
