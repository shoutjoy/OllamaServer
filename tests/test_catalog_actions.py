import unittest
from unittest.mock import Mock, patch

from app import App


class CatalogActionsTests(unittest.TestCase):
    def make_app(self):
        app = Mock()
        app.busy = set()
        app.install_terminal_active = False
        app.target.get.return_value = 'deepseek-r1:8b'
        return app

    def test_pull_uses_selected_tag_and_executes(self):
        app = self.make_app()
        App.pull_in_console(app)
        app.command.set.assert_called_once_with('ollama pull deepseek-r1:8b')
        app.notebook.select.assert_called_once_with(app.console_tab)
        app.console_execute.assert_called_once_with()

    def test_detail_window_model_is_not_changed_by_main_selection(self):
        app = self.make_app()
        App.pull_in_console(app, 'deepseek-ocr:latest')
        app.command.set.assert_called_once_with('ollama pull deepseek-ocr:latest')

    def test_busy_actions_never_send_to_stdin(self):
        for job in ('console', 'pull', 'chat', 'server', 'installer'):
            app = self.make_app()
            app.busy = {job}
            with patch('app.messagebox.showinfo'):
                App.pull_in_console(app)
            app.console_execute.assert_not_called()
            app.command.set.assert_not_called()

    def test_invalid_model_does_not_execute(self):
        app = self.make_app()
        with patch('app.messagebox.showerror') as error:
            App.pull_in_console(app, 'bad; command')
        error.assert_called_once()
        app.console_execute.assert_not_called()

    def test_site_uses_selected_result(self):
        app = self.make_app()
        app.selected_catalog_result.return_value = ('deepseek-ocr', 'Full description')
        with patch('app.webbrowser.open') as opener:
            App.open_model_site(app)
        opener.assert_called_once_with('https://ollama.com/library/deepseek-ocr')

    def test_no_selection(self):
        app = self.make_app()
        app.results.selection.return_value = ()
        with patch('app.messagebox.showinfo') as info:
            self.assertIsNone(App.selected_catalog_result(app))
        info.assert_called_once()
