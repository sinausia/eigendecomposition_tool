"""Look of the window: colours, fonts and ttk styles.

Built on the cross-platform 'clam' theme so the app looks the same on macOS
and Windows. Change the colours here and the whole window follows.
"""
import sys
import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

# ---- Colours ----
BG = '#F4F4F2'            # window background (warm light grey)
CARD = '#FFFFFF'          # panels
BORDER = '#E2E2DE'        # panel outlines, separators
FIELD_BORDER = '#CACAC4'  # entry and button outlines
HOVER = '#F3F3F0'
PRESSED = '#E8E8E4'
INK = '#1F1F24'           # main text
MUTED = '#6B6B73'         # secondary text
FAINT = '#A3A3AA'         # placeholder / disabled text
ACCENT = '#4B2A7B'        # plum, first colour of the plot palette (style.SUNSET)
ACCENT_HOVER = '#5E3A94'
ACCENT_PRESS = '#3A1F61'
ACCENT_SOFT = '#EEE9F6'
DISABLED_BG = '#E9E9E6'
SUCCESS = '#2E7D4F'
ERROR = '#B3261E'
LOG_BG = '#FAFAF8'


class Fonts:
    """Named fonts, sized for each platform (Tk point sizes differ between macOS and Windows)."""

    def __init__(self, root):
        if sys.platform == 'darwin':
            family = tkfont.nametofont('TkDefaultFont', root=root).actual('family')
            body, small, title, mono = 13, 11, 20, ('Menlo', 11)
        elif sys.platform == 'win32':
            family = 'Segoe UI'
            body, small, title, mono = 10, 9, 16, ('Consolas', 9)
        else:
            family = tkfont.nametofont('TkDefaultFont', root=root).actual('family')
            body, small, title, mono = 10, 9, 15, ('DejaVu Sans Mono', 9)
        self.body = tkfont.Font(root, family=family, size=body)
        self.body_bold = tkfont.Font(root, family=family, size=body, weight='bold')
        self.small = tkfont.Font(root, family=family, size=small)
        self.small_bold = tkfont.Font(root, family=family, size=small, weight='bold')
        self.title = tkfont.Font(root, family=family, size=title, weight='bold')
        self.mono = tkfont.Font(root, family=mono[0], size=mono[1])


def _flat(style, name, bg, border=None, **kwargs):
    """Configure a clam element with no 3D shading (light/dark colours = background)."""
    style.configure(name, background=bg, lightcolor=bg, darkcolor=bg,
                    bordercolor=border or bg, **kwargs)


def _flat_map(style, name, states):
    """states: list of (statespec, background, border, foreground or None)."""
    style.map(name,
              background=[(s, bg) for s, bg, _, _ in states],
              lightcolor=[(s, bg) for s, bg, _, _ in states],
              darkcolor=[(s, bg) for s, bg, _, _ in states],
              bordercolor=[(s, b) for s, _, b, _ in states],
              foreground=[(s, fg) for s, _, _, fg in states if fg])


