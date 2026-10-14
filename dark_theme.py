"""Built-in Tk/ttk dark theme, also available in PyInstaller bundles."""
import ctypes
import sys
import tkinter as tk
from tkinter import ttk

BACKGROUND = '#111827'
SURFACE = '#1f2937'
TEXT = '#e5e7eb'
MUTED = '#94a3b8'
BORDER = '#374151'
SELECTED = '#2563eb'


def apply_dark_theme(root, mode='dark'):
    root.ui_theme = mode
    BACKGROUND, SURFACE, TEXT, MUTED, BORDER, SELECTED = (
        ('#111827', '#1f2937', '#e5e7eb', '#94a3b8', '#374151', '#2563eb')
        if mode == 'dark' else
        ('#f3f5f9', '#ffffff', '#233047', '#64748b', '#cbd5e1', '#2563eb'))
    text_background = '#101827' if mode == 'dark' else '#ffffff'
    root.configure(background=BACKGROUND)
    # Tk widgets (including future Toplevels, Texts and combo popdown lists).
    for pattern, value in {
        '*background': BACKGROUND, '*foreground': TEXT,
        '*Text.background': text_background, '*Text.foreground': TEXT,
        '*Text.insertBackground': TEXT, '*Text.selectBackground': SELECTED,
        '*Text.selectForeground': '#ffffff', '*Text.highlightBackground': BORDER,
        '*Text.highlightColor': SELECTED,
        '*Listbox.background': SURFACE, '*Listbox.foreground': TEXT,
        '*Listbox.selectBackground': SELECTED, '*Listbox.selectForeground': '#ffffff',
        '*Scrollbar.background': SURFACE, '*Scrollbar.troughColor': BACKGROUND,
        '*Scrollbar.activeBackground': BORDER,
    }.items():
        root.option_add(pattern, value)
    style = ttk.Style(root)
    style.theme_use('clam')
    style.configure('.', font=('맑은 고딕', 10), background=BACKGROUND,
                    foreground=TEXT, bordercolor=BORDER, lightcolor=BORDER,
                    darkcolor=BORDER, troughcolor=BACKGROUND,
                    selectbackground=SELECTED, selectforeground='#ffffff')
    for name in ('TFrame', 'TLabel', 'TLabelframe', 'TCheckbutton', 'TNotebook'):
        style.configure(name, background=BACKGROUND)
    style.configure('TLabelframe.Label', background=BACKGROUND, foreground=MUTED)
    style.configure('Title.TLabel', font=('맑은 고딕', 23, 'bold'))
    for name in ('TButton', 'TCheckbutton', 'Treeview.Heading', 'TNotebook.Tab'):
        style.configure(name, background=SURFACE, foreground=TEXT, padding=(12, 7))
        style.map(name, background=[('disabled', BACKGROUND), ('pressed', SELECTED),
                                   ('active', BORDER)],
                  foreground=[('disabled', MUTED)])
    style.configure('TCheckbutton', background=BACKGROUND)
    style.map('TNotebook.Tab', background=[('selected', SELECTED), ('active', BORDER)],
              foreground=[('selected', '#ffffff')])
    for name in ('TEntry', 'TCombobox', 'TSpinbox'):
        style.configure(name, fieldbackground=SURFACE, foreground=TEXT,
                        insertcolor=TEXT, background=SURFACE, arrowcolor=TEXT)
        style.map(name, fieldbackground=[('disabled', BACKGROUND), ('readonly', SURFACE)],
                  foreground=[('disabled', MUTED), ('readonly', TEXT)],
                  selectbackground=[('!disabled', SELECTED)],
                  selectforeground=[('!disabled', '#ffffff')])
    style.configure('Treeview', rowheight=32, background=SURFACE,
                    fieldbackground=SURFACE, foreground=TEXT)
    style.map('Treeview', background=[('selected', SELECTED)],
              foreground=[('selected', '#ffffff')])
    for axis in ('Horizontal', 'Vertical'):
        style.configure(axis + '.TScrollbar', background=SURFACE, arrowcolor=TEXT)
        style.map(axis + '.TScrollbar', background=[('active', BORDER)])
        style.configure(axis + '.TProgressbar', background='#60a5fa')
    def repaint(widget):
        if isinstance(widget, (tk.Tk, tk.Toplevel, tk.Frame, tk.Label, tk.Canvas)):
            widget.configure(background=getattr(widget, '_theme_background',
                             SURFACE if getattr(widget, '_theme_surface', False) else BACKGROUND))
            if isinstance(widget, tk.Label):
                widget.configure(foreground=TEXT)
            if isinstance(widget, (tk.Tk, tk.Toplevel)):
                _set_titlebar(widget, mode)
        if isinstance(widget, tk.Text):
            terminal = getattr(widget, '_theme_terminal', False)
            foreground = '#e5e7eb' if terminal else TEXT
            widget.configure(background='#000000' if terminal else text_background, foreground=foreground,
                             insertbackground=foreground, selectbackground=SELECTED,
                             selectforeground='#ffffff', highlightbackground=BORDER)
        if isinstance(widget, tk.Scrollbar) and not isinstance(widget, ttk.Scrollbar):
            widget.configure(background=SURFACE, troughcolor=BACKGROUND,
                             activebackground=BORDER)
        for child in widget.winfo_children():
            repaint(child)
    repaint(root)
    # A combobox popdown is a Tcl child, absent from winfo_children().
    def popdowns(widget):
        if isinstance(widget, ttk.Combobox):
            popdown = widget.tk.call('ttk::combobox::PopdownWindow', widget)
            widget.tk.call(str(popdown) + '.f.l', 'configure',
                           '-background', SURFACE, '-foreground', TEXT,
                           '-selectbackground', SELECTED, '-selectforeground', '#ffffff')
        for child in widget.winfo_children():
            popdowns(child)
    popdowns(root)
    if not getattr(root, '_theme_map_bound', False):
        root.bind('<Map>', _dark_titlebar, add='+')
        root._theme_map_bound = True


def _dark_titlebar(event):
    """Best-effort Windows title bar; other platforms use their window manager."""
    if sys.platform != 'win32' or event.widget.winfo_class() not in ('Tk', 'Toplevel'):
        return
    _set_titlebar(event.widget, getattr(event.widget.winfo_toplevel().master or event.widget, 'ui_theme', 'dark'))


def _set_titlebar(widget, mode):
    if sys.platform != 'win32':
        return
    try:
        user32 = ctypes.windll.user32
        user32.GetParent.argtypes = [ctypes.c_void_p]
        user32.GetParent.restype = ctypes.c_void_p
        hwnd = ctypes.c_void_p(user32.GetParent(widget.winfo_id()))
        enabled = ctypes.c_int(mode == 'dark')
        for attribute in (20, 19):
            if ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, attribute, ctypes.byref(enabled), ctypes.sizeof(enabled)) == 0:
                break
    except (AttributeError, OSError):
        pass
