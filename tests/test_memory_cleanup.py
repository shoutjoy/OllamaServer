import tkinter as tk
import time
import unittest
from unittest.mock import Mock, patch

from app import App
from memory_cleanup import clean_memory


class MemoryCleanupTests(unittest.TestCase):
    def test_automatic_collection_does_not_trim_working_set(self):
        with patch('memory_cleanup.gc.collect', return_value=7), patch('memory_cleanup.ctypes.WinDLL', create=True) as dll:
            self.assertIn('7개', clean_memory())
            dll.assert_not_called()

    def test_windows_trims_only_current_process_with_pointer_sized_handle(self):
        kernel = Mock()
        kernel.GetCurrentProcess.return_value = 0x123456789
        kernel.K32EmptyWorkingSet.return_value = 1
        with patch('memory_cleanup.os.name', 'nt'), patch('memory_cleanup.ctypes.WinDLL', create=True, return_value=kernel):
            self.assertIn('반환 완료', clean_memory(trim=True))
        kernel.K32EmptyWorkingSet.assert_called_once_with(0x123456789)

    def test_trim_failure_still_collects(self):
        with patch('memory_cleanup.os.name', 'nt'), patch('memory_cleanup.gc.collect', return_value=3), patch('memory_cleanup.ctypes.WinDLL', create=True, side_effect=OSError('denied')):
            result = clean_memory(trim=True)
        self.assertIn('3개', result)
        self.assertIn('반환 실패', result)

    def test_cleanup_skips_active_jobs(self):
        app = Mock(busy={'chat'})
        App.clean_app_memory(app)
        app.job.assert_not_called()
        app.trim_log_views.assert_not_called()

    def test_real_widget_limit_preserves_conversation(self):
        root = tk.Tk()
        root.withdraw()
        try:
            log = tk.Text(root)
            conversation = tk.Text(root)
            App.append(log, '가' * 210000, max_chars=200000)
            App.append(conversation, '나' * 210000)
            self.assertEqual(len(log.get('1.0', 'end-1c')), 200000)
            self.assertEqual(len(conversation.get('1.0', 'end-1c')), 210000)
            self.assertEqual(log.cget('state'), 'disabled')
        finally:
            root.destroy()

    def test_app_cleanup_completes_and_auto_mode_can_be_disabled(self):
        with patch.object(App, 'monitor_resources'), patch.object(App, 'refresh'), patch('app.clean_memory', return_value='정리 완료') as collect:
            app = App()
            app.withdraw()
            try:
                app.clean_app_memory()
                deadline = time.monotonic() + 3
                while 'app-memory' in app.busy and time.monotonic() < deadline:
                    app.update()
                    time.sleep(.01)
                self.assertNotIn('app-memory', app.busy)
                self.assertEqual(app.memory_status.get(), '정리 완료')
                collect.assert_called_once_with(trim=True)
                app.auto_memory.set(False)
                app.auto_clean_memory()
                collect.assert_called_once()
                app.auto_memory.set(True)
                app.auto_clean_memory()
                deadline = time.monotonic() + 3
                while 'app-memory' in app.busy and time.monotonic() < deadline:
                    app.update()
                    time.sleep(.01)
                collect.assert_called_with(trim=False)
            finally:
                app.closed = True
                app.monitor_stop.set()
                app.destroy()
