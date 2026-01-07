import tkinter as tk
from tkinter import ttk, scrolledtext

class LogPanel:
    def __init__(self, parent, app):
        log_frame = ttk.LabelFrame(parent, text="Log Output", padding="10")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 5), ipady=5, side=tk.BOTTOM)
        clear_log_button = ttk.Button(log_frame, text="Clear Log", command=app.clear_log_display, width=10)
        clear_log_button.pack(side=tk.RIGHT, anchor='ne', padx=5, pady=(0,5))
        app.log_display = scrolledtext.ScrolledText(log_frame, height=8, wrap=tk.WORD)
        app.log_display.pack(fill=tk.BOTH, expand=True)
        self.frame = log_frame
