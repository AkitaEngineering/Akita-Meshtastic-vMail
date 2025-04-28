# -*- coding: utf-8 -*-
"""
File: gui.py
Description: Defines the main Tkinter GUI application class (AkitaVmailApp)
             for the Meshtastic Voice Messenger. Handles user interaction,
             displays messages and logs, and coordinates the audio and
             meshtastic handlers. Reads config via protocol module.
"""
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, Listbox, Scrollbar, Frame
import queue
import threading
import time
import logging
import logging.handlers
import os
import uuid # For unique recording filenames
from datetime import datetime

# --- Import local modules ---
try:
    # Utils now loads config first
    from utils import log_to_gui, add_tooltip, setup_logging_queue, clear_scrolled_text, load_config
    # Protocol loads config and defines constants based on it
    from protocol import (
        PRIVATE_APP_PORT, CHUNK_SIZES, DEFAULT_CHUNK_SIZE_KEY, DEFAULT_CHUNK_SIZE,
        CHUNK_TIMEOUT, MSG_TYPE_VOICE_CHUNK, MSG_TYPE_ACK,
        MSG_TYPE_TEST, MSG_TYPE_COMPLETE_VOICE, verify_chunk_crc,
        verify_complete_voice_crc
    )
    # Audio handler also loads config for its defaults
    from audio_handler import AudioHandler
    from meshtastic_handler import MeshtasticHandler
except ImportError as e:
     print(f"FATAL ERROR: Could not import required local modules: {e}")
     print("Ensure utils.py, audio_handler.py, meshtastic_handler.py, and protocol.py are present.")
     exit(1)


