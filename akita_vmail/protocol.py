# -*- coding: utf-8 -*-
"""
File: protocol.py
Description: Defines the communication protocol, message formats, constants,
             and related functions for Akita vMail. Reads configuration
             from utils.load_config().
"""
import zlib
import json
import base64
import uuid
import math
import struct
import logging

# Import config loading utility (use cached getter when available)
try:
    from utils import get_config
except Exception:
    get_config = None

# Default configuration used if `get_config()` is unavailable
DEFAULT_CONFIG = {
    "meshtastic_port_num": 256,
    "chunking": {
        "sizes": {"Small": 150, "Medium": 180, "Large": 200},
        "default_key": "Medium",
        "retry_count": 2,
        "retry_delay_sec": 1.0,
        "receive_timeout_sec": 60
    }
}

# The protocol module no longer stores config-bound module-level constants.
# Callers should pass an explicit `config` dict into the getters below.


## Accessor functions for other modules to use (avoids importing constants at module import time)
def get_private_app_port(config: dict | None = None) -> int:
    """Return the configured private app port. If `config` is provided use it,
    otherwise fall back to the last-refreshed module value.
    """
    if isinstance(config, dict):
        return config.get("meshtastic_port_num", DEFAULT_CONFIG.get("meshtastic_port_num", 256))
    return PRIVATE_APP_PORT

def get_chunk_sizes(config: dict | None = None) -> dict:
    if isinstance(config, dict):
        return config.get("chunking", DEFAULT_CONFIG["chunking"]).get("sizes", DEFAULT_CONFIG["chunking"]["sizes"])
    return CHUNK_SIZES

def get_default_chunk_size_key(config: dict | None = None) -> str:
    if isinstance(config, dict):
        chunk_cfg = config.get("chunking", DEFAULT_CONFIG["chunking"]) or DEFAULT_CONFIG["chunking"]
        key = chunk_cfg.get("default_key", DEFAULT_CONFIG["chunking"]["default_key"])
        sizes = chunk_cfg.get("sizes", DEFAULT_CONFIG["chunking"]["sizes"]) or DEFAULT_CONFIG["chunking"]["sizes"]
        if key not in sizes and sizes:
            return list(sizes.keys())[0]
        return key
    return DEFAULT_CHUNK_SIZE_KEY

def get_default_chunk_size(config: dict | None = None) -> int:
    if isinstance(config, dict):
        sizes = get_chunk_sizes(config)
        key = get_default_chunk_size_key(config)
        return sizes.get(key, 180)
    return DEFAULT_CHUNK_SIZE

def get_chunk_retry_count(config: dict | None = None) -> int:
    if isinstance(config, dict):
        return config.get("chunking", DEFAULT_CONFIG["chunking"]).get("retry_count", DEFAULT_CONFIG["chunking"]["retry_count"])
    return CHUNK_RETRY_COUNT

def get_chunk_retry_delay(config: dict | None = None) -> float:
    if isinstance(config, dict):
        return config.get("chunking", DEFAULT_CONFIG["chunking"]).get("retry_delay_sec", DEFAULT_CONFIG["chunking"]["retry_delay_sec"])
    return CHUNK_RETRY_DELAY

def get_chunk_timeout(config: dict | None = None) -> int:
    if isinstance(config, dict):
        return config.get("chunking", DEFAULT_CONFIG["chunking"]).get("receive_timeout_sec", DEFAULT_CONFIG["chunking"]["receive_timeout_sec"])
    return CHUNK_TIMEOUT

# --- Other Constants ---
BROADCAST_ADDR = "^all"     # Meshtastic broadcast address alias

# --- Message Types --- (Used in the 'type' field of the JSON payload)
MSG_TYPE_VOICE_CHUNK = "voice_chunk"    # A chunk of a larger voice message
MSG_TYPE_ACK = "ack"                    # Acknowledgement for a received chunk
MSG_TYPE_TEST = "test"                  # A simple text message for testing connectivity
MSG_TYPE_COMPLETE_VOICE = "complete_voice" # A voice message sent in a single packet

