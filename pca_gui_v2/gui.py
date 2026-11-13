"""Tkinter window for running PCA on a CSV of spectra, in two steps.

Step 1 "Run PCA" shows the eigenspectra and scores of every PC.
Step 2 "Reconstruct" then uses the PCs you tick after inspecting them.
"""
import os
import queue
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import matplotlib
matplotlib.use('TkAgg')
import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.cm import ScalarMappable
from matplotlib.colors import Normalize
from matplotlib.figure import Figure
from matplotlib.ticker import AutoMinorLocator, MaxNLocator

import plots
import theme
from analysis import PCASettings, run_pca_step, run_reconstruction
from data_loader import load_spectra_csv
from style import NATURE_RC, SUNSET_RAMP, ramp_colors

GRID_ROW_PX = 95   # height of one PC row in the results tab

# The Nature style, with text enlarged for reading on screen. Only keys of
# NATURE_RC are changed, so the saved figures (drawn inside NATURE_RC) are unaffected.
SCREEN_RC = {**NATURE_RC, 'font.size': 9, 'axes.labelsize': 10, 'axes.titlesize': 10,
             'xtick.labelsize': 9, 'ytick.labelsize': 9, 'legend.fontsize': 8.5,
             'axes.linewidth': 0.8, 'lines.linewidth': 1.1}


def results_subfolder_name(s):
    return f"PCA_{s.wn_min:g}-{s.wn_max:g}cm-1_spectra{s.first_spectrum}-{s.last_spectrum}"


def format_wavenumber(value):
    """Shortest text that reads back as exactly this number (all decimals of the file, no float noise)."""
    return np.format_float_positional(float(value), trim='-')


