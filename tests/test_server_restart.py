import unittest
from unittest.mock import Mock, patch
from app import App


class RestartTests(unittest.TestCase):
    def make_app(self):
        app = Mock()
        app.busy = set()
        app.process = Mock()
        app.process.poll.return_value = None
        app.performance = {'keep_alive': '30m'}
        return app

    def test_stop_then_start_with_saved_settings(self):
        app = self.make_app()
        order = []
        app.stop_server_worker.side_effect = lambda owned: order.append(('stop', owned))
        app.start_server_worker.side_effect = lambda exe, settings: order.append(('start', settings)) or '서버가 시작되었습니다.'
        app.job.side_effect = lambda key, work, done: done(work())
        with patch('app.find_ollama', return_value='ollama.exe'):
            App.restart_server(app)
        self.assertEqual(order, [('stop', True), ('start', {'keep_alive': '30m'})])
        app.refresh.assert_called_once()

    def test_stop_failure_never_starts(self):
        app = self.make_app()
        app.stop_server_worker.side_effect = RuntimeError('still running')
        app.job.side_effect = lambda key, work, done: work()
        with patch('app.find_ollama', return_value='ollama.exe'), self.assertRaises(RuntimeError):
            App.restart_server(app)
        app.start_server_worker.assert_not_called()

    def test_offline_server_starts_without_stop(self):
        app = self.make_app()
        app.process = None
        app.client.get.side_effect = OSError('offline')
        app.start_server_worker.return_value = '서버가 시작되었습니다.'
        app.job.side_effect = lambda key, work, done: done(work())
        with patch('app.find_ollama', return_value='ollama.exe'):
            App.restart_server(app)
        app.stop_server_worker.assert_not_called()
        app.start_server_worker.assert_called_once()

    def test_active_request_blocks_restart(self):
        app = self.make_app()
        app.busy = {'chat'}
        with patch('app.messagebox.showinfo'):
            App.restart_server(app)
        app.job.assert_not_called()