def apply_theme(root):
    """Style the whole application. Returns the Fonts."""
    fonts = Fonts(root)
    root.configure(background=BG)
    style = ttk.Style(root)
    style.theme_use('clam')

    style.configure('.', background=BG, foreground=INK, font=fonts.body, bordercolor=BORDER,
                    lightcolor=BG, darkcolor=BG, troughcolor=BG, focuscolor=ACCENT,
                    selectbackground=ACCENT_SOFT, selectforeground=INK, insertcolor=INK)

    # Frames and labels
    style.configure('TFrame', background=BG)
    style.configure('Card.TFrame', background=CARD)
    style.configure('TLabel', background=BG, foreground=INK)
    style.configure('Title.TLabel', font=fonts.title)
    style.configure('Subtitle.TLabel', foreground=MUTED, font=fonts.small)
    style.configure('Card.TLabel', background=CARD)
    style.configure('Heading.Card.TLabel', background=CARD, font=fonts.body_bold)
    style.configure('Field.Card.TLabel', background=CARD, foreground=MUTED)
    style.configure('Muted.Card.TLabel', background=CARD, foreground=MUTED, font=fonts.small)
    style.configure('Small.Card.TLabel', background=CARD, font=fonts.small)
    style.configure('Status.TLabel', background=CARD, foreground=MUTED, font=fonts.small)

    # Entries
    _flat(style, 'TEntry', CARD, FIELD_BORDER, fieldbackground=CARD, foreground=INK,
          padding=(7, 4), insertwidth=1)
    style.map('TEntry',
              bordercolor=[('focus', ACCENT)], lightcolor=[('focus', ACCENT)],
              foreground=[('disabled', FAINT)], fieldbackground=[('disabled', DISABLED_BG)])

    # Dropdowns (read-only: click anywhere to open the list)
    _flat(style, 'TCombobox', CARD, FIELD_BORDER, fieldbackground=CARD, foreground=INK, arrowcolor=MUTED,
          padding=(7, 4), arrowsize=12)
    style.map('TCombobox',
              fieldbackground=[('readonly', CARD), ('disabled', DISABLED_BG)],
              background=[('active', HOVER), ('pressed', PRESSED)],
              bordercolor=[('focus', ACCENT)], lightcolor=[('focus', ACCENT)],
              selectbackground=[('readonly', CARD)], selectforeground=[('readonly', INK)],
              arrowcolor=[('active', ACCENT), ('disabled', FAINT)], foreground=[('disabled', FAINT)])
    root.option_add('*TCombobox*Listbox.background', CARD)
    root.option_add('*TCombobox*Listbox.foreground', INK)
    root.option_add('*TCombobox*Listbox.selectBackground', ACCENT)
    root.option_add('*TCombobox*Listbox.selectForeground', 'white')
    root.option_add('*TCombobox*Listbox.borderWidth', 0)
    root.option_add('*TCombobox*Listbox.relief', 'flat')

    # Buttons: drop the dotted focus element for a clean, flat look
    style.layout('TButton', [('Button.border', {'sticky': 'nswe', 'border': '1', 'children': [
        ('Button.padding', {'sticky': 'nswe', 'children': [('Button.label', {'sticky': 'nswe'})]})]})])
    _flat(style, 'TButton', CARD, FIELD_BORDER, foreground=INK, padding=(12, 4), relief='flat',
          anchor='center')
    _flat_map(style, 'TButton', [('disabled', CARD, BORDER, FAINT), ('pressed', PRESSED, FIELD_BORDER, None),
                                 ('active', HOVER, FIELD_BORDER, None)])

    _flat(style, 'Accent.TButton', ACCENT, ACCENT, foreground='white', font=fonts.body_bold,
          padding=(14, 7), relief='flat', anchor='center')
    _flat_map(style, 'Accent.TButton', [('disabled', DISABLED_BG, DISABLED_BG, FAINT),
                                        ('pressed', ACCENT_PRESS, ACCENT_PRESS, None),
                                        ('active', ACCENT_HOVER, ACCENT_HOVER, None)])

    _flat(style, 'Link.TButton', CARD, CARD, foreground=ACCENT, font=fonts.small, padding=(0, 0),
          relief='flat')
    _flat_map(style, 'Link.TButton', [('disabled', CARD, CARD, FAINT), ('active', CARD, CARD, ACCENT_HOVER)])

    # Checkbuttons (indicator only, label drawn separately where needed)
    style.layout('Card.TCheckbutton', [('Checkbutton.padding', {'sticky': 'nswe', 'children': [
        ('Checkbutton.indicator', {'side': 'left', 'sticky': ''}),
        ('Checkbutton.label', {'side': 'left', 'sticky': 'nswe'})]})])
    style.configure('Card.TCheckbutton', background=CARD, foreground=INK, padding=(0, 2),
                    indicatorbackground=CARD, indicatorforeground='white', indicatormargin=(0, 0, 6, 0),
                    upperbordercolor=FIELD_BORDER, lowerbordercolor=FIELD_BORDER)
    style.map('Card.TCheckbutton',
              background=[('active', CARD)],
              indicatorbackground=[('disabled', DISABLED_BG), ('selected', ACCENT), ('active', HOVER)],
              upperbordercolor=[('selected', ACCENT)], lowerbordercolor=[('selected', ACCENT)],
              foreground=[('disabled', FAINT)])

    # Progress bar
    style.configure('Thin.Horizontal.TProgressbar', background=ACCENT, troughcolor=BORDER, bordercolor=BORDER,
                    lightcolor=ACCENT, darkcolor=ACCENT, thickness=4)

    # Notebook: flat tabs, selected tab joins the white page
    style.configure('TNotebook', background=BG, borderwidth=0, tabmargins=(0, 0, 0, 0),
                    bordercolor=BORDER, lightcolor=CARD, darkcolor=CARD)
    style.layout('TNotebook.Tab', [('Notebook.tab', {'sticky': 'nswe', 'children': [
        ('Notebook.padding', {'side': 'top', 'sticky': 'nswe', 'children': [
            ('Notebook.label', {'side': 'top', 'sticky': ''})]})]})])
    style.configure('TNotebook.Tab', background=BG, foreground=MUTED, font=fonts.body_bold,
                    padding=(18, 8), borderwidth=0, bordercolor=BG, lightcolor=BG)
    style.map('TNotebook.Tab',
              background=[('selected', CARD), ('active', HOVER)],
              foreground=[('selected', ACCENT), ('active', INK)],
              bordercolor=[('selected', BORDER)], lightcolor=[('selected', CARD)],
              expand=[('selected', (0, 0, 0, 0))])

    # Scrollbars: slim, no arrows
    for orient in ('Vertical', 'Horizontal'):
        name = f'{orient}.TScrollbar'
        style.layout(name, [(f'{orient}.Scrollbar.trough', {'sticky': 'nswe', 'children': [
            (f'{orient}.Scrollbar.thumb', {'expand': '1', 'sticky': 'nswe'})]})])
        _flat(style, name, '#D4D4CF', CARD, troughcolor=CARD, gripcount=0, arrowsize=10)
        style.map(name, background=[('active', '#BABAB4')], lightcolor=[('active', '#BABAB4')],
                  darkcolor=[('active', '#BABAB4')])

    root.option_add('*TCombobox*Listbox.font', fonts.body)
    return fonts


