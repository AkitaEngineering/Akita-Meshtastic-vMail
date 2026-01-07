import tkinter as tk
from tkinter import ttk
import logging


def setup_styles(app):
    """Apply theme, colors, and style configuration to the given app instance.
    Sets style attributes on `app` (bg_color, accent_color, etc.) and creates
    a `ttk.Style()` instance at `app.style`.
    """
    app.bg_color = "#F0F4F8"
    app.accent_color = "#2980B9"
    app.button_color = "#3498DB"
    app.text_color = "#2C3E50"
    app.list_bg = "#ECF0F1"
    app.log_bg = "#FFFFFF"
    app.status_bg = "#BDC3C7"
    app.error_color = "#E74C3C"

    try:
        app.master.configure(bg=app.bg_color)
    except Exception:
        pass

    app.style = ttk.Style()
    try:
        app.style.theme_use('clam')
    except tk.TclError:
        app.log("Clam theme not available, using default.", logging.WARNING)

    app.style.configure("TFrame", background=app.bg_color)
    app.style.configure("TLabel", background=app.bg_color, foreground=app.text_color, font=("Arial", 10))
    app.style.configure("Header.TLabel", font=("Arial", 16, "bold"), foreground=app.accent_color)
    app.style.configure("Status.TLabel", font=("Arial", 9), foreground=app.text_color, background=app.status_bg, padding=3)
    app.style.configure("TButton", font=("Arial", 10, "bold"), foreground="white", background=app.button_color, borderwidth=1, padding=(5, 3))
    app.style.map("TButton", background=[('active', app.accent_color), ('disabled', '#a0a0a0')], foreground=[('disabled', '#d0d0d0')])
    app.style.configure("TLabelframe", background=app.bg_color, bordercolor=app.accent_color, relief=tk.GROOVE, padding=5)
    app.style.configure("TLabelframe.Label", background=app.bg_color, foreground=app.accent_color, font=("Arial", 11, "bold"))
    app.style.configure("TCombobox", font=("Arial", 10), padding=2)
    app.style.configure("TEntry", font=("Arial", 10), padding=2)

    # Listbox styling via option_add
    try:
        app.master.option_add('*Listbox.background', app.list_bg)
        app.master.option_add('*Listbox.foreground', app.text_color)
        app.master.option_add('*Listbox.font', ('Arial', 10))
        app.master.option_add('*Listbox.borderwidth', 0)
        app.master.option_add('*Listbox.highlightThickness', 1)
        app.master.option_add('*Listbox.highlightColor', app.accent_color)
        app.master.option_add('*Listbox.selectBackground', app.accent_color)
        app.master.option_add('*Listbox.selectForeground', 'white')

        # ScrolledText styling via option_add
        app.master.option_add('*ScrolledText.background', app.log_bg)
        app.master.option_add('*ScrolledText.foreground', app.text_color)
        app.master.option_add('*ScrolledText.font', ('Courier New', 9))
        app.master.option_add('*ScrolledText.borderwidth', 0)
        app.master.option_add('*ScrolledText.highlightThickness', 0)
    except Exception:
        pass
