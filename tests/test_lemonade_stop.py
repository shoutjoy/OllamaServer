import unittest
from unittest.mock import Mock, patch
from app import App


class LemonadeStopTests(unittest.TestCase):
    def test_unresponsive_unload_still_quits_process_tree(self):
        app = Mock()
        app.client.engine = 'lemonade'
        app.client.post.side_effect = RuntimeError('server not responding')
        app.client.get.side_effect = ConnectionError('stopped')
        with patch('app.find_lemonade', return_value='C:/Lemonade/LemonadeServer.exe'), patch('app.os.name', 'nt'), patch('app.subprocess.run') as run:
            self.assertIn('정지', App.stop_server_worker(app, False))
        app.client.post.assert_called_once_with('/api/v1/unload', {}, timeout=5)
        script = run.call_args.args[0][-1]
        self.assertIn('taskkill.exe /PID $target.Id /T /F', script)
        self.assertIn('$_.Path -eq $p', script)
        self.assertIn('Lemonade tray is still running', script)
        self.assertNotIn('Get-CimInstance', script)
        self.assertIsNone(app.process)

    def test_failed_process_termination_is_not_reported_as_success(self):
        app = Mock()
        app.client.engine = 'lemonade'
        with patch('app.find_lemonade', return_value='C:/Lemonade/LemonadeServer.exe'), patch('app.os.name', 'nt'), patch('app.subprocess.run', side_effect=RuntimeError('denied')):
            with self.assertRaisesRegex(RuntimeError, 'denied'):
                App.stop_server_worker(app, False)
        app.client.get.assert_not_called()


if __name__ == '__main__':
    unittest.main()
