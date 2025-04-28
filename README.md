# Akita vMail - Meshtastic Voice Messenger

From [Akita Engineering](https://www.akitaengineering.com)

Akita vMail sets the standard for reliable voice communication over Meshtastic networks.  
This robust Python application enables sending and receiving short voice messages using a connected Meshtastic device.  
Engineered for resilience, this version incorporates CRC32 checksums for data integrity and a basic Acknowledgement (ACK) system for enhanced reliability of chunked messages, ensuring your voice gets through even in challenging network conditions.  
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
2. Save Files
Save all the provided code files (.py, .json, .txt) into the akita_vmail directory.

3. Install Dependencies
```bash
pip install -r requirements.txt
```
Note: Installing PyAudio might require additional system dependencies (e.g., portaudio19-dev on Debian/Ubuntu or portaudio via Homebrew on macOS).
Refer to the PyAudio documentation for your OS.

4. Create Voice Message Directory
```bash
mkdir voice_messages
```
This is where recordings and received messages will be stored.

5. (Optional) Edit Configuration
Modify config.json to change default settings like the Meshtastic port number or chunking parameters if needed.

Usage
1. Connect your Meshtastic device via USB or ensure it's reachable via IP.

2. Run the application:
```bash
python main.py
```
3. In the GUI:

- Enter/select the connection target (COM port or IP address).
- Click Connect.
- Check the log output for connection status and list of known nodes.
- The status bar will show your node information upon connection.

4. Adjust recording settings (Length, Quality, Chunk Size) via the GUI dropdowns/entries.

5. Record:

- Click 🎤 Record.
- It will record for the specified duration or until you click ⏹ Stop Rec.

6. Send:

- After recording, click ✉️ Send.
- The message will be compressed, chunked (if needed), and sent.
- Check the log for sending progress.

7. Receive:

- Incoming voice messages (chunked or complete) will appear in the "Messages" list after successful CRC validation.

- Text messages will also appear.

8. Playback:

- Select a received voice message (🔊 icon).

- Click ▶ Play.

- Use ⏹ Stop to halt playback.

9. Clear Log:

- Click the Clear Log button to empty the log output area.

Protocol Details (v2 - CRC/ACK)
- Messages use the Meshtastic port number defined in config.json (meshtastic_port_num, default 256).

- Payloads are JSON formatted.

Message Types
- complete_voice

- voice_chunk

- ack

- test

Complete Voice Messages
- Contain:

- - voice_data (base64 encoded compressed audio + header)

- - timestamp

- - crc32 checksum (calculated on the raw compressed audio + header)

Chunked Messages
Each chunk payload includes:

- type: "voice_chunk"

- chunk_id

- chunk_num

- total_chunks

- crc32 (calculated on raw chunk data before base64 encoding)

- data (base64 encoded chunk data)

Acknowledgements (ACKs)
- Sent by receiver upon successful CRC validation of a voice_chunk.

- Payload includes:

-- type: "ack"

-- ack_id (matching the chunk_id)

-- chunk_num

- ACKs are sent directly back to the original sender.

⚠️ Disclaimer
This is experimental software provided by Akita Engineering. Use it at your own risk.
Network performance, reliability, and successful message delivery depend heavily on Meshtastic network conditions (distance, obstructions, node density, channel utilization).
The ACK mechanism confirms chunk reception by the next hop or end device, but it does not guarantee successful reassembly if other chunks are lost.


