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
# Akita vMail - Meshtastic Voice Messenger

From [Akita Engineering](https://www.akitaengineering.com)

Akita vMail is a desktop application for sending and receiving short voice
messages over Meshtastic networks. The project focuses on resilience and
observability: messages include CRC32 checks for integrity and a reliable ACK
scheme for chunked transfers over lossy links.

This repository contains the application code (under `akita_vmail/`),
configuration defaults, and a small test suite. The GUI uses Tkinter and the
core code is written for Python 3.8+ (tested on 3.10+ as well).

---

## Recent changes

- Implemented ACK tracking and retransmit logic for chunked messages.
- Added `ack_timeout_sec` configuration and getters in `protocol.py`.
- Improved `AudioHandler` to auto-stop recordings and safely close streams.
- GUI now exposes simple metrics (pending ACKs / retransmit counts) in the
  status bar for observability.

See commit history for full details.

---

## Quickstart (developer / local run)

1. Create and activate a virtual environment (recommended):

```powershell
python -m venv .venv
.venv\\Scripts\\Activate.ps1
```

2. Install Python dependencies:

```powershell
python -m pip install --upgrade pip
python -m pip install -r akita_vmail/requirements.txt
```

3. Ensure a directory exists for voice files (defaults to `voice_messages`):

```powershell
mkdir voice_messages
```

4. (Optional) Edit `config.json` in the project root to change defaults.

5. Run the application from the repository root:

```powershell
python -m akita_vmail.main
# or
python akita_vmail/main.py
```

Notes:
- On Windows, installing `pyaudio` may be easier via `pipwin`.
- Running the GUI headlessly (in CI) requires mocking audio and Meshtastic
  dependencies; the test suite already includes test-time fakes/mocks.

---

## Configuration

Configuration defaults live in `akita_vmail/utils.py` as `DEFAULT_CONFIG`. A
local `config.json` (in repository root) will be merged recursively over the
defaults when present. Use `get_config()` to access the cached config at
runtime; call `load_config()` to force a reload.

Key config sections:
- `meshtastic_port_num`: default app port number used when sending data
- `chunking`: sizes, default key, `retry_count`, `retry_delay_sec`,
  `ack_timeout_sec`, and `receive_timeout_sec`
- `audio`: default quality keys and sampling rates, default recording length

---

## Running Tests

Unit tests use `pytest`. To run tests locally:

```powershell
python -m pytest tests/ -q
```

The test harness includes fakes/mocks for runtime-only modules so tests run
headlessly (no audio hardware or Meshtastic device required).

---

## Project layout

- `akita_vmail/` - application package
  - `main.py` - application entrypoint
  - `gui.py` - main Tkinter app (componentized)
  - `audio_handler.py` - audio recording/playback/compression
  - `meshtastic_handler.py` - Meshtastic interface and send/receive logic
  - `protocol.py` - message formats, CRC, chunk helpers (config-aware)
  - `utils.py` - config loader, logging helpers, small GUI utilities
  - `style_helper.py` and `_panel.py` files - UI components
- `voice_messages/` - runtime recordings and received messages (created at runtime)
- `requirements.txt` - Python dependencies
- `tests/` - unit tests

---

## Troubleshooting

- If `meshtastic` or `pyaudio` imports fail, confirm they are installed in
  the active virtual environment.
- If the Meshtastic device is not found by serial, ensure the COM port is
  correct and accessible by the running user.
- The GUI intentionally uses explicit imports for components; a missing
  component file will produce an import error at startup so the problem is
  visible immediately.

---

## Development notes

- Use the `config` argument when creating handlers in code to ensure
  configuration is explicit (e.g., `AudioHandler(self.log, config)`).
- Prefer the protocol getters (e.g., `get_chunk_sizes(config)`) to avoid
  relying on import-time constants.

---

## License & Contact

This project is published by Akita Engineering and is licensed under the
GNU GPL v3 (see `LICENSE` in the repository root). For questions contact
info@akitaengineering.com.