class StepBadge(tk.Canvas):
    """Small round badge with a step number; plum when the step is available, grey otherwise."""

    SIZE = 22

    def __init__(self, parent, number, fonts, active=True):
        super().__init__(parent, width=self.SIZE, height=self.SIZE, background=CARD,
                         highlightthickness=0, borderwidth=0)
        self._oval = self.create_oval(1, 1, self.SIZE - 1, self.SIZE - 1, outline='')
        self._text = self.create_text(self.SIZE / 2, self.SIZE / 2, text=str(number), font=fonts.small_bold)
        self.set_active(active)

    def set_active(self, active):
        self.itemconfigure(self._oval, fill=ACCENT if active else DISABLED_BG)
        self.itemconfigure(self._text, fill='white' if active else MUTED)


class StatusDot(tk.Canvas):
    COLORS = {'idle': FAINT, 'busy': ACCENT, 'ok': SUCCESS, 'error': ERROR}

    def __init__(self, parent):
        super().__init__(parent, width=10, height=10, background=CARD, highlightthickness=0, borderwidth=0)
        self._dot = self.create_oval(1, 1, 9, 9, outline='')
        self.set('idle')

    def set(self, state):
        self.itemconfigure(self._dot, fill=self.COLORS[state])


class ScrollableFrame(ttk.Frame):
    """Frame that grows a slim scrollbar only when its content is taller than the window."""

    def __init__(self, parent, style='TFrame', padding=0):
        super().__init__(parent, style=style)
        bg = ttk.Style(self).lookup(style, 'background')
        self.canvas = tk.Canvas(self, background=bg, highlightthickness=0, borderwidth=0)
        self.scrollbar = ttk.Scrollbar(self, orient='vertical', command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.grid(row=0, column=0, sticky='nsew')
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.inner = ttk.Frame(self.canvas, style=style, padding=padding)
        self._window = self.canvas.create_window((0, 0), window=self.inner, anchor='nw')
        self.inner.bind('<Configure>', self._on_content)
        self.canvas.bind('<Configure>', self._on_canvas)
        self.bind('<Enter>', lambda e: self._bind_wheel(True))
        self.bind('<Leave>', self._on_leave)

    def _on_content(self, event):
        self.canvas.configure(scrollregion=self.canvas.bbox('all'), width=self.inner.winfo_reqwidth())
        self._update_scrollbar()

    def _on_canvas(self, event):
        self.canvas.itemconfigure(self._window, width=event.width)
        self._update_scrollbar()

    def _needs_scroll(self):
        return self.inner.winfo_reqheight() > self.canvas.winfo_height() + 1

    def _update_scrollbar(self):
        if self._needs_scroll():
            self.scrollbar.grid(row=0, column=1, sticky='ns')
        else:
            self.scrollbar.grid_remove()
            self.canvas.yview_moveto(0)

    def _on_leave(self, event):
        # <Leave> also fires when the pointer moves onto a child widget
        widget = self.winfo_containing(*self.winfo_pointerxy())
        if widget is None or not str(widget).startswith(str(self)):
            self._bind_wheel(False)

    def _bind_wheel(self, on):
        if on:
            self.bind_all('<MouseWheel>', self._on_wheel, add=False)
            self.bind_all('<Button-4>', lambda e: self._scroll(-1))
            self.bind_all('<Button-5>', lambda e: self._scroll(1))
        else:
            for seq in ('<MouseWheel>', '<Button-4>', '<Button-5>'):
                self.unbind_all(seq)

    def _on_wheel(self, event):
        self._scroll(-event.delta if sys.platform == 'darwin' else -event.delta // 120)

    def _scroll(self, step):
        if self._needs_scroll():
            self.canvas.yview_scroll(int(step), 'units')
