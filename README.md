# Akita vMail - Meshtastic Voice Messenger

From [Akita Engineering](https://www.akitaengineering.com)

Akita vMail sets the standard for reliable voice communication over Meshtastic networks.  
This robust application enables sending and receiving short voice messages using a connected Meshtastic device.
  
Engineered for resilience, Akita vMail incorporates CRC32 checksums for data integrity and a basic Acknowledgement (ACK) system for enhanced reliability of chunked messages, ensuring your voice gets through even in challenging network conditions.  

Settings are configurable via `config.json`.

---

## Contact

- **Email:** info@akitaengineering.com

---

## License

This software is licensed under the **GNU General Public License v3.0 (GPLv3)**.  
License file not included in this package.  
Refer to: [GNU GPL v3 License](https://www.gnu.org/licenses/gpl-3.0.en.html)

---

## Features

- Record short voice messages.
- Compress and send voice messages over Meshtastic.
- Receive and play voice messages.
- Message chunking for larger messages.
- CRC32 checksums for data integrity on chunks and complete messages.
- Basic Acknowledgement (ACK) for received chunks (receiver sends ACK upon successful CRC validation).
- Adjustable audio quality and network chunk size via GUI.
- External configuration via `config.json`.
- Simple GUI built with Tkinter, including a log clear button.
- Logs known mesh nodes upon connection.

---

## Requirements

- Python 3.7+
- Meshtastic device connected via USB/Serial or accessible via TCP (running recent firmware).
- Required Python libraries (see `requirements.txt`).

---

## Installation

### 1. Create Project Directory
```bash
mkdir akita_vmail
cd akita_vmail
```
### 2. Save Files
Save all the provided code files (.py, .json, .txt) into the akita_vmail directory.

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```
Note: Installing PyAudio might require additional system dependencies (e.g., portaudio19-dev on Debian/Ubuntu or portaudio via Homebrew on macOS).
Refer to the PyAudio documentation for your OS.

### 4. Create Voice Message Directory
```bash
mkdir voice_messages
```
This is where recordings and received messages will be stored.

### 5. (Optional) Edit Configuration
Modify config.json to change default settings like the Meshtastic port number or chunking parameters if needed.

# Usage
### 1. Connect your Meshtastic device via USB or ensure it's reachable via IP.

### 2. Run the application:
```bash
python main.py
```
# Akita vMail - Meshtastic Voice Messenger

From [Akita Engineering](https://www.akitaengineering.com)

Akita vMail enables sending and receiving short voice messages over Meshtastic networks using a GUI-based desktop app. It supports chunked transfers with CRC32 checks and simple ACKs to improve reliability on lossy mesh links.

Configuration is provided via [config.json](akita_vmail/config.json) and runtime data is stored in a `voice_messages` directory by default.

---

**Contact**: info@akitaengineering.com

---

## License

This project is licensed under the GNU GPL v3.0. See the included [LICENSE](LICENSE) file for details.

---

## Highlights

- Record and play short voice messages
- Compress and transmit messages over Meshtastic
- Chunking for larger payloads with CRC32 validation
- ACKs for chunk confirmation, GUI built with Tkinter
- Configurable audio quality, recording length, and chunk size

---

## Requirements

- Python 3.8+ recommended
- A Meshtastic device (USB/Serial) or a reachable Meshtastic TCP endpoint
- See `akita_vmail/requirements.txt` for Python package dependencies

Notable packages: `meshtastic`, `pyserial`, `pyaudio`, `numpy`, `pypubsub`.

---

## Quick Setup (Linux-first)

1. Clone the repository and open a terminal in the project root.

2. Create and activate a Python virtual environment (recommended):

```bash
python3 -m venv .venv
source .venv/bin/activate
```

3. Install system packages required for audio and building native extensions (Debian/Ubuntu example):

```bash
sudo apt-get update
sudo apt-get install -y build-essential portaudio19-dev libsndfile1 libasound2-dev
```

4. Install Python dependencies into the activated venv:

```bash
python3 -m pip install --upgrade pip
python3 -m pip install -r akita_vmail/requirements.txt
```

Note: On many Linux distributions `pyaudio` must be compiled against `portaudio` (installed above). If `pyaudio` fails to install, install `portaudio19-dev` (Debian/Ubuntu) or the equivalent package for your distro, then re-run the `pip install` command.

5. Create the recordings storage directory (if not already present):

```bash
mkdir -p voice_messages
```

6. (Optional) Edit `akita_vmail/config.json` to change defaults such as `meshtastic_port_num`, chunk sizes, and audio quality.

> Windows users: If you're on Windows you can still follow the above steps but use PowerShell for the venv activation. Installing `pyaudio` on Windows is often easiest with `pipwin`:

```powershell
python -m pip install pipwin
python -m pipwin install pyaudio
```

---

## Run the App

Run from the project root with the venv Python (or after activating the venv):

```powershell
python akita_vmail/main.py
```

Alternatively, change directory into `akita_vmail` and run `python main.py`.

---

## Troubleshooting

- If imports fail for `pyaudio` or `meshtastic`, ensure the packages are installed in the active environment. For `pyaudio` on Windows, prefer `pipwin` as shown above.
- If the Meshtastic device isn't detected, verify the COM port in Device Manager (Windows) or use `ls /dev/tty*` on Unix. The GUI accepts COM names (e.g., `COM3`) or IP addresses for TCP connections.
- Logs appear in the GUI log pane; enable console logging by running without a frozen/bundled executable.

---

## Development Notes

- The GUI lives in `akita_vmail/gui.py`.
- Audio logic is in `akita_vmail/audio_handler.py` and protocol helpers are in `akita_vmail/protocol.py`.
- If you modify config loading, see `akita_vmail/utils.py` for the `load_config()` helper.




