import tkinter as tk
from tkinter import ttk

class HeaderPanel:
    def __init__(self, parent, app):
        header_label = ttk.Label(parent, text="Akita vMail", style="Header.TLabel", anchor=tk.CENTER)
        header_label.pack(fill=tk.X, pady=(0, 15))
        self.frame = header_label
