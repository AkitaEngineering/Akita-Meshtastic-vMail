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


# Akita vMail - Meshtastic Voice Messenger

From [Akita Engineering](https://www.akitaengineering.com)

Akita vMail is a desktop application for sending and receiving short voice
messages over Meshtastic networks. The project focuses on resilience and
observability: messages include CRC32 checks for integrity and a simple ACK
scheme to support chunked transfers over lossy links.

This repository contains the application code (under `akita_vmail/`),
configuration defaults, and a small test suite. The GUI uses Tkinter and the
core code is written for Python 3.8+.

---

## What's changed (recent refactor)

- Centralized configuration loader in `akita_vmail/utils.py` with a cached
	`get_config()` and a recursive merge on `load_config()`.
- Protocol constants moved out of import-time module state; use the
	config-aware getters in `akita_vmail/protocol.py` (e.g. `get_chunk_sizes(config)`).
- Dependency injection: `AudioHandler`, `MeshtasticHandler`, and the GUI
	receive an explicit `config` dict instead of loading globals at import time.
- GUI decomposed into smaller components under `akita_vmail/` (e.g.
	`connection_panel.py`, `recording_panel.py`, `controls_panel.py`, etc.) and
	`style_helper.py` centralizes theme/styling.
- Fail-fast imports: components use explicit package-relative imports so
	missing modules surface at startup (no silent fallback imports remain).

---

## Quickstart (developer / local run)

1. Create and activate a virtual environment (recommended):

```bash
python -m venv .venv
# Unix/macOS
source .venv/bin/activate
# Windows (PowerShell)
.venv\Scripts\Activate.ps1
```

2. Install Python dependencies:

```bash
python -m pip install --upgrade pip
python -m pip install -r akita_vmail/requirements.txt
```

3. Ensure a directory exists for voice files (defaults to `voice_messages`):

```bash
mkdir -p voice_messages
```

4. (Optional) Edit `config.json` in the project root to change defaults.

5. Run the application from the repository root:

```bash
python -m akita_vmail.main
# or
python akita_vmail/main.py
```

Notes:
- On Windows, installing `pyaudio` may be easier via `pipwin`.
- Running the GUI headlessly (in CI) requires mocking audio and meshtastic
	dependencies; the test suite already includes test-time fakes.

---

## Configuration

Configuration defaults live in `akita_vmail/utils.py` as `DEFAULT_CONFIG`. A
local `config.json` (in repository root) will be merged recursively over the
defaults when present. Use `get_config()` to access the cached config at
runtime; call `load_config()` to force a reload.

Key config sections:
- `meshtastic_port_num`: default app port number used when sending data
- `chunking`: sizes, default key, retry_count, retry delays and timeouts
- `audio`: default quality keys and sampling rates, default recording length

---

## Running Tests

Unit tests use Python's `unittest`. To run tests locally:

```bash
python -m unittest discover -v
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

This project is published by Akita Engineering. See the `LICENSE` file in
the repository root for licensing details. For questions contact
info@akitaengineering.com.
Run from the project root with the venv Python (or after activating the venv):



```powershell

python akita_vmail/main.py