# --- Protocol Functions ---

def calculate_crc32(data: bytes) -> int:
    """Calculate CRC32 checksum for byte data."""
    return zlib.crc32(data) & 0xffffffff # Ensure unsigned 32-bit integer

def create_chunk_payload(chunk_id: str, chunk_num: int, total_chunks: int, chunk_data: bytes) -> bytes:
    """
    Create the JSON payload (as bytes) for a voice message chunk.
    Includes CRC32 checksum calculated on the raw chunk data.
    """
    encoded_data = base64.b64encode(chunk_data).decode('utf-8')
    crc = calculate_crc32(chunk_data)
    payload = {
        "type": MSG_TYPE_VOICE_CHUNK,
        "chunk_id": chunk_id,
        "chunk_num": chunk_num,
        "total_chunks": total_chunks,
        "crc32": crc,
        "data": encoded_data
    }
    return json.dumps(payload).encode('utf-8')

def create_ack_payload(chunk_id: str, chunk_num: int) -> bytes:
    """Create the JSON payload (as bytes) for an ACK message."""
    payload = {
        "type": MSG_TYPE_ACK,
        "ack_id": chunk_id,
        "chunk_num": chunk_num
    }
    return json.dumps(payload).encode('utf-8')

def create_test_payload(message_text: str) -> bytes:
    """Create the JSON payload (as bytes) for a test message."""
    payload = {
        "type": MSG_TYPE_TEST,
        "test": message_text
    }
    return json.dumps(payload).encode('utf-8')

def create_complete_voice_payload(compressed_voice_data: bytes, timestamp: str) -> bytes:
    """
    Create the JSON payload (as bytes) for a non-chunked voice message.
    Includes CRC32 checksum calculated on the raw compressed data.
    """
    encoded_data = base64.b64encode(compressed_voice_data).decode('utf-8')
    crc = calculate_crc32(compressed_voice_data)
    payload = {
        "type": MSG_TYPE_COMPLETE_VOICE,
        "crc32": crc,
        "voice_data": encoded_data,
        "timestamp": timestamp
    }
    return json.dumps(payload).encode('utf-8')

def parse_payload(data_bytes: bytes) -> dict | None:
    """Parse incoming JSON payload bytes into a Python dictionary."""
    try:
        payload_str = data_bytes.decode('utf-8')
        return json.loads(payload_str)
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        logging.error(f"Failed to parse payload: {e}. Payload start: {data_bytes[:50]}...")
        return None
    except Exception as e:
        logging.error(f"Unexpected error parsing payload: {e}")
        return None

def verify_chunk_crc(chunk_payload: dict) -> tuple[bool, bytes | None]:
    """
    Verify the CRC32 checksum of a received voice chunk payload.
    Returns (True, raw_chunk_data) if valid, otherwise (False, None).
    """
    if not isinstance(chunk_payload, dict): return False, None # Basic type check
    if not all(k in chunk_payload for k in ['data', 'crc32', 'chunk_num', 'chunk_id']):
        logging.warning(f"Chunk payload missing required fields: {chunk_payload}")
        return False, None

    try:
        received_crc = chunk_payload['crc32']
        encoded_data = chunk_payload['data']
        chunk_num = chunk_payload['chunk_num']
        chunk_id = chunk_payload['chunk_id']

        raw_chunk_data = base64.b64decode(encoded_data)
        calculated_crc = calculate_crc32(raw_chunk_data)

        if received_crc == calculated_crc:
            return True, raw_chunk_data
        else:
            logging.warning(f"CRC mismatch for chunk {chunk_num}/{chunk_payload.get('total_chunks','?')} "
                            f"(ID: {chunk_id}): Expected {received_crc}, Calculated {calculated_crc}")
            return False, None
    except (base64.binascii.Error, TypeError) as e:
        logging.error(f"Error decoding base64 or calculating CRC for chunk "
                      f"{chunk_payload.get('chunk_num','?')}: {e}")
        return False, None
    except Exception as e:
        logging.error(f"Unexpected error verifying chunk CRC: {e}")
        return False, None

