import tkinter as tk
from tkinter import ttk

class ConnectionPanel:
    def __init__(self, parent, app):
        """Create Connection controls and attach widgets to `app` for compatibility."""
        settings_frame = ttk.LabelFrame(parent, text="Connection", padding="10")
        settings_frame.pack(side=tk.LEFT, padx=(0, 10), fill=tk.Y, anchor='nw')
        ttk.Label(settings_frame, text="Target:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        target_frame = ttk.Frame(settings_frame)
        target_frame.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5, pady=5)

        # populate app attributes used elsewhere
        app.com_ports = app.meshtastic_handler.get_available_ports()
        app.connect_target_var = tk.StringVar()
        app.connect_target_entry = ttk.Entry(target_frame, textvariable=app.connect_target_var, width=18)
        if app.com_ports:
            app.connect_target_var.set(app.com_ports[0])
        app.connect_target_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Refresh and connect buttons reference app methods
        refresh_button = ttk.Button(target_frame, text="⟳", width=3, command=app.refresh_ports)
        refresh_button.pack(side=tk.LEFT, padx=(5, 0))
        app.connect_button = ttk.Button(settings_frame, text="Connect", command=app.toggle_connection, width=10)
        app.connect_button.grid(row=0, column=2, padx=(10, 5), pady=5)

        # Keep frames accessible if needed
        self.frame = settings_frame


