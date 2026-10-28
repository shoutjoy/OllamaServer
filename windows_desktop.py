"""Windows login startup and notification icon, using only the standard library."""
import os
import subprocess
import sys
import threading
from pathlib import Path

RUN_KEY = r'Software\Microsoft\Windows\CurrentVersion\Run'
APP_NAME = 'OllamaDesk'


def startup_enabled():
    if os.name != 'nt':
        return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.QueryValueEx(key, APP_NAME)
        return True
    except FileNotFoundError:
        return False


def set_startup(enabled):
    import winreg
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
        if enabled:
            executable = Path(sys.executable)
            args = [str(executable)]
            if not getattr(sys, 'frozen', False):
                windowed = executable.with_name('pythonw.exe')
                args = [str(windowed if windowed.exists() else executable),
                        str(Path(__file__).resolve().with_name('app.py'))]
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ,
                             subprocess.list2cmdline(args + ['--startup']))
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass


class TrayIcon:
    def __init__(self, icon_path, on_open, on_exit):
        self.icon_path = str(icon_path)
        self.on_open, self.on_exit = on_open, on_exit
        self.hwnd = None
        self.error = None
        self.ready = threading.Event()

    def start(self):
        threading.Thread(target=self._run, daemon=True).start()
        if not self.ready.wait(5):
            raise OSError('시스템 트레이 응답 시간 초과')
        if self.error:
            raise OSError(str(self.error))

    def stop(self):
        if self.hwnd:
            import ctypes
            ctypes.windll.user32.PostMessageW(self.hwnd, 0x0010, 0, 0)

    def _run(self):
        import ctypes as c
        from ctypes import wintypes as w
        user, shell, kernel = c.windll.user32, c.windll.shell32, c.windll.kernel32
        callback_type = c.WINFUNCTYPE(c.c_ssize_t, w.HWND, w.UINT, w.WPARAM, w.LPARAM)
        class WindowClass(c.Structure):
            _fields_ = [('style', w.UINT), ('proc', callback_type), ('clsExtra', c.c_int),
                        ('wndExtra', c.c_int), ('instance', w.HINSTANCE), ('icon', w.HICON),
                        ('cursor', w.HANDLE), ('background', w.HBRUSH),
                        ('menu', w.LPCWSTR), ('name', w.LPCWSTR)]
        class NotifyData(c.Structure):
            _fields_ = [('size', w.DWORD), ('hwnd', w.HWND), ('id', w.UINT),
                        ('flags', w.UINT), ('message', w.UINT), ('icon', w.HICON),
                        ('tip', w.WCHAR * 128), ('state', w.DWORD), ('mask', w.DWORD),
                        ('info', w.WCHAR * 256), ('timeout', w.UINT),
                        ('title', w.WCHAR * 64), ('infoFlags', w.DWORD),
                        ('guid', c.c_byte * 16), ('balloon', w.HICON)]
        user.DefWindowProcW.restype = c.c_ssize_t
        user.DefWindowProcW.argtypes = [w.HWND, w.UINT, w.WPARAM, w.LPARAM]
        user.CreateWindowExW.restype = w.HWND
        user.CreateWindowExW.argtypes = [w.DWORD, w.LPCWSTR, w.LPCWSTR, w.DWORD,
                                       c.c_int, c.c_int, c.c_int, c.c_int,
                                       w.HWND, w.HMENU, w.HINSTANCE, c.c_void_p]
        kernel.GetModuleHandleW.restype = w.HMODULE
        user.LoadImageW.restype = w.HANDLE
        user.LoadImageW.argtypes = [w.HINSTANCE, w.LPCWSTR, w.UINT, c.c_int, c.c_int, w.UINT]
        user.CreatePopupMenu.restype = w.HMENU
        user.AppendMenuW.argtypes = [w.HMENU, w.UINT, c.c_size_t, w.LPCWSTR]
        user.TrackPopupMenu.argtypes = [w.HMENU, w.UINT, c.c_int, c.c_int, c.c_int, w.HWND, c.c_void_p]
        user.DestroyMenu.argtypes = [w.HMENU]
        user.DestroyWindow.argtypes = [w.HWND]
        user.SetForegroundWindow.argtypes = [w.HWND]
        user.PostMessageW.argtypes = [w.HWND, w.UINT, w.WPARAM, w.LPARAM]
        user.DestroyIcon.argtypes = [w.HICON]
        user.UnregisterClassW.argtypes = [w.LPCWSTR, w.HINSTANCE]
        taskbar_created = user.RegisterWindowMessageW('TaskbarCreated')
        data = NotifyData()
        @callback_type
        def handler(hwnd, msg, wp, lp):
            if msg == taskbar_created:
                shell.Shell_NotifyIconW(0, c.byref(data))
            elif msg == 0x8001:
                if lp == 0x0203:
                    self.on_open()
                elif lp in (0x0205, 0x007B):
                    point = w.POINT()
                    user.GetCursorPos(c.byref(point))
                    menu = user.CreatePopupMenu()
                    user.AppendMenuW(menu, 0, 1, '열기')
                    user.AppendMenuW(menu, 0, 2, '종료')
                    user.SetForegroundWindow(hwnd)
                    chosen = user.TrackPopupMenu(menu, 0x0100 | 0x0002, point.x, point.y, 0, hwnd, None)
                    user.DestroyMenu(menu)
                    user.PostMessageW(hwnd, 0, 0, 0)
                    if chosen == 1:
                        self.on_open()
                    elif chosen == 2:
                        self.on_exit()
            elif msg == 0x0010:
                user.DestroyWindow(hwnd)
            elif msg == 0x0002:
                shell.Shell_NotifyIconW(2, c.byref(data))
                user.PostQuitMessage(0)
            return user.DefWindowProcW(hwnd, msg, wp, lp)
        icon = None
        try:
            instance = kernel.GetModuleHandleW(None)
            name = 'OllamaDeskTray' + str(id(self))
            wc = WindowClass()
            wc.proc, wc.instance, wc.name = handler, instance, name
            if not user.RegisterClassW(c.byref(wc)):
                raise c.WinError()
            self.hwnd = user.CreateWindowExW(0, name, name, 0, 0, 0, 0, 0, None, None, instance, None)
            if not self.hwnd:
                raise c.WinError()
            icon = user.LoadImageW(None, self.icon_path, 1, 32, 32, 0x0010)
            if not icon:
                raise c.WinError()
            data.size, data.hwnd, data.id = c.sizeof(data), self.hwnd, 1
            data.flags, data.message, data.icon, data.tip = 7, 0x8001, icon, 'Ollama Desk'
            if not shell.Shell_NotifyIconW(0, c.byref(data)):
                raise c.WinError()
            self.ready.set()
            msg = w.MSG()
            while user.GetMessageW(c.byref(msg), None, 0, 0) > 0:
                user.TranslateMessage(c.byref(msg))
                user.DispatchMessageW(c.byref(msg))
        except Exception as exc:
            self.error = exc
            self.ready.set()
        finally:
            if self.hwnd:
                shell.Shell_NotifyIconW(2, c.byref(data))
            self.hwnd = None
            if icon:
                user.DestroyIcon(icon)
            user.UnregisterClassW(c.c_wchar_p(name), instance)
