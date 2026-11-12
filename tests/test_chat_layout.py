import tkinter as tk
import unittest
from unittest.mock import patch
from app import App


class ChatLayoutTests(unittest.TestCase):
    def test_composer_remains_visible_in_default_window(self):
        with patch.object(App, 'refresh'), patch.object(App, 'monitor_resources'), patch.object(App, 'start_bridge'), patch.object(App, 'load_startup_model'):
            app = App()
            try:
                app.geometry('1380x780')
                app.notebook.select(app.transcript.master.master)
                app.update()
                composer = app.prompt._w
                self.assertTrue(app.prompt.winfo_ismapped(), composer)
                self.assertTrue(app.send_button.winfo_ismapped())
                self.assertGreater(app.prompt.winfo_height(), 20)
                self.assertLess(app.prompt.winfo_rooty() + app.prompt.winfo_height(), app.winfo_rooty() + app.winfo_height())
                self.assertLess(app.send_button.winfo_rooty() + app.send_button.winfo_height(), app.winfo_rooty() + app.winfo_height())
            finally:
                app.closed = True
                app.monitor_stop.set()
                for callback in app.tk.call('after', 'info'):
                    app.after_cancel(callback)
                app.destroy()

