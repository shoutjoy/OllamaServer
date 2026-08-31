"""Real Tk widgets with a fake Ollama transport; no downloads or server changes."""
import time
from unittest.mock import patch
from app import App


def get(path, timeout=4):
    return {'version': 'test'} if path.endswith('version') else {'models': [{'name': 'test:1b'}]}


def stream(path, data, cancel=None):
    if path == '/api/pull':
        yield {'status': 'pulling', 'total': 100, 'completed': 50}
        yield {'status': 'success'}
    else:
        yield {'message': {'content': '테스트 응답'}, 'done': False}
        yield {'message': {'content': ''}, 'done': True}


with patch('app.Client.get', side_effect=get), patch('app.Client.stream', side_effect=stream), \
     patch('app.search_models', return_value=[('test', 'Test model')]), \
     patch('app.fetch_tags', return_value=['1b']), patch('app.App.select_model'):
    app = App()
    def settle():
        deadline = time.monotonic() + 4
        while time.monotonic() < deadline:
            app.update()
            if not app.busy and app.events.empty():
                return
            time.sleep(0.02)
        raise AssertionError('UI job timed out')
    settle()
    assert app.online
    assert app.server_light.itemcget(app.server_light_dot, 'fill') == '#16a34a'
    app.refreshed((None, []))
    assert app.server_light.itemcget(app.server_light_dot, 'fill') == '#94a3b8'
    app.refreshed(('test', [{'name': 'test:1b'}]))
    assert app.server_light.itemcget(app.server_light_dot, 'fill') == '#16a34a'
    app.search()
    settle()
    app.results.selection_set(app.results.get_children()[0])
    app.update()
    settle()
    app.tags.set('1b')
    app.pick_tag()
    assert app.target.get() == 'test:1b'
    app.pull()
    settle()
    assert app.progress['value'] == 100
    app.prompt.insert('1.0', '안녕하세요')
    app.send()
    settle()
    assert app.history[-1]['content'] == '테스트 응답'
    assert '테스트 응답' in app.transcript.get('1.0', 'end')
    app.clear_chat()
    assert not app.history
    app.notebook.select(app.console_tab)
    def console_run(args, output):
        assert args == ['fake-ollama', 'list']
        output('NAME SIZE\ntest:1b 100 MB\n')
        return 0
    with patch('app.find_ollama', return_value='fake-ollama'), patch('app.ConsoleRunner.run', side_effect=console_run):
        app.command.set('ollama list')
        app.command_entry.event_generate('<Return>')
        # Explicit focus is not guaranteed on unattended desktops.
        if app.command.get():
            app.console_execute()
        settle()
    assert 'test:1b 100 MB' in app.console_view.get('1.0', 'end')
    app.console_history(-1)
    assert app.command.get() == 'ollama list'
    app.command.set('powershell whoami')
    app.console_execute()
    assert '지원 명령' in app.console_view.get('1.0', 'end')
    app.console_clear()
    assert not app.console_view.get('1.0', 'end').strip()
    assert app.winfo_width() >= 840
    app.close()
print('PASS: Tk window, search, pull, chat, console execution/output/history/validation/clear')