class PCAApp:
    def __init__(self, root):
        self.root = root
        self.root.title("PCA of spectra")
        self.root.minsize(1000, 640)
        self.fonts = theme.apply_theme(root)
        matplotlib.rcParams.update(SCREEN_RC)

        self.data = None
        self.pca_run = None          # result of step 1
        self.last_output = None
        self.pc_vars = []            # one BooleanVar per PC checkbox
        self.grid_canvas = None
        self.grid_width = 0
        self.messages = queue.Queue()

        self.csv_var = tk.StringVar()
        self.output_var = tk.StringVar()
        self.first_var = tk.StringVar(value='1')
        self.last_var = tk.StringVar()
        self.wn_min_var = tk.StringVar()
        self.wn_max_var = tk.StringVar()
        self.time_var = tk.StringVar(value='1.1')
        self.n_show_var = tk.StringVar(value='15')
        self.plots_3d_var = tk.BooleanVar(value=False)

        self._build_widgets()
        self.root.after(100, self._poll_messages)

    # ---------- layout ----------

    def _build_widgets(self):
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(0, weight=1)

        # Left: the four steps, scrollable if the window is short
        sidebar = theme.ScrollableFrame(self.root, padding=(20, 18, 14, 8))
        sidebar.grid(row=0, column=0, sticky='ns')
        left = sidebar.inner

        header = ttk.Frame(left)
        header.pack(fill='x', pady=(0, 14))
        ttk.Label(header, text="PCA of spectra", style='Title.TLabel').pack(anchor='w')
        ttk.Label(header, text="Principal component analysis of time-resolved spectra",
                  style='Subtitle.TLabel').pack(anchor='w', pady=(2, 0))

        # 1. Files
        files, _ = self._card(left, 1, "Files")
        files.columnconfigure(0, weight=1)
        ttk.Label(files, text="Spectra (CSV)", style='Field.Card.TLabel').grid(row=1, column=0, columnspan=2, sticky='w')
        ttk.Entry(files, textvariable=self.csv_var, width=30).grid(row=2, column=0, sticky='ew', pady=(3, 0))
        ttk.Button(files, text="Browse…", command=self._choose_csv).grid(row=2, column=1, padx=(6, 0), pady=(3, 0))
        ttk.Label(files, text="Save results in", style='Field.Card.TLabel').grid(
            row=3, column=0, columnspan=2, sticky='w', pady=(10, 0))
        ttk.Entry(files, textvariable=self.output_var, width=30).grid(row=4, column=0, sticky='ew', pady=(3, 0))
        ttk.Button(files, text="Browse…", command=self._choose_output).grid(row=4, column=1, padx=(6, 0), pady=(3, 0))
        self.file_info = ttk.Label(files, text="No file loaded", style='Muted.Card.TLabel')
        self.file_info.grid(row=5, column=0, columnspan=2, sticky='w', pady=(8, 0))

        # 2. Data selection
        sel, _ = self._card(left, 2, "Data to use")
        sel.columnconfigure(0, weight=1)
        self._range_row(sel, 1, "Spectra", self.first_var, self.last_var, "")
        self.wn_boxes = self._range_row(sel, 2, "Wavenumber", self.wn_min_var, self.wn_max_var, "cm⁻¹",
                                        dropdown=True)
        ttk.Button(sel, text="Update preview", command=self._update_preview).grid(
            row=3, column=0, columnspan=5, sticky='w', pady=(10, 0))

        # 3. PCA
        opts, _ = self._card(left, 3, "Principal component analysis")
        opts.columnconfigure(0, weight=1)
        self._field_row(opts, 1, "Time per spectrum", self.time_var, "s")
        self._field_row(opts, 2, "PCs to inspect", self.n_show_var, "")
        ttk.Checkbutton(opts, text="Also make 3D plots (slower)", variable=self.plots_3d_var,
                        style='Card.TCheckbutton').grid(row=3, column=0, columnspan=3, sticky='w', pady=(8, 0))
        self.run_btn = ttk.Button(opts, text="Run PCA", style='Accent.TButton', command=self._start_pca)
        self.run_btn.grid(row=4, column=0, columnspan=3, sticky='ew', pady=(12, 0))

        # 4. Reconstruction (enabled after step 3)
        self.recon_frame, self.recon_badge = self._card(left, 4, "Reconstruct with selected PCs", active=False)
        self.recon_frame.columnconfigure(0, weight=1)
        self.recon_hint = ttk.Label(self.recon_frame, style='Muted.Card.TLabel', wraplength=330, justify='left',
                                    text="Run PCA first, inspect the eigenspectra and scores, "
                                         "then tick the PCs to keep here.")
        self.recon_hint.grid(row=1, column=0, sticky='w')
        self.pc_tools = ttk.Frame(self.recon_frame, style='Card.TFrame')
        ttk.Button(self.pc_tools, text="Select all", style='Link.TButton',
                   command=lambda: self._select_pcs(True)).pack(side='left')
        ttk.Label(self.pc_tools, text="·", style='Muted.Card.TLabel').pack(side='left', padx=6)
        ttk.Button(self.pc_tools, text="None", style='Link.TButton',
                   command=lambda: self._select_pcs(False)).pack(side='left')
        self.pc_box = ttk.Frame(self.recon_frame, style='Card.TFrame')
        self.pc_box.grid(row=3, column=0, sticky='ew', pady=(6, 0))
        self.recon_btn = ttk.Button(self.recon_frame, text="Reconstruct", style='Accent.TButton',
                                    command=self._start_reconstruction, state='disabled')
        self.recon_btn.grid(row=4, column=0, sticky='ew', pady=(12, 0))

        # Right: tabs on a white page
        right = ttk.Frame(self.root, padding=(6, 18, 20, 12))
        right.grid(row=0, column=1, sticky='nsew')
        self.tabs = ttk.Notebook(right)
        self.tabs.pack(fill='both', expand=True)
        preview_tab = ttk.Frame(self.tabs, style='Card.TFrame', padding=8)
        self.results_tab = ttk.Frame(self.tabs, style='Card.TFrame', padding=(8, 8, 2, 8))
        log_tab = ttk.Frame(self.tabs, style='Card.TFrame', padding=1)
        self.tabs.add(preview_tab, text="Data preview")
        self.tabs.add(self.results_tab, text="PCA results")
        self.tabs.add(log_tab, text="Log")

        self.fig = Figure(figsize=(5, 4), facecolor=theme.CARD, layout='constrained')
        gs = self.fig.add_gridspec(1, 2, width_ratios=[40, 1])
        self.ax = self.fig.add_subplot(gs[0, 0])
        self.cax = self.fig.add_subplot(gs[0, 1])
        self.canvas = FigureCanvasTkAgg(self.fig, master=preview_tab)
        self.canvas.get_tk_widget().configure(background=theme.CARD, highlightthickness=0)
        self.canvas.get_tk_widget().pack(fill='both', expand=True)
        self._draw_empty_preview()

        # Scrollable area for the eigenspectra/scores grid
        self.scroll_canvas = tk.Canvas(self.results_tab, background=theme.CARD, highlightthickness=0)
        grid_scroll = ttk.Scrollbar(self.results_tab, orient='vertical', command=self.scroll_canvas.yview)
        self.scroll_canvas.configure(yscrollcommand=grid_scroll.set)
        grid_scroll.pack(side='right', fill='y')
        self.scroll_canvas.pack(side='left', fill='both', expand=True)
        self.grid_holder = tk.Frame(self.scroll_canvas, background=theme.CARD)
        self.scroll_canvas.create_window((0, 0), window=self.grid_holder, anchor='nw')
        self.grid_holder.bind('<Configure>', lambda e: self.scroll_canvas.configure(
            scrollregion=self.scroll_canvas.bbox('all')))
        self.scroll_canvas.bind('<Configure>', self._on_results_resize)
        self._empty_message(self.grid_holder, "No results yet",
                            "Run PCA (step 3) to see the eigenspectrum and scores of each PC here.")

        # Log
        self.log_text = tk.Text(log_tab, wrap='word', state='disabled', relief='flat', borderwidth=0,
                                highlightthickness=0, background=theme.LOG_BG, foreground=theme.INK,
                                font=self.fonts.mono, padx=14, pady=10, spacing1=1, spacing3=3)
        self.log_text.tag_configure('time', foreground=theme.FAINT)
        self.log_text.tag_configure('error', foreground=theme.ERROR)
        scroll = ttk.Scrollbar(log_tab, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right', fill='y')
        self.log_text.pack(side='left', fill='both', expand=True)

        # Bottom status bar
        tk.Frame(self.root, background=theme.BORDER, height=1).grid(row=1, column=0, columnspan=2, sticky='ew')
        status = ttk.Frame(self.root, style='Card.TFrame', padding=(20, 7, 20, 7))
        status.grid(row=2, column=0, columnspan=2, sticky='ew')
        self.status_dot = theme.StatusDot(status)
        self.status_dot.pack(side='left')
        self.status_label = ttk.Label(status, text="Ready. Choose a CSV file to begin.", style='Status.TLabel')
        self.status_label.pack(side='left', padx=(8, 0))
        self.open_btn = ttk.Button(status, text="Open results folder", command=self._open_output, state='disabled')
        self.open_btn.pack(side='right')
        self.busy = ttk.Progressbar(status, mode='indeterminate', length=140, style='Thin.Horizontal.TProgressbar')

    def _card(self, parent, number, title, active=True):
        """White panel with a numbered heading. Returns (body frame, badge); content goes in rows >= 1."""
        outer = tk.Frame(parent, background=theme.CARD, highlightthickness=1,
                         highlightbackground=theme.BORDER, highlightcolor=theme.BORDER)
        outer.pack(fill='x', pady=(0, 12))
        body = ttk.Frame(outer, style='Card.TFrame', padding=(16, 14, 16, 16))
        body.pack(fill='both', expand=True)
        head = ttk.Frame(body, style='Card.TFrame')
        head.grid(row=0, column=0, columnspan=5, sticky='ew', pady=(0, 12))
        badge = theme.StepBadge(head, number, self.fonts, active=active)
        badge.pack(side='left')
        ttk.Label(head, text=title, style='Heading.Card.TLabel').pack(side='left', padx=(10, 0))
        return body, badge

    def _empty_message(self, parent, title, text):
        box = tk.Frame(parent, background=theme.CARD)
        box.pack(padx=40, pady=60, anchor='w')
        tk.Label(box, text=title, background=theme.CARD, foreground=theme.INK,
                 font=self.fonts.body_bold).pack(anchor='w')
        tk.Label(box, text=text, background=theme.CARD, foreground=theme.MUTED,
                 font=self.fonts.small).pack(anchor='w', pady=(4, 0))

    def _range_row(self, parent, row, label, var_a, var_b, unit, dropdown=False):
        """Two fields 'from – to'. dropdown=True: click to pick from a scrollable list instead of typing.

        Returns the two widgets.
        """
        pady = (0 if row == 1 else 8, 0)
        ttk.Label(parent, text=label, style='Field.Card.TLabel').grid(row=row, column=0, sticky='w', pady=pady)
        widgets = []
        for col, var in ((1, var_a), (3, var_b)):
            if dropdown:
                widget = ttk.Combobox(parent, textvariable=var, width=9, justify='right', state='readonly',
                                      height=18)
                widget.bind('<<ComboboxSelected>>', self._on_wavenumber_picked)
            else:
                widget = ttk.Entry(parent, textvariable=var, width=8, justify='right')
                widget.bind('<Return>', lambda e: self._update_preview())
            widget.grid(row=row, column=col, pady=pady)
            widgets.append(widget)
        ttk.Label(parent, text="–", style='Field.Card.TLabel').grid(row=row, column=2, padx=6, pady=pady)
        ttk.Label(parent, text=unit, style='Field.Card.TLabel', width=5).grid(
            row=row, column=4, sticky='w', padx=(6, 0), pady=pady)
        return widgets

    def _on_wavenumber_picked(self, event):
        event.widget.selection_clear()
        self._update_preview()

    def _field_row(self, parent, row, label, var, unit):
        pady = (0 if row == 1 else 8, 0)
        ttk.Label(parent, text=label, style='Field.Card.TLabel').grid(row=row, column=0, sticky='w', pady=pady)
        ttk.Entry(parent, textvariable=var, width=8, justify='right').grid(row=row, column=1, sticky='e', pady=pady)
        ttk.Label(parent, text=unit, style='Field.Card.TLabel', width=5).grid(
            row=row, column=2, sticky='w', padx=(6, 0), pady=pady)

    def _select_pcs(self, value):
        for var in self.pc_vars:
            var.set(value)

    # ---------- file selection ----------

    def _choose_csv(self):
        path = filedialog.askopenfilename(
            title="Select the CSV file with spectra",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if path:
            self.csv_var.set(path)
            self._load_csv(path)

    def _choose_output(self):
        folder = filedialog.askdirectory(title="Select where to save the results")
        if folder:
            self.output_var.set(folder)

    def _load_csv(self, path):
        try:
            self.root.config(cursor='watch')
            self.root.update_idletasks()
            self.data = load_spectra_csv(path)
        except Exception as e:
            self.data = None
            messagebox.showerror("Could not read file", str(e))
            return
        finally:
            self.root.config(cursor='')

        wn = self.data.wavenumbers
        self.first_var.set('1')
        self.last_var.set(str(self.data.n_spectra))
        # Every wavenumber of the file, exactly as stored, high to low (IR convention)
        choices = [format_wavenumber(v) for v in np.sort(wn)[::-1]]
        for box in self.wn_boxes:
            box.configure(values=choices)
        self.wn_min_var.set(format_wavenumber(wn.min()))
        self.wn_max_var.set(format_wavenumber(wn.max()))
        if not self.output_var.get():
            self.output_var.set(os.path.dirname(path))
        self.file_info.configure(
            text=f"{self.data.n_spectra} spectra · {len(wn)} wavenumbers · "
                 f"{wn.min():.0f}–{wn.max():.0f} cm⁻¹", foreground=theme.INK)
        self._log(f"Loaded {os.path.basename(path)}", state='ok')
        self.tabs.select(0)
        self._update_preview()

    # ---------- settings ----------

    def _read_settings(self):
        """Validate the form. Returns PCASettings or None (after showing an error)."""
        if self.data is None:
            messagebox.showerror("No data", "Please select a CSV file first.")
            return None
        try:
            settings = PCASettings(
                csv_path=self.csv_var.get(),
                output_folder='',
                first_spectrum=int(self.first_var.get()),
                last_spectrum=int(self.last_var.get()),
                wn_min=float(self.wn_min_var.get()),
                wn_max=float(self.wn_max_var.get()),
                time_per_spectrum=float(self.time_var.get()),
                n_pcs_to_show=int(self.n_show_var.get()),
                make_3d_plots=self.plots_3d_var.get(),
            )
        except ValueError:
            messagebox.showerror("Invalid input", "Please check that all numeric fields contain numbers.")
            return None
        if settings.wn_min > settings.wn_max:
            settings.wn_min, settings.wn_max = settings.wn_max, settings.wn_min
        return settings

    # ---------- preview ----------

    def _draw_empty_preview(self):
        self.ax.clear()
        self.ax.axis('off')
        self.cax.set_visible(False)
        self.ax.text(0.5, 0.52, "No data loaded", ha='center', va='center', transform=self.ax.transAxes,
                     color=theme.INK, fontsize=11, fontweight='bold')
        self.ax.text(0.5, 0.45, "Choose a CSV file in step 1 to preview the spectra.", ha='center', va='center',
                     transform=self.ax.transAxes, color=theme.MUTED, fontsize=9.5)
        self.canvas.draw()

    def _update_preview(self):
        if self.data is None:
            return
        try:
            first = int(self.first_var.get())
            last = int(self.last_var.get())
            lo, hi = sorted((float(self.wn_min_var.get()), float(self.wn_max_var.get())))
        except ValueError:
            return
        first = max(1, min(first, self.data.n_spectra))
        last = max(first, min(last, self.data.n_spectra))

        wn = self.data.wavenumbers
        spectra = self.data.spectra[first - 1:last]
        ax = self.ax
        ax.clear()
        ax.axis('on')

        # Up to 12 evenly spaced spectra from the selection, coloured by spectrum number
        picks = np.unique(np.linspace(0, len(spectra) - 1, min(12, len(spectra))).astype(int))
        for color, i in zip(ramp_colors(len(picks)), picks):
            ax.plot(wn, spectra[i], color=color, lw=0.9)

        # Selected region (only marked when it is part of the data): soft band, thin edges, label on top
        if lo > wn.min() or hi < wn.max():
            ax.axvspan(lo, hi, color=theme.ACCENT_SOFT, zorder=0, lw=0)
            for edge in (lo, hi):
                ax.axvline(edge, color='#9C8BC0', lw=0.8, ls=(0, (3, 2)), zorder=1)
            ax.text((max(lo, wn.min()) + min(hi, wn.max())) / 2, 1.0, "PCA region",
                    transform=ax.get_xaxis_transform(), ha='center', va='bottom', fontsize=8, color=theme.ACCENT)

        ax.set_xlim(wn.max(), wn.min())
        ax.set_xlabel(plots.WN_LABEL)
        ax.set_ylabel('Absorbance (a.u.)')
        ax.xaxis.set_minor_locator(AutoMinorLocator())
        ax.yaxis.set_minor_locator(AutoMinorLocator())
        ax.set_title(f"Spectra {first}–{last}  ({last - first + 1} selected)", loc='left', pad=14,
                     fontsize=10.5, fontweight='bold')
        ax.set_title(f"Region {lo:g}–{hi:g} cm$^{{-1}}$", loc='right', pad=14, color=theme.MUTED, fontsize=9)

        # Colour bar: which spectrum each colour is
        self.cax.clear()
        self.cax.set_visible(True)
        cbar = self.fig.colorbar(ScalarMappable(norm=Normalize(first, max(last, first + 1)), cmap=SUNSET_RAMP),
                                 cax=self.cax)
        cbar.set_label('Spectrum number')
        cbar.outline.set_visible(False)
        cbar.ax.tick_params(width=0.6, length=2.5)
        cbar.ax.yaxis.set_major_locator(MaxNLocator(nbins=5, integer=True))
        self.canvas.draw_idle()

    # ---------- PCA results tab ----------

    def _show_pca_results(self):
        """Draw the eigenspectra/scores grid and build the PC checkboxes."""
        self.tabs.select(1)
        self.root.update_idletasks()
        self._draw_pc_grid()

        run = self.pca_run
        for child in self.pc_box.winfo_children():
            child.destroy()
        self.pc_vars = []
        colors = ramp_colors(run.n_show)
        n_cols = 3
        for c in range(n_cols):
            self.pc_box.columnconfigure(c, weight=1, uniform='pc')
        for i in range(run.n_show):
            var = tk.BooleanVar(value=False)
            self.pc_vars.append(var)
            self._pc_chip(i, var, colors[i], run.result.explained_variance[i]).grid(
                row=i // n_cols, column=i % n_cols, sticky='w', pady=2)
        s = run.settings
        self.recon_hint.configure(
            foreground=theme.INK,
            text=f"PCA of spectra {s.first_spectrum}–{s.last_spectrum}, {s.wn_min:g}–{s.wn_max:g} cm⁻¹. "
                 f"Tick the PCs to keep:")
        self.pc_tools.grid(row=2, column=0, sticky='w', pady=(6, 0))
        self.recon_badge.set_active(True)
        self.recon_btn.configure(state='normal')

    def _pc_chip(self, i, var, color, variance):
        """Checkbox + line swatch in the PC's plot colour + 'PC n' + explained variance."""
        chip = ttk.Frame(self.pc_box, style='Card.TFrame')
        ttk.Checkbutton(chip, variable=var, style='Card.TCheckbutton').pack(side='left')
        swatch = tk.Canvas(chip, width=12, height=10, background=theme.CARD, highlightthickness=0, borderwidth=0)
        swatch.create_line(0, 5, 12, 5, fill=matplotlib.colors.to_hex(color), width=2.5)
        swatch.pack(side='left', padx=(0, 5))
        name = ttk.Label(chip, text=f"PC {i + 1}", style='Small.Card.TLabel')
        name.pack(side='left')
        pct = ttk.Label(chip, text=plots.format_percent(variance), style='Muted.Card.TLabel')
        pct.pack(side='left', padx=(4, 0))
        for w in (swatch, name, pct):
            w.bind('<Button-1>', lambda e: var.set(not var.get()))
        return chip

    def _draw_pc_grid(self):
        run = self.pca_run
        if run is None:
            return
        for child in self.grid_holder.winfo_children():
            child.destroy()
        width_px = max(400, self.scroll_canvas.winfo_width())
        self.grid_width = width_px
        dpi = 100
        n = run.n_show
        fig = Figure(figsize=(width_px / dpi, (70 + GRID_ROW_PX * n) / dpi), dpi=dpi, facecolor=theme.CARD)
        plots.draw_pc_grid(fig, run.selection.wavenumbers, run.time, run.result, n, label_size=9)
        fig.subplots_adjust(left=0.11, right=0.98, top=1 - 25 / (70 + GRID_ROW_PX * n),
                            bottom=48 / (70 + GRID_ROW_PX * n))
        self.grid_canvas = FigureCanvasTkAgg(fig, master=self.grid_holder)
        widget = self.grid_canvas.get_tk_widget()
        widget.configure(background=theme.CARD, highlightthickness=0)
        widget.pack()
        self.grid_canvas.draw()
        for w in (widget, self.scroll_canvas):
            w.bind('<MouseWheel>', self._on_mousewheel)
            w.bind('<Button-4>', lambda e: self.scroll_canvas.yview_scroll(-1, 'units'))
            w.bind('<Button-5>', lambda e: self.scroll_canvas.yview_scroll(1, 'units'))

    def _on_results_resize(self, event):
        # Redraw the grid at the new width (debounced)
        if self.pca_run is not None and abs(event.width - self.grid_width) > 40:
            if hasattr(self, '_resize_job'):
                self.root.after_cancel(self._resize_job)
            self._resize_job = self.root.after(300, self._draw_pc_grid)

    def _on_mousewheel(self, event):
        step = -event.delta if sys.platform == 'darwin' else -event.delta // 120
        self.scroll_canvas.yview_scroll(int(step), 'units')

    # ---------- running ----------

    def _start_pca(self):
        settings = self._read_settings()
        if settings is None:
            return
        base = self.output_var.get().strip() or os.path.dirname(settings.csv_path)
        settings.output_folder = os.path.join(base, results_subfolder_name(settings))
        if os.path.isdir(settings.output_folder) and not messagebox.askyesno(
                "Overwrite?", f"{settings.output_folder}\nalready exists. Overwrite the results in it?"):
            return
        self._update_preview()
        self._run_in_background(self._pca_job, settings)

    def _start_reconstruction(self):
        pcs = [i + 1 for i, var in enumerate(self.pc_vars) if var.get()]
        if not pcs:
            messagebox.showerror("No PCs selected", "Tick at least one PC to reconstruct with.")
            return
        self._run_in_background(self._reconstruction_job, pcs, self.plots_3d_var.get())

    def _run_in_background(self, job, *args):
        self.run_btn.configure(state='disabled')
        self.recon_btn.configure(state='disabled')
        self.busy.pack(side='right', padx=(0, 16))
        self.busy.start(10)
        self.status_dot.set('busy')
        threading.Thread(target=job, args=args, daemon=True).start()

    def _send_log(self, msg):
        self.messages.put(('log', msg))

    def _pca_job(self, settings):
        try:
            run = run_pca_step(settings, log=self._send_log, data=self.data)
            self.messages.put(('pca_done', run))
        except Exception as e:
            self.messages.put(('error', str(e)))

    def _reconstruction_job(self, pcs, make_3d):
        try:
            folder = run_reconstruction(self.pca_run, pcs, make_3d_plots=make_3d, log=self._send_log)
            self.messages.put(('recon_done', folder))
        except Exception as e:
            self.messages.put(('error', str(e)))

    def _poll_messages(self):
        """Apply updates sent from the worker thread (Tk is not thread-safe)."""
        try:
            while True:
                kind, payload = self.messages.get_nowait()
                if kind == 'log':
                    self._log(payload)
                elif kind == 'pca_done':
                    self.pca_run = payload
                    self._finish(payload.output_folder)
                    self._show_pca_results()
                    self._log("PCA done. Inspect the results, then tick PCs in step 4 to reconstruct.", state='ok')
                elif kind == 'recon_done':
                    self._finish(payload)
                    self._log("Reconstruction finished.", state='ok')
                    messagebox.showinfo("Done", f"Reconstruction saved in:\n{payload}")
                elif kind == 'error':
                    self._log(f"Error: {payload}", state='error')
                    self._finish(None)
                    messagebox.showerror("Error", payload)
        except queue.Empty:
            pass
        self.root.after(100, self._poll_messages)

    def _finish(self, output_folder):
        self.busy.stop()
        self.busy.pack_forget()
        self.run_btn.configure(state='normal')
        if self.pca_run is not None:
            self.recon_btn.configure(state='normal')
        if output_folder:
            self.last_output = output_folder
            self.open_btn.configure(state='normal')

    def _open_output(self):
        if not self.last_output:
            return
        if sys.platform == 'darwin':
            subprocess.run(['open', self.last_output])
        elif sys.platform == 'win32':
            os.startfile(self.last_output)
        else:
            subprocess.run(['xdg-open', self.last_output])

    def _log(self, msg, state=None):
        """Add a line to the Log tab and show it in the status bar."""
        self.log_text.configure(state='normal')
        self.log_text.insert('end', time.strftime('%H:%M:%S  '), 'time')
        self.log_text.insert('end', msg + '\n', 'error' if state == 'error' else ())
        self.log_text.see('end')
        self.log_text.configure(state='disabled')
        first_line = msg.strip().splitlines()[0] if msg.strip() else ''
        self.status_label.configure(text=first_line,
                                    foreground=theme.ERROR if state == 'error' else theme.MUTED)
        if state:
            self.status_dot.set(state)


def main():
    root = tk.Tk()
    PCAApp(root)
    root.mainloop()
