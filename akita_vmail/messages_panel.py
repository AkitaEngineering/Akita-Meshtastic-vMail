import tkinter as tk
from tkinter import ttk, Frame, Listbox

class MessagesPanel:
    def __init__(self, parent, app):
        messages_frame = ttk.LabelFrame(parent, text="Messages", padding="10")
        messages_frame.pack(fill=tk.BOTH, expand=True, pady=5, ipady=5)
        list_container = Frame(messages_frame, bd=0)
        list_container.pack(fill=tk.BOTH, expand=True)
        app.messages_list = Listbox(list_container, height=10)
        app.messages_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        app.messages_list.bind('<<ListboxSelect>>', app.on_message_select)
        scrollbar = ttk.Scrollbar(list_container, orient=tk.VERTICAL, command=app.messages_list.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        app.messages_list.configure(yscrollcommand=scrollbar.set)
        self.frame = messages_frame
