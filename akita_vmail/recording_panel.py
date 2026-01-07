import tkinter as tk
from tkinter import ttk

class RecordingPanel:
    def __init__(self, parent, app):
        """Create recording controls and attach variables/widgets to `app`."""
        recording_frame = ttk.LabelFrame(parent, text="Recording", padding="10")
        recording_frame.pack(side=tk.LEFT, padx=10, fill=tk.Y, anchor='nw')

        audio_cfg = app.config.get("audio", {})
        ttk.Label(recording_frame, text="Length (s):").grid(row=0, column=0, sticky=tk.W, padx=5, pady=3)
        app.recording_length_var = tk.StringVar(value=str(app.audio_handler.record_seconds))
        app.recording_length_entry = ttk.Entry(recording_frame, textvariable=app.recording_length_var, width=5)
        app.recording_length_entry.grid(row=0, column=1, sticky=tk.W, padx=5, pady=3)

        ttk.Label(recording_frame, text="Quality:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=3)
        app.compression_quality_var = tk.StringVar(value=app.audio_handler.default_quality)
        app.compression_quality_combo = ttk.Combobox(recording_frame, textvariable=app.compression_quality_var,
                                                    values=list(app.audio_handler.quality_rates.keys()), width=10, state="readonly")
        app.compression_quality_combo.grid(row=1, column=1, sticky=tk.W, padx=5, pady=3)

        # Chunk size chooser (values obtained via protocol getter to remain config-aware)
        ttk.Label(recording_frame, text="Chunk Size:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=3)
        try:
            from .protocol import get_chunk_sizes, get_default_chunk_size_key
            chunk_sizes = get_chunk_sizes(app.config)
            default_chunk_key = get_default_chunk_size_key(app.config)
            chunk_values = list(chunk_sizes.keys())
        except Exception:
            default_chunk_key = 'Medium'
            chunk_values = ['Small', 'Medium', 'Large']

        app.chunk_size_var = tk.StringVar(value=default_chunk_key)
        app.chunk_size_combo = ttk.Combobox(recording_frame, textvariable=app.chunk_size_var,
                                            values=chunk_values, width=10, state="readonly")
        app.chunk_size_combo.grid(row=2, column=1, sticky=tk.W, padx=5, pady=3)
        app.chunk_size_combo.bind("<<ComboboxSelected>>", app.update_chunk_size)

        self.frame = recording_frame
