# -*- coding: utf-8 -*-
"""
File: main.py
Description: Main entry point for the Akita vMail application.
             Sets up basic logging, initializes Tkinter, and starts the GUI.
"""

import tkinter as tk
import logging
import sys # For checking if running as executable

# --- Import the main application class ---
try:
    from gui import AkitaVmailApp
except ImportError as e:
     print(f"FATAL ERROR: Could not import AkitaVmailApp from gui.py: {e}")
     print("Ensure gui.py and other required .py files are in the same directory.")
     # Pause for user to see the error in console if run directly
     input("Press Enter to exit...")
     exit(1)
except Exception as e:
     print(f"FATAL ERROR: An unexpected error occurred during import: {e}")
     input("Press Enter to exit...")
     exit(1)


def setup_basic_logging():
    """Sets up basic console logging for messages before GUI starts."""
    log_format = '%(asctime)s - %(levelname)s - %(message)s'
    # Check if running as a bundled executable (e.g., PyInstaller)
    # to potentially disable console logging or log to a file instead.
    if getattr(sys, 'frozen', False):
        # Running as executable - maybe log to file?
        # logging.basicConfig(level=logging.INFO, filename='akita_vmail.log', filemode='a', format=log_format)
        # Or disable basic console logging if GUI handles everything
         pass # Let GUI setup handle it
    else:
        # Running as script, log to console
        logging.basicConfig(level=logging.INFO, format=log_format)

def main():
    """Main function to initialize and run the Akita vMail application."""
    setup_basic_logging() # Setup console logging first
    logging.info("Starting Akita vMail application...")

    # --- Load central configuration ---
    try:
        from utils import get_config, load_config
        try:
            config = get_config()
        except Exception:
            config = load_config()
    except Exception:
        config = {}

    # --- Initialize Tkinter ---
    # Use themed Tkinter if available
    try:
        # Requires 'pip install ttkthemes'
        # from ttkthemes import ThemedTk
        # root = ThemedTk(theme="arc") # Example theme
        root = tk.Tk() # Fallback to standard Tk
    except ImportError:
        root = tk.Tk()
        logging.info("ttkthemes not found, using standard Tkinter.")
    except tk.TclError as e:
         root = tk.Tk()
         logging.warning(f"Failed to apply theme: {e}. Using standard Tkinter.")


    # --- Create and Run the Application ---
    app = None # Define app variable outside try block
    try:
        app = AkitaVmailApp(root, config) # Create instance of the main GUI class with central config
        root.mainloop() # Start the Tkinter event loop
    except KeyboardInterrupt:
        logging.info("KeyboardInterrupt detected, initiating clean shutdown...")
        try:
             if app and hasattr(app, 'on_closing') and root.winfo_exists():
                 app.on_closing()
             elif root.winfo_exists():
                  root.destroy()
        except Exception as e:
             logging.error(f"Error during KeyboardInterrupt cleanup: {e}")
    except Exception as e:
         logging.exception("An unexpected critical error occurred in the main loop.")
         try:
             if root.winfo_exists(): root.destroy()
         except Exception: pass
         # Optionally show a simple error dialog if possible
         # messagebox.showerror("Fatal Error", f"A critical error occurred:\n{e}\nSee logs for details.")


if __name__ == "__main__":
    # This block executes when the script is run directly
    main()
    logging.info("Akita vMail finished.")
    print("Akita vMail finished.") # Console message on exit