def verify_complete_voice_crc(payload: dict) -> tuple[bool, bytes | None]:
    """
    Verify the CRC32 checksum of a received complete (non-chunked) voice message.
    Returns (True, raw_compressed_voice_data) if valid, otherwise (False, None).
    """
    if not isinstance(payload, dict): return False, None # Basic type check
    if not all(k in payload for k in ['voice_data', 'crc32']):
        logging.warning(f"Complete voice payload missing required fields: {payload}")
        return False, None

    try:
        received_crc = payload['crc32']
        encoded_data = payload['voice_data']
        raw_compressed_voice_data = base64.b64decode(encoded_data)
        calculated_crc = calculate_crc32(raw_compressed_voice_data)

        if received_crc == calculated_crc:
            return True, raw_compressed_voice_data
        else:
            logging.warning(f"CRC mismatch for complete voice message: "
                            f"Expected {received_crc}, Calculated {calculated_crc}")
            return False, None
    except (base64.binascii.Error, TypeError) as e:
        logging.error(f"Error decoding base64 or calculating CRC for complete voice message: {e}")
        return False, None
    except Exception as e:
        logging.error(f"Unexpected error verifying complete voice CRC: {e}")
        return False, None

def generate_unique_id() -> str:
    """Generate a short, reasonably unique ID for messages."""
    return str(uuid.uuid4())[:8]

def split_data_into_chunks(data: bytes, max_chunk_payload_size: int) -> list[bytes]:
    """
    Splits raw byte data into multiple smaller byte chunks suitable for sending.
    Aims to ensure the *final JSON payload* for each chunk does not exceed limit.
    """
    # Dynamically estimate JSON fixed overhead by serializing a sample payload
    # that includes all keys except the base64 data. This provides a safer
    # estimate than a hardcoded constant.
    try:
        sample_payload = {
            "type": MSG_TYPE_VOICE_CHUNK,
            "chunk_id": "00000000",
            "chunk_num": 1,
            "total_chunks": 1,
            "crc32": 0,
            "data": ""  # empty data to measure fixed overhead
        }
        json_fixed_overhead = len(json.dumps(sample_payload).encode('utf-8'))
    except Exception:
        json_fixed_overhead = 150

    max_b64_data_size = max_chunk_payload_size - json_fixed_overhead
    if max_b64_data_size <= 10:
        raise ValueError(f"max_chunk_payload_size ({max_chunk_payload_size}) is too small "
                         f"for estimated JSON overhead ({json_fixed_overhead}).")

    # Max raw data size = max_b64 * 3 / 4. Subtract buffer for padding.
    max_raw_data_size_per_chunk = int(max_b64_data_size * 0.75) - 2

    if max_raw_data_size_per_chunk <= 0:
         raise ValueError(f"Effective max_raw_data_size ({max_raw_data_size_per_chunk}) is too small. "
                          f"Increase max_chunk_payload_size or reduce overhead estimate.")

    logging.debug(f"Splitting data: Max payload={max_chunk_payload_size}, "
                  f"Est. overhead={json_fixed_overhead}, "
                  f"Max raw data/chunk={max_raw_data_size_per_chunk}")

    num_chunks = math.ceil(len(data) / max_raw_data_size_per_chunk)
    if num_chunks == 0 and len(data) > 0:
        num_chunks = 1

    chunks = []
    for i in range(num_chunks):
        start_index = i * max_raw_data_size_per_chunk
        end_index = min(start_index + max_raw_data_size_per_chunk, len(data))
        chunk = data[start_index:end_index]
        if chunk:
            chunks.append(chunk)
        else:
             logging.warning(f"Generated an empty chunk during splitting (Index {i}). Check logic.")

    logging.debug(f"Data length {len(data)} split into {len(chunks)} chunks.")
    return chunks

logging.info("Protocol module loaded. Use getters with explicit config dict to access runtime values.")

