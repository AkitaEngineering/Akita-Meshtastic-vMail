import tkinter as tk
from tkinter import ttk

class StatusPanel:
    def __init__(self, parent, app):
        # Create status var and status bar label
        app.status_var = tk.StringVar(value="Status: Disconnected")
        status_bar = ttk.Label(parent, textvariable=app.status_var, relief=tk.SUNKEN, anchor=tk.W, style="Status.TLabel")
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        self.frame = status_bar
