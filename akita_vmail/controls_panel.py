import tkinter as tk
from tkinter import ttk

class ControlsPanel:
    def __init__(self, parent, app):
        """Create voice controls and attach widgets to `app` for compatibility."""
        voice_frame_container = ttk.LabelFrame(parent, text="Controls", padding="10")
        voice_frame_container.pack(fill=tk.X, pady=10)
        voice_frame = ttk.Frame(voice_frame_container)
        voice_frame.pack()

        # Buttons: record, send, play, stop, test
        app.record_button = ttk.Button(voice_frame, text="🎤 Record", command=app.toggle_recording, width=12)
        app.record_button.pack(side=tk.LEFT, padx=5, pady=5)
        app.send_button = ttk.Button(voice_frame, text="✉️ Send", command=app.send_voice_message, width=10)
        app.send_button.pack(side=tk.LEFT, padx=5, pady=5)
        app.play_button = ttk.Button(voice_frame, text="▶ Play", command=app.play_selected_message, width=8)
        app.play_button.pack(side=tk.LEFT, padx=5, pady=5)
        app.stop_button = ttk.Button(voice_frame, text="⏹ Stop", command=app.stop_playback, width=8)
        app.stop_button.pack(side=tk.LEFT, padx=5, pady=5)
        app.test_button = ttk.Button(voice_frame, text="🧪 Test Send", command=app.send_test_message, width=12)
        app.test_button.pack(side=tk.LEFT, padx=(20,5), pady=5)

        self.frame = voice_frame_container