class AkitaVmailApp:
    """Main application class for the Akita vMail GUI."""

    def __init__(self, master: tk.Tk):
        """Initialize the application."""
        self.master = master
        master.title("Akita vMail - Meshtastic Voice Messenger")
        master.geometry("750x750")
        master.minsize(650, 650)

        # --- Load Config ---
        # Config is loaded by utils and used by protocol/audio_handler implicitly now
        # We might need specific values here too
        self.config = load_config()
        audio_cfg = self.config.get("audio", {})
        chunk_cfg = self.config.get("chunking", {})

        # --- Internal State ---
        self.is_connected = False
        self.current_recording_path = None
        self.voice_messages = [] # List of dicts: {"description", "filepath", "from_id"}
        self.message_chunks = {} # Dict for reassembly: {chunk_id: {chunks, total, from_id, timestamp}}
        # Get chunk size default from loaded config via protocol constants
        self.max_chunk_size = DEFAULT_CHUNK_SIZE
        self.log_queue = queue.Queue()
        self.connected_node_info = "N/A" # Store connected node info string

        # --- Setup Logging ---
        self.log_display = None
        setup_logging_queue(self.log_queue)
        self.master.after(100, self.process_log_queue)

        # --- Initialize Handlers ---
        self.audio_handler = AudioHandler(self.log) # Gets config via its import
        self.meshtastic_handler = MeshtasticHandler(self.log_queue, self.handle_received_message)

        # --- UI Styling ---
        self._setup_styles()

        # --- Create Widgets ---
        self.create_widgets()

        # --- Periodic Tasks ---
        chunk_timeout_ms = int(chunk_cfg.get("receive_timeout_sec", 60) * 1000)
        self.master.after(chunk_timeout_ms, self.check_incomplete_chunks)

        # --- Cleanup on Close ---
        self.master.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.log("Akita vMail application initialized.")
        self.update_ui_state()


    def _setup_styles(self):
        """Configure ttk styles for the application."""
        self.bg_color = "#F0F4F8"
        self.accent_color = "#2980B9"
        self.button_color = "#3498DB"
        self.text_color = "#2C3E50"
        self.list_bg = "#ECF0F1"
        self.log_bg = "#FFFFFF"
        self.status_bg = "#BDC3C7"
        self.error_color = "#E74C3C"

        self.master.configure(bg=self.bg_color)
        self.style = ttk.Style()
        try: self.style.theme_use('clam')
        except tk.TclError: self.log("Clam theme not available, using default.", logging.WARNING)

        self.style.configure("TFrame", background=self.bg_color)
        self.style.configure("TLabel", background=self.bg_color, foreground=self.text_color, font=("Arial", 10))
        self.style.configure("Header.TLabel", font=("Arial", 16, "bold"), foreground=self.accent_color)
        self.style.configure("Status.TLabel", font=("Arial", 9), foreground=self.text_color, background=self.status_bg, padding=3)
        self.style.configure("TButton", font=("Arial", 10, "bold"), foreground="white", background=self.button_color, borderwidth=1, padding=(5, 3))
        self.style.map("TButton", background=[('active', self.accent_color), ('disabled', '#a0a0a0')], foreground=[('disabled', '#d0d0d0')])
        self.style.configure("TLabelframe", background=self.bg_color, bordercolor=self.accent_color, relief=tk.GROOVE, padding=5)
        self.style.configure("TLabelframe.Label", background=self.bg_color, foreground=self.accent_color, font=("Arial", 11, "bold"))
        self.style.configure("TCombobox", font=("Arial", 10), padding=2)
        self.style.configure("TEntry", font=("Arial", 10), padding=2)

        # Listbox styling via option_add
        self.master.option_add('*Listbox.background', self.list_bg)
        self.master.option_add('*Listbox.foreground', self.text_color)
        self.master.option_add('*Listbox.font', ('Arial', 10))
        self.master.option_add('*Listbox.borderwidth', 0)
        self.master.option_add('*Listbox.highlightThickness', 1)
        self.master.option_add('*Listbox.highlightColor', self.accent_color)
        self.master.option_add('*Listbox.selectBackground', self.accent_color)
        self.master.option_add('*Listbox.selectForeground', 'white')

        # ScrolledText styling via option_add
        self.master.option_add('*ScrolledText.background', self.log_bg)
        self.master.option_add('*ScrolledText.foreground', self.text_color)
        self.master.option_add('*ScrolledText.font', ('Courier New', 9))
        self.master.option_add('*ScrolledText.borderwidth', 0)
        self.master.option_add('*ScrolledText.highlightThickness', 0)


    def log(self, message: str, level=logging.INFO):
        """Log message via the root logger (queued)."""
        if level == logging.DEBUG: logging.debug(message)
        elif level == logging.INFO: logging.info(message)
        elif level == logging.WARNING: logging.warning(message)
        elif level == logging.ERROR: logging.error(message)
        elif level == logging.CRITICAL: logging.critical(message)
        else: logging.log(level, message)

    def process_log_queue(self):
        """Process messages from the log queue and update the GUI log display."""
        while not self.log_queue.empty():
            try:
                record = self.log_queue.get_nowait()
                if self.log_display:
                    log_to_gui(self.log_display, record.getMessage())
            except queue.Empty:
                break
            except Exception as e:
                print(f"Error processing log queue: {e}") # Fallback
        self.master.after(100, self.process_log_queue)


    def create_widgets(self):
        """Create all GUI elements and arrange them."""
        # --- Main Container Frame ---
        main_frame = ttk.Frame(self.master, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # --- Header ---
        header_label = ttk.Label(main_frame, text="Akita vMail", style="Header.TLabel", anchor=tk.CENTER)
        header_label.pack(fill=tk.X, pady=(0, 15))

        # --- Top Row: Connection & Recording Settings ---
        top_row_frame = ttk.Frame(main_frame)
        top_row_frame.pack(fill=tk.X, pady=5)

        # --- Connection Settings Frame ---
        settings_frame = ttk.LabelFrame(top_row_frame, text="Connection", padding="10")
        settings_frame.pack(side=tk.LEFT, padx=(0, 10), fill=tk.Y, anchor='nw')
        ttk.Label(settings_frame, text="Target:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        target_frame = ttk.Frame(settings_frame)
        target_frame.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5, pady=5)
        self.com_ports = self.meshtastic_handler.get_available_ports()
        self.connect_target_var = tk.StringVar()
        self.connect_target_entry = ttk.Entry(target_frame, textvariable=self.connect_target_var, width=18)
        if self.com_ports: self.connect_target_var.set(self.com_ports[0])
        self.connect_target_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        add_tooltip(self.connect_target_entry, "Enter COM Port (e.g., COM3) or IP Address")
        refresh_button = ttk.Button(target_frame, text="⟳", width=3, command=self.refresh_ports)
        refresh_button.pack(side=tk.LEFT, padx=(5, 0))
        add_tooltip(refresh_button, "Refresh COM Port List (updates dropdown if available)")
        self.connect_button = ttk.Button(settings_frame, text="Connect", command=self.toggle_connection, width=10)
        self.connect_button.grid(row=0, column=2, padx=(10, 5), pady=5)

        # --- Recording Settings Frame ---
        recording_frame = ttk.LabelFrame(top_row_frame, text="Recording", padding="10")
        recording_frame.pack(side=tk.LEFT, padx=10, fill=tk.Y, anchor='nw')
        # Use defaults from audio_handler which loaded config
        audio_cfg = self.config.get("audio", {})
        ttk.Label(recording_frame, text="Length (s):").grid(row=0, column=0, sticky=tk.W, padx=5, pady=3)
        self.recording_length_var = tk.StringVar(value=str(self.audio_handler.record_seconds))
        self.recording_length_entry = ttk.Entry(recording_frame, textvariable=self.recording_length_var, width=5)
        self.recording_length_entry.grid(row=0, column=1, sticky=tk.W, padx=5, pady=3)
        add_tooltip(self.recording_length_entry, "Recording duration (1-30 seconds)")
        ttk.Label(recording_frame, text="Quality:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=3)
        self.compression_quality_var = tk.StringVar(value=self.audio_handler.default_quality)
        self.compression_quality_combo = ttk.Combobox(recording_frame, textvariable=self.compression_quality_var,
                                                     values=list(self.audio_handler.quality_rates.keys()), width=10, state="readonly")
        self.compression_quality_combo.grid(row=1, column=1, sticky=tk.W, padx=5, pady=3)
        add_tooltip(self.compression_quality_combo, "Audio quality vs compressed size")
        ttk.Label(recording_frame, text="Chunk Size:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=3)
        self.chunk_size_var = tk.StringVar(value=DEFAULT_CHUNK_SIZE_KEY)
        self.chunk_size_combo = ttk.Combobox(recording_frame, textvariable=self.chunk_size_var,
                                            values=list(CHUNK_SIZES.keys()), width=10, state="readonly")
        self.chunk_size_combo.grid(row=2, column=1, sticky=tk.W, padx=5, pady=3)
        self.chunk_size_combo.bind("<<ComboboxSelected>>", self.update_chunk_size)
        add_tooltip(self.chunk_size_combo, "Max network packet payload size")

        # --- Middle Row: Voice Controls ---
        voice_frame_container = ttk.LabelFrame(main_frame, text="Controls", padding="10")
        voice_frame_container.pack(fill=tk.X, pady=10)
        voice_frame = ttk.Frame(voice_frame_container)
        voice_frame.pack() # Center buttons horizontally
        self.record_button = ttk.Button(voice_frame, text="🎤 Record", command=self.toggle_recording, width=12)
        self.record_button.pack(side=tk.LEFT, padx=5, pady=5)
        add_tooltip(self.record_button, "Start/Stop Recording")
        self.send_button = ttk.Button(voice_frame, text="✉️ Send", command=self.send_voice_message, width=10)
        self.send_button.pack(side=tk.LEFT, padx=5, pady=5)
        add_tooltip(self.send_button, "Send Last Recording")
        self.play_button = ttk.Button(voice_frame, text="▶ Play", command=self.play_selected_message, width=8)
        self.play_button.pack(side=tk.LEFT, padx=5, pady=5)
        add_tooltip(self.play_button, "Play Selected Message")
        self.stop_button = ttk.Button(voice_frame, text="⏹ Stop", command=self.stop_playback, width=8)
        self.stop_button.pack(side=tk.LEFT, padx=5, pady=5)
        add_tooltip(self.stop_button, "Stop Playback")
        self.test_button = ttk.Button(voice_frame, text="🧪 Test Send", command=self.send_test_message, width=12)
        self.test_button.pack(side=tk.LEFT, padx=(20, 5), pady=5)
        add_tooltip(self.test_button, "Send Test Message")

        # --- Messages List ---
        messages_frame = ttk.LabelFrame(main_frame, text="Messages", padding="10")
        messages_frame.pack(fill=tk.BOTH, expand=True, pady=5, ipady=5)
        list_container = Frame(messages_frame, bd=0)
        list_container.pack(fill=tk.BOTH, expand=True)
        self.messages_list = Listbox(list_container, height=10)
        self.messages_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.messages_list.bind('<<ListboxSelect>>', self.on_message_select)
        scrollbar = ttk.Scrollbar(list_container, orient=tk.VERTICAL, command=self.messages_list.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.messages_list.configure(yscrollcommand=scrollbar.set)

        # --- Log Display ---
        log_frame = ttk.LabelFrame(main_frame, text="Log Output", padding="10")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 5), ipady=5, side=tk.BOTTOM)
        # Add a clear button for the log
        clear_log_button = ttk.Button(log_frame, text="Clear Log", command=self.clear_log_display, width=10)
        clear_log_button.pack(side=tk.RIGHT, anchor='ne', padx=5, pady=(0,5)) # Top-right corner
        self.log_display = scrolledtext.ScrolledText(log_frame, height=8, wrap=tk.WORD)
        self.log_display.pack(fill=tk.BOTH, expand=True)

        # --- Status Bar ---
        self.status_var = tk.StringVar(value="Status: Disconnected")
        status_bar = ttk.Label(self.master, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W, style="Status.TLabel")
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)


    def update_status(self, message: str):
        """Update the status bar message safely."""
        if self.master and self.master.winfo_exists():
            try: self.status_var.set(f"Status: {message}")
            except tk.TclError: pass # Ignore if window closing

    def update_ui_state(self):
        """Update button states based on connection, recording, playback, and sending status."""
        if not self.master or not self.master.winfo_exists() or not hasattr(self, 'connect_button'):
             return # Avoid errors during shutdown

        try:
            is_rec = self.audio_handler.recording
            is_play = self.audio_handler.playing
            has_recording = self.current_recording_path and os.path.isfile(self.current_recording_path)
            is_sending = self.meshtastic_handler.sending_active

            selection = self.messages_list.curselection()
            has_selection = bool(selection)
            can_play_selection = False
            if has_selection:
                idx = selection[0]
                if 0 <= idx < len(self.voice_messages):
                    can_play_selection = bool(self.voice_messages[idx].get("filepath"))

            # Connection state
            connect_state = tk.NORMAL if not self.is_connected else tk.DISABLED
            connected_dependent_state = tk.NORMAL if self.is_connected else tk.DISABLED

            self.connect_target_entry.config(state=connect_state)
            self.connect_button.config(text="Disconnect" if self.is_connected else "Connect", state=tk.NORMAL) # Connect/Disconnect always enabled

            # Test button state
            test_btn_state = tk.NORMAL if self.is_connected and not is_sending else tk.DISABLED
            self.test_button.config(state=test_btn_state)

            # Record Button
            if is_rec:
                self.record_button.config(text="⏹ Stop Rec", state=tk.NORMAL)
            else:
                rec_btn_state = tk.NORMAL if self.is_connected and not is_play and not is_sending else tk.DISABLED
                self.record_button.config(text="🎤 Record", state=rec_btn_state)

            # Send Button
            send_btn_state = tk.NORMAL if self.is_connected and has_recording and not is_rec and not is_play and not is_sending else tk.DISABLED
            self.send_button.config(state=send_btn_state)

            # Play Button
            play_btn_state = tk.NORMAL if can_play_selection and not is_rec and not is_play and not is_sending else tk.DISABLED
            self.play_button.config(state=play_btn_state)

            # Stop Button
            stop_btn_state = tk.NORMAL if is_play else tk.DISABLED
            self.stop_button.config(state=stop_btn_state)

        except tk.TclError: pass # Ignore errors during shutdown
        except Exception as e: self.log(f"Error updating UI state: {e}", logging.ERROR)


    def refresh_ports(self):
        """Refresh the list of available COM ports and update the Entry field (optional)."""
        self.log("Refreshing COM ports list...")
        self.com_ports = self.meshtastic_handler.get_available_ports()
        current_target = self.connect_target_var.get()
        # If entry is empty or looks like a COM port, update with first found port
        if not current_target or any(s in current_target.upper() for s in ["COM", "/DEV/TTY", "/DEV/CU."]):
             if self.com_ports: self.connect_target_var.set(self.com_ports[0])
             else: self.connect_target_var.set("")
        self.log("COM ports list refreshed.")


    def update_chunk_size(self, event=None):
        """Update the max_chunk_size based on the dropdown selection."""
        selected_key = self.chunk_size_var.get()
        if selected_key in CHUNK_SIZES:
            new_size = CHUNK_SIZES[selected_key]
            if new_size != self.max_chunk_size:
                self.max_chunk_size = new_size
                self.log(f"Max network payload size set to {selected_key} ({self.max_chunk_size} bytes)")
        else:
            self.log(f"Invalid chunk size key: {selected_key}. Using default.", logging.WARNING)
            self.chunk_size_var.set(DEFAULT_CHUNK_SIZE_KEY)
            self.max_chunk_size = DEFAULT_CHUNK_SIZE


    def toggle_connection(self):
        """Connect or disconnect the Meshtastic device."""
        if self.is_connected:
            self.update_status("Disconnecting...")
            self.meshtastic_handler.disconnect()
            # State updates handled by callback
        else:
            target = self.connect_target_var.get().strip()
            if not target:
                messagebox.showerror("Error", "Please enter a COM Port or IP Address.")
                return
            self.update_status(f"Connecting to {target}...")
            self.connect_button.config(state=tk.DISABLED) # Disable during attempt
            self.meshtastic_handler.connect(target) # Async connection


    def toggle_recording(self):
        """Start or stop voice recording."""
        if self.audio_handler.recording:
            # === Stop Recording ===
            self.update_status("Stopping recording...")
            self.record_button.config(state=tk.DISABLED)
            if self.current_recording_path:
                threading.Thread(target=self._stop_recording_thread,
                                 args=(self.current_recording_path,), daemon=True).start()
            else:
                self.log("Error: No recording path available.", logging.ERROR)
                self.audio_handler.stop_recording("dummy_error.wav")
                self.update_status("Recording stopped (Error - No Path)")
                self.update_ui_state()
        else:
            # === Start Recording ===
            if not self.is_connected:
                 messagebox.showwarning("Not Connected", "Connect before recording.")
                 return
            quality = self.compression_quality_var.get()
            seconds_str = self.recording_length_var.get()
            clamped_seconds = self.audio_handler.set_recording_params(seconds_str, quality)
            if str(clamped_seconds) != seconds_str: self.recording_length_var.set(str(clamped_seconds))

            self.update_status(f"Starting recording ({clamped_seconds}s)...")
            self.record_button.config(state=tk.DISABLED)
            success, filepath = self.audio_handler.start_recording()
            if success:
                self.current_recording_path = filepath
                self.log(f"Recording started. Output file: {filepath}")
                self.update_status("Recording...")
                self.master.after(int(clamped_seconds * 1000) + 100, self.auto_stop_recording)
            else:
                self.log("Failed to start recording.", logging.ERROR)
                self.update_status("Recording failed to start")
                self.current_recording_path = None
                messagebox.showerror("Recording Error", "Could not start recording.")
            self.update_ui_state()


    def _stop_recording_thread(self, filepath: str):
        """Worker thread to stop recording and save the file."""
        success = self.audio_handler.stop_recording(filepath)
        self.master.after(0, self._stop_recording_finished, success, filepath)

    def _stop_recording_finished(self, success: bool, filepath: str):
        """GUI updates after stopping recording."""
        if success:
            self.log(f"Recording finished and saved: {filepath}")
            desc = f"🎙️ My Recording @ {datetime.now().strftime('%H:%M:%S')}"
            self.add_message_to_list(desc, filepath, "Me")
            self.update_status("Recording saved")
        else:
            self.log("Recording stopped, but failed to save.", logging.WARNING)
            self.current_recording_path = None
            self.update_status("Recording stopped (Save failed)")
            messagebox.showwarning("Save Error", f"Could not save recording to:\n{filepath}")
        self.update_ui_state()


    def auto_stop_recording(self):
        """Automatically stop recording if it's still active after the timer."""
        if self.audio_handler.recording:
            self.log("Recording duration reached. Stopping automatically.")
            self.toggle_recording()


    def add_message_to_list(self, description: str, filepath: str | None, from_id: str):
        """Add a message entry to the GUI listbox."""
        icon = "❓"
        if filepath and from_id == "Me": icon = "🎙️"
        elif filepath: icon = "🔊"
        elif not filepath: icon = "💬"
        full_description = f"{icon} {description}"
        self.voice_messages.append({"description": full_description, "filepath": filepath, "from_id": from_id})
        self.messages_list.insert(tk.END, full_description)
        self.messages_list.yview(tk.END)


    def on_message_select(self, event=None):
        """Handle selection change in the messages list."""
        self.update_ui_state()


    def play_selected_message(self):
        """Play the voice message selected in the list."""
        selection = self.messages_list.curselection()
        if not selection: return
        index = selection[0]
        if 0 <= index < len(self.voice_messages):
            message_info = self.voice_messages[index]
            filepath = message_info.get("filepath")
            description = message_info.get("description")
            if filepath and os.path.isfile(filepath):
                self.update_status(f"Playing: {description}")
                self.update_ui_state() # Disable buttons before starting thread
                threading.Thread(target=self._play_thread, args=(filepath,), daemon=True).start()
            elif filepath:
                self.log(f"Audio file not found: {filepath}", logging.ERROR)
                messagebox.showerror("Playback Error", f"Audio file not found:\n{filepath}")
                self.update_status("Playback Error (File Not Found)")
            else:
                self.log("Selected item is not playable.", logging.INFO)
                self.update_status("Cannot play selected item")
        else:
            self.log(f"Invalid selection index: {index}", logging.WARNING)

    def _play_thread(self, filepath: str):
        """Background thread for audio playback."""
        success = self.audio_handler.start_playback(filepath)
        if success:
            while self.audio_handler.playing: time.sleep(0.1)
        self.master.after(0, self._playback_finished)


    def _playback_finished(self):
        """Update GUI after playback finishes or is stopped."""
        self.audio_handler.playback_finished()
        self.update_status("Playback finished")
        self.update_ui_state()


    def stop_playback(self):
        """Stop the currently playing audio."""
        if self.audio_handler.playing:
            self.log("Stop playback requested.")
            self.audio_handler.stop_playback()
            self.update_status("Playback stopped")
            self.update_ui_state()


    def send_test_message(self):
        """Send a simple test message."""
        if not self.is_connected: messagebox.showerror("Error", "Not connected."); return
        if self.meshtastic_handler.sending_active: messagebox.showwarning("Busy", "Already sending."); return
        self.update_status("Sending test message...")
        node_name = "N/A"
        try:
            if self.meshtastic_handler.interface and self.meshtastic_handler.interface.myInfo:
                 node_name = self.meshtastic_handler.interface.myInfo.long_name or f"!{self.meshtastic_handler.interface.myInfo.my_node_num:x}"
        except Exception: pass
        message = f"Akita vMail test from {node_name} @ {datetime.now().strftime('%H:%M:%S')}"
        self.update_ui_state() # Disable buttons
        threading.Thread(target=self._send_test_thread, args=(message,), daemon=True).start()

    def _send_test_thread(self, message: str):
        """Background thread for sending test message."""
        success = self.meshtastic_handler.send_test_message(message)
        self.master.after(0, self._send_finished, success, "Test message")


    def send_voice_message(self):
        """Compress and send the last recorded voice message."""
        if not self.is_connected: messagebox.showerror("Error", "Not connected."); return
        if not self.current_recording_path or not os.path.isfile(self.current_recording_path):
            messagebox.showerror("Error", "No valid recording available."); return
        if self.meshtastic_handler.sending_active: messagebox.showwarning("Busy", "Already sending."); return

        self.update_chunk_size()
        quality = self.compression_quality_var.get()
        filepath = self.current_recording_path
        filename_short = os.path.basename(filepath)
        self.update_status(f"Preparing '{filename_short}'...")
        self.log(f"Initiating send: {filepath}, Quality: {quality}, ChunkKey: {self.chunk_size_var.get()} ({self.max_chunk_size} bytes)")
        self.update_ui_state() # Disable buttons
        threading.Thread(target=self._send_voice_thread, args=(filepath, quality), daemon=True).start()


    def _send_voice_thread(self, filepath: str, quality: str):
        """Background thread for compressing and sending a voice message."""
        filename_short = os.path.basename(filepath)
        self.master.after(0, self.update_status, f"Compressing '{filename_short}' ({quality})...")
        compressed_data = self.audio_handler.compress_audio(filepath, quality)

        if not compressed_data:
            self.master.after(0, messagebox.showerror, "Compression Error", f"Failed to compress:\n{filename_short}")
            self.master.after(0, self.update_status, "Compression Failed")
            self.master.after(0, self.update_ui_state)
            return

        data_len = len(compressed_data)
        estimated_payload_len = data_len * 1.34 + 150 # Heuristic
        success = False
        description = f"Voice message '{filename_short}' ({data_len} bytes compressed)"

        if estimated_payload_len > self.max_chunk_size:
            self.master.after(0, self.update_status, f"Sending chunked: {filename_short} ({data_len} bytes)...")
            success = self.meshtastic_handler.send_chunked_message(compressed_data, self.max_chunk_size)
        else:
            self.master.after(0, self.update_status, f"Sending complete: {filename_short} ({data_len} bytes)...")
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            success = self.meshtastic_handler.send_complete_voice_message(compressed_data, timestamp)

        self.master.after(0, self._send_finished, success, description)


    def _send_finished(self, success: bool, description: str):
        """Update GUI after a send attempt is finished."""
        if success:
            self.log(f"Send command for '{description}' issued successfully.")
            self.update_status("Send Successful")
        else:
            self.log(f"Failed to send '{description}'.", logging.ERROR)
            self.update_status("Send Failed")
            messagebox.showerror("Send Error", f"Failed to send {description}.\nCheck connection and logs.")
        self.update_ui_state() # Re-enable buttons


    # --- Message Receiving and Processing Callbacks ---

    def handle_received_message(self, msg_type: str, data: any, from_id: str, packet_id: str):
        """Callback from MeshtasticHandler. Schedules processing in main thread."""
        self.master.after(0, self._process_received_message_mainthread, msg_type, data, from_id, packet_id)

    def _process_received_message_mainthread(self, msg_type: str, data: any, from_id: str, packet_id: str):
        """Process received messages in the main GUI thread."""
        self.log(f"GUI Thread: Processing {msg_type} from {from_id} (PktID: {packet_id})", logging.DEBUG)

        # --- Handle Status Updates ---
        if msg_type == 'status':
             full_status = str(data)
             # Extract node info if present (format: "Connected: Node: !xxxx (Name) HW:...")
             if "Connected: Node:" in full_status:
                  self.connected_node_info = full_status.split("Connected: ", 1)[1]
                  status_display = f"Connected: {self.connected_node_info}"
             elif "Disconnected" in full_status or "Failed" in full_status:
                  self.connected_node_info = "N/A"
                  status_display = full_status # Show full disconnect/fail message
             else:
                  status_display = full_status # Other status messages

             self.update_status(status_display)
             self.is_connected = "Connected" in status_display and "Failed" not in status_display
             self.update_ui_state()
             return

        # --- Handle Standard Text Messages ---
        elif msg_type == 'text':
            desc = f"from {from_id}: {data}"
            self.add_message_to_list(desc, None, from_id)
            self.update_status(f"Received Text from {from_id}")

        # --- Handle Custom Data Payloads ---
        elif msg_type == 'data':
            if not isinstance(data, dict):
                 self.log(f"Received non-dict data payload from {from_id}. Ignoring.", logging.WARNING)
                 return
            payload_type = data.get('type')

            if payload_type == MSG_TYPE_TEST:
                test_msg = data.get('test', '(empty)')
                self.log(f"Received Test from {from_id}: {test_msg}")
                messagebox.showinfo("Test Received", f"From: {from_id}\nMessage: {test_msg}")
                self.update_status(f"Received Test from {from_id}")

            elif payload_type == MSG_TYPE_COMPLETE_VOICE:
                self.log(f"Processing Complete Voice from {from_id}")
                crc_ok, raw_voice_data = verify_complete_voice_crc(data)
                if crc_ok and raw_voice_data:
                    timestamp = data.get('timestamp', datetime.now().strftime('%Y%m%d_%H%M%S'))
                    filename = os.path.join(self.audio_handler.voice_message_dir, f"rec_{from_id}_{timestamp}.wav")
                    if self.audio_handler.create_wav_from_compressed(raw_voice_data, filename):
                        desc = f"from {from_id} @ {timestamp}"
                        self.add_message_to_list(desc, filename, from_id)
                        self.update_status(f"Received Voice from {from_id}")
                    else: self.update_status(f"Voice decode error from {from_id}")
                else:
                    self.log(f"CRC check failed for complete voice from {from_id}", logging.WARNING)
                    self.update_status(f"Voice CRC error from {from_id}")

            elif payload_type == MSG_TYPE_VOICE_CHUNK:
                self.process_incoming_chunk(data, from_id)

            elif payload_type == MSG_TYPE_ACK:
                ack_id = data.get('ack_id')
                chunk_num = data.get('chunk_num')
                self.log(f"Received ACK for chunk {chunk_num} (ID: {ack_id}) from {from_id}", logging.INFO)
                # TODO: Track ACKs if retransmission implemented

            else: self.log(f"Received unknown data type '{payload_type}' from {from_id}.", logging.WARNING)
        else: self.log(f"Received unhandled message type '{msg_type}' from {from_id}", logging.WARNING)


    def process_incoming_chunk(self, chunk_data: dict, from_node: str):
        """Process a received chunk of a multi-part voice message in the GUI thread."""
        chunk_id = chunk_data.get('chunk_id')
        chunk_num = chunk_data.get('chunk_num')
        total_chunks = chunk_data.get('total_chunks')
        if not all([chunk_id, isinstance(chunk_num, int), isinstance(total_chunks, int)]):
            self.log(f"Invalid chunk data from {from_node}: {chunk_data}", logging.WARNING)
            return

        self.log(f"Processing chunk {chunk_num}/{total_chunks} (ID: {chunk_id}) from {from_node}", logging.DEBUG)
        crc_ok, raw_chunk_data = verify_chunk_crc(chunk_data)
        if not crc_ok:
            self.update_status(f"Chunk CRC error from {from_node} (ID:{chunk_id} Num:{chunk_num})")
            return

        # Send ACK
        self.meshtastic_handler.send_ack(chunk_id, chunk_num, from_node)

        # Store the Chunk
        if chunk_id not in self.message_chunks:
            if chunk_num == 1:
                 self.message_chunks[chunk_id] = {'chunks': {}, 'total': total_chunks, 'from_id': from_node, 'timestamp': time.time()}
                 self.log(f"Started receiving message {chunk_id} ({total_chunks} chunks) from {from_node}")
                 self.update_status(f"Receiving {chunk_id} from {from_node} (1/{total_chunks})...")
            else:
                 self.log(f"Received chunk {chunk_num} for {chunk_id} before chunk 1. Discarding.", logging.WARNING)
                 return

        if chunk_id in self.message_chunks:
            if chunk_num not in self.message_chunks[chunk_id]['chunks']:
                self.message_chunks[chunk_id]['chunks'][chunk_num] = raw_chunk_data
                self.message_chunks[chunk_id]['timestamp'] = time.time()
                self.log(f"Stored chunk {chunk_num} for {chunk_id}.", logging.DEBUG)
            else:
                self.log(f"Duplicate chunk {chunk_num} for {chunk_id}. Ignoring.", logging.DEBUG)
                return

            # Check for Completion
            received_count = len(self.message_chunks[chunk_id]['chunks'])
            total_expected = self.message_chunks[chunk_id]['total']
            self.update_status(f"Receiving {chunk_id} ({received_count}/{total_expected})...")
            self.log(f"Have {received_count}/{total_expected} chunks for {chunk_id}.", logging.DEBUG)

            if received_count >= total_expected: # Use >= in case total_chunks was wrong
                if received_count > total_expected:
                     self.log(f"Warning: Received more chunks ({received_count}) than expected ({total_expected}) for {chunk_id}.", logging.WARNING)
                self.log(f"Received all expected chunks for {chunk_id}. Reassembling...")
                self.reassemble_message(chunk_id)
        else:
             self.log(f"Received chunk {chunk_num} for untracked message ID {chunk_id}.", logging.WARNING)


    def reassemble_message(self, chunk_id: str):
        """Reassemble message from chunks, create WAV, update list (GUI thread)."""
        if chunk_id not in self.message_chunks:
            self.log(f"Cannot reassemble: ID {chunk_id} not found.", logging.ERROR)
            return

        message_info = self.message_chunks[chunk_id]
        from_node = message_info['from_id']
        total_chunks = message_info['total']
        received_chunks_map = message_info['chunks']
        received_count = len(received_chunks_map)

        if received_count < total_chunks:
            self.log(f"Reassembly called for {chunk_id} but missing chunks ({received_count}/{total_chunks}). Aborting.", logging.WARNING)
            return # Wait for timeout

        # Combine Chunks
        combined_data = b""
        missing_chunk_numbers = []
        reassembly_successful = True
        try:
            for i in range(1, total_chunks + 1):
                if i in received_chunks_map: combined_data += received_chunks_map[i]
                else: missing_chunk_numbers.append(i); reassembly_successful = False

            if not reassembly_successful:
                 self.log(f"Reassembly failed for {chunk_id}: Missing data for chunks: {missing_chunk_numbers}", logging.ERROR)
                 self.update_status(f"Reassembly failed for {chunk_id}")
            else:
                # Create WAV
                self.log(f"Combined {total_chunks} chunks for {chunk_id}. Size: {len(combined_data)} bytes.")
                timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = os.path.join(self.audio_handler.voice_message_dir, f"rec_{from_node}_{timestamp_str}_chunked.wav")
                if self.audio_handler.create_wav_from_compressed(combined_data, filename):
                    desc = f"from {from_node} @ {timestamp_str} (Chunked)"
                    self.add_message_to_list(desc, filename, from_node)
                    self.update_status(f"Reassembled Voice from {from_node}")
                    self.log(f"Reassembled and saved {chunk_id} to {filename}")
                else:
                    self.update_status(f"Reassembly decode error from {from_node}")
                    reassembly_successful = False
        except Exception as e:
            self.log(f"Unexpected error reassembling {chunk_id}: {e}", logging.ERROR)
            import traceback; self.log(traceback.format_exc(), logging.ERROR)
            reassembly_successful = False
            self.update_status(f"Reassembly error for {chunk_id}")
        finally:
            # Clean up
            if chunk_id in self.message_chunks:
                del self.message_chunks[chunk_id]
                self.log(f"Cleaned up chunk data for {chunk_id}.", logging.DEBUG)


    def check_incomplete_chunks(self):
        """Periodically check for and clean up timed-out incomplete messages."""
        now = time.time()
        timed_out_ids = []
        chunk_timeout = self.config.get("chunking", {}).get("receive_timeout_sec", 60)

        for chunk_id in list(self.message_chunks.keys()):
            if chunk_id in self.message_chunks:
                message_info = self.message_chunks[chunk_id]
                last_update = message_info.get('timestamp', 0)
                if now - last_update > chunk_timeout:
                    timed_out_ids.append(chunk_id)
                    rcvd = len(message_info['chunks']); total = message_info['total']
                    frm = message_info['from_id']
                    self.log(f"Message {chunk_id} from {frm} timed out ({rcvd}/{total} chunks). Discarding.", logging.WARNING)

        if timed_out_ids:
             self.log(f"Cleaning up timed-out messages: {timed_out_ids}", logging.INFO)
             for chunk_id in timed_out_ids:
                 if chunk_id in self.message_chunks: del self.message_chunks[chunk_id]
             self.update_status("Cleaned up timed-out messages")

        self.master.after(int(chunk_timeout * 1000 / 2), self.check_incomplete_chunks) # Check at half the timeout interval


    def clear_log_display(self):
        """Clears the log display widget."""
        clear_scrolled_text(self.log_display)


    def on_closing(self):
        """Handle window close event cleanly."""
        self.log("Closing application requested...")
        self.update_status("Closing...")
        self.master.protocol("WM_DELETE_WINDOW", lambda: None) # Disable close

        # Give handlers a chance to finish current ops if possible
        # (e.g., wait briefly if sending) - complex, skip for now

        if self.meshtastic_handler.is_connected:
            self.log("Disconnecting Meshtastic...")
            self.meshtastic_handler.disconnect()
            time.sleep(0.5) # Allow disconnect to process

        self.log("Cleaning up audio resources...")
        self.audio_handler.cleanup()

        self.log("Destroying main window.")
        # Stop log queue polling? Not strictly necessary if window is destroyed.
        self.master.destroy()
        print("Akita vMail closed.")

