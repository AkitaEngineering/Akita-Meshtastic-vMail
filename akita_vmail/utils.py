# -*- coding: utf-8 -*-
"""
File: utils.py
Description: Utility functions for Akita vMail, including configuration loading,
             logging setup, GUI logging, and tooltips.
"""
import tkinter as tk
from tkinter import scrolledtext, Toplevel, Label
from datetime import datetime
import logging
import logging.handlers # Required for QueueHandler
import json
import os
import collections.abc
import copy

# --- Configuration Loading ---

DEFAULT_CONFIG = {
    "meshtastic_port_num": 256,
    "chunking": {
        "sizes": {"Small": 150, "Medium": 180, "Large": 200},
        "default_key": "Medium",
        "retry_count": 2,
        "retry_delay_sec": 1.0,
        "receive_timeout_sec": 60
    },
    "audio": {
        "default_quality": "Low",
        "default_length_sec": 3,
        "quality_rates_hz": {"Ultra Low": 4000, "Very Low": 8000, "Low": 11025}
    }
}

def _recursive_update(d, u):
    """Recursively update a dictionary."""
    for k, v in u.items():
        if isinstance(v, collections.abc.Mapping):
            d[k] = _recursive_update(d.get(k, {}), v)
        else:
            d[k] = v
    return d

_CACHED_CONFIG = None

def load_config(config_path="config.json") -> dict:
    """
    Loads configuration from a JSON file, falling back to defaults.
    Performs a recursive merge of the loaded config onto the defaults.
    Creates a default config file if one doesn't exist.
    """
    config = copy.deepcopy(DEFAULT_CONFIG) # Start with a deep copy of defaults

    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                loaded_config = json.load(f)
                config = _recursive_update(config, loaded_config)
                logging.info(f"Successfully loaded and merged configuration from {config_path}")
        except json.JSONDecodeError as e:
            logging.error(f"Error decoding JSON from {config_path}: {e}. Using default configuration.")
            config = DEFAULT_CONFIG.copy() # Revert to defaults on error
        except Exception as e:
            logging.error(f"Error loading configuration file {config_path}: {e}. Using default configuration.")
            config = DEFAULT_CONFIG.copy() # Revert to defaults on error
    else:
        logging.warning(f"Configuration file '{config_path}' not found. Using defaults and creating a new one.")
        try:
            with open(config_path, 'w') as f:
                json.dump(DEFAULT_CONFIG, f, indent=2)
            logging.info(f"Created default configuration file at {config_path}")
        except Exception as e:
            logging.error(f"Could not create default configuration file: {e}")
    return config


def get_config(config_path="config.json") -> dict:
    """
    Return a cached configuration dictionary. The file is read only once per process
    and subsequent calls return the same object. Callers that need fresh reloads
    should call `load_config` directly.
    """
    global _CACHED_CONFIG
    if _CACHED_CONFIG is None:
        _CACHED_CONFIG = load_config(config_path)
    return _CACHED_CONFIG

# --- Logging Setup ---

def setup_logging_queue(log_queue):
    """Configure the root logger to use a queue for thread-safe GUI updates."""
    queue_handler = logging.handlers.QueueHandler(log_queue)
    logger = logging.getLogger() # Get the root logger
    # Prevent adding handler multiple times if called again
    if not any(isinstance(h, logging.handlers.QueueHandler) for h in logger.handlers):
        logger.addHandler(queue_handler)
        logger.setLevel(logging.INFO) # Set the desired level for the logger

def log_to_gui(log_display: scrolledtext.ScrolledText, message: str):
    """
    Safely add a timestamped message to the Tkinter ScrolledText log display.
    Ensures the widget is enabled before inserting and disabled afterward.
    """
    if not log_display or not log_display.winfo_exists(): # Check if widget exists
        # Fallback to console print if GUI log is unavailable
        # print(f"GUI Log Unavailable: {message}")
        return
    try:
        # Save current state and enable
        original_state = log_display.cget('state')
        log_display.config(state=tk.NORMAL)

        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_display.insert(tk.END, f"[{timestamp}] {message}\n")
        log_display.see(tk.END) # Scroll to the end

        # Restore original state
        log_display.config(state=original_state)

    except tk.TclError as e:
        # Handle cases where the widget might be destroyed during shutdown
        # print(f"Error logging to GUI (widget might be destroyed): {e}")
        pass # Ignore error if widget is gone
    except Exception as e:
        print(f"Unexpected error logging to GUI: {e}") # Fallback print for other errors

# --- GUI Utilities ---

def add_tooltip(widget: tk.Widget, text: str):
    """Add a simple tooltip to a Tkinter widget."""
    tooltip_window = None

    def enter(event):
        nonlocal tooltip_window
        # Ensure no existing tooltip window is lingering
        if tooltip_window:
            tooltip_window.destroy()

        x, y, _, _ = widget.bbox("insert") # Get position relative to widget
        # Calculate position relative to the screen
        x += widget.winfo_rootx() + 25
        y += widget.winfo_rooty() + 20 # Adjust vertical position slightly

        # Create a Toplevel window (a separate window without decorations)
        tooltip_window = Toplevel(widget)
        tooltip_window.wm_overrideredirect(True) # Remove window borders, title bar
        tooltip_window.wm_geometry(f"+{x}+{y}") # Position the tooltip

        # Create a label inside the Toplevel window to display the text
        label = Label(tooltip_window, text=text, justify=tk.LEFT,
                      background="#FFFFE0", relief=tk.SOLID, borderwidth=1,
                      font=("Arial", "9", "normal")) # Slightly larger font
        label.pack(ipadx=2, ipady=2) # Add internal padding

    def leave(event):
        nonlocal tooltip_window
        if tooltip_window:
            try:
                tooltip_window.destroy()
            except tk.TclError: # Handle case where window might already be destroyed
                pass
            tooltip_window = None

    # Bind mouse enter and leave events to the widget
    widget.bind("<Enter>", enter)
    widget.bind("<Leave>", leave)
    # Also bind button press/release in case the mouse leaves while button is down
    widget.bind("<ButtonPress>", leave)

def clear_scrolled_text(log_display: scrolledtext.ScrolledText):
    """Safely clears the content of a ScrolledText widget."""
    if not log_display or not log_display.winfo_exists():
        return
    try:
        original_state = log_display.cget('state')
        log_display.config(state=tk.NORMAL)
        log_display.delete('1.0', tk.END) # Delete all content
        log_display.config(state=original_state)
        logging.info("Log display cleared.")
    except tk.TclError as e:
        # print(f"Error clearing log display (widget might be destroyed): {e}")
        pass
    except Exception as e:
        print(f"Unexpected error clearing log display: {e}")

