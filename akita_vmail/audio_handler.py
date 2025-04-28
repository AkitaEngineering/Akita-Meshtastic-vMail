# -*- coding: utf-8 -*-
"""
File: audio_handler.py
Description: Handles audio recording, playback, compression, and WAV file
             operations using PyAudio and standard libraries. Reads config
             from utils.load_config().
"""
import pyaudio      # For audio I/O
import wave         # For reading/writing WAV files
import os           # For path manipulation, directory creation
import time         # For sleep
import zlib         # For data compression/decompression
import audioop      # For audio operations like rate conversion, bit depth change
import struct       # For packing/unpacking header data
import numpy as np  # For numerical operations (dynamic range compression)
import logging      # For logging messages
from datetime import datetime # For timestamps in filenames

# Import config loading utility
try:
    from utils import load_config
except ImportError:
    logging.critical("FATAL: Cannot import load_config from utils. Ensure utils.py is present.")
    # Define fallback defaults directly here if utils is missing (less ideal)
    DEFAULT_AUDIO_CONFIG = {
        "default_quality": "Low",
        "default_length_sec": 3,
        "quality_rates_hz": {"Ultra Low": 4000, "Very Low": 8000, "Low": 11025}
    }
    AUDIO_CONFIG = DEFAULT_AUDIO_CONFIG
else:
    # Load configuration
    CONFIG = load_config()
    AUDIO_CONFIG = CONFIG.get("audio", DEFAULT_AUDIO_CONFIG) # Fallback if audio section missing


class AudioHandler:
    """Manages audio recording, playback, and processing."""

    def __init__(self, log_callback: callable):
        """
        Initialize the AudioHandler.

        Args:
            log_callback: A function to call for logging messages (e.g., self.log from the GUI class).
        """
        self.log = log_callback # Use the passed-in logging function
        self.chunk = 1024       # Size of audio chunks read/written at a time
        self.format = pyaudio.paInt16 # Audio format (16-bit integers)
        self.channels = 1       # Mono audio
        self.voice_message_dir = "voice_messages" # Directory to store recordings

        # --- Audio Quality Settings from Config ---
        self.quality_rates = AUDIO_CONFIG.get("quality_rates_hz", DEFAULT_AUDIO_CONFIG["quality_rates_hz"])
        self.default_quality = AUDIO_CONFIG.get("default_quality", DEFAULT_AUDIO_CONFIG["default_quality"])
        # Ensure default quality exists in rates, else pick first available
        if self.default_quality not in self.quality_rates and self.quality_rates:
             self.default_quality = list(self.quality_rates.keys())[0]
             self.log(f"Configured default quality '{AUDIO_CONFIG.get('default_quality')}' not found in rates. Using '{self.default_quality}'.", logging.WARNING)
        elif not self.quality_rates: # Handle empty rates config
             self.quality_rates = DEFAULT_AUDIO_CONFIG["quality_rates_hz"]
             self.default_quality = DEFAULT_AUDIO_CONFIG["default_quality"]
             self.log("Audio quality rates missing in config. Using defaults.", logging.WARNING)

        self.rate = self.quality_rates.get(self.default_quality, 11025) # Current sample rate, fallback

        # --- Recording State from Config ---
        self.record_seconds = AUDIO_CONFIG.get("default_length_sec", DEFAULT_AUDIO_CONFIG["default_length_sec"])
        self.recording = False  # Flag indicating if recording is active
        self.frames = []        # Buffer to store recorded audio frames

        # --- Playback State ---
        self.playing = False    # Flag indicating if playback is active
        self.wf = None          # Wave file object for playback

        # --- PyAudio Instance and Stream ---
        try:
            self.p = pyaudio.PyAudio() # Initialize PyAudio
            self.stream = None         # Placeholder for the PyAudio stream object
        except Exception as e:
            self.log(f"FATAL: Failed to initialize PyAudio: {e}", logging.CRITICAL)
            self.p = None # Indicate PyAudio failed

        # Ensure the voice message directory exists
        try:
            os.makedirs(self.voice_message_dir, exist_ok=True)
        except OSError as e:
             self.log(f"Error creating directory {self.voice_message_dir}: {e}", logging.ERROR)

        self.log(f"AudioHandler initialized. Default Quality: {self.default_quality} ({self.rate}Hz), Default Length: {self.record_seconds}s")


    def set_recording_params(self, seconds_str: str, quality: str) -> int:
        """
        Set recording length and quality (sample rate).

        Args:
            seconds_str: The desired recording length as a string.
            quality: The desired quality level key (e.g., "Low").

        Returns:
            The validated and potentially clamped recording length in seconds.
        """
        # Validate and set recording length
        try:
            rec_sec = int(seconds_str)
            if not (1 <= rec_sec <= 30): # Clamp duration between 1 and 30 seconds
                self.log(f"Recording length {rec_sec}s out of range (1-30s). Clamping.")
                self.record_seconds = max(1, min(30, rec_sec))
            else:
                 self.record_seconds = rec_sec
        except ValueError:
            default_len = AUDIO_CONFIG.get("default_length_sec", 3)
            self.log(f"Invalid recording length '{seconds_str}'. Using default {default_len}s.", logging.WARNING)
            self.record_seconds = default_len

        # Validate and set quality/sample rate
        if quality in self.quality_rates:
            new_rate = self.quality_rates[quality]
            if new_rate != self.rate:
                self.rate = new_rate
                self.log(f"Recording quality set to '{quality}' ({self.rate} Hz)")
        else:
            # Fallback to default if invalid key provided
            default_rate = self.quality_rates.get(self.default_quality, 11025)
            self.log(f"Invalid quality key '{quality}'. Using default '{self.default_quality}' ({default_rate}Hz).", logging.WARNING)
            self.rate = default_rate

        return self.record_seconds # Return the potentially clamped value

    def start_recording(self) -> tuple[bool, str | None]:
        """
        Start audio recording using a non-blocking stream callback.

        Returns:
            A tuple (success: bool, filepath: str | None).
            Filepath is the path where the recording will be saved if successful.
        """
        if not self.p:
             self.log("Cannot record: PyAudio not initialized.", logging.ERROR)
             return False, None
        if self.recording:
            self.log("Already recording.", logging.WARNING)
            return False, None

        self.recording = True
        self.frames = [] # Clear buffer for new recording
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        # Ensure filepath is unique even if clock resolution is low
        filepath = os.path.join(self.voice_message_dir, f"recording_{timestamp}_{uuid.uuid4().hex[:6]}.wav")

        try:
            self.stream = self.p.open(format=self.format,
                                      channels=self.channels,
                                      rate=self.rate,
                                      input=True,
                                      frames_per_buffer=self.chunk,
                                      stream_callback=self._recording_callback)
            self.log(f"Recording for {self.record_seconds} seconds at {self.rate}Hz...")
            self.stream.start_stream()
            return True, filepath
        except OSError as e:
             self.log(f"OS Error starting recording stream (device issue?): {e}", logging.ERROR)
             self.recording = False
             if self.stream: self.stream.close()
             self.stream = None
             return False, None
        except Exception as e:
            self.log(f"Error starting recording stream: {e}", logging.ERROR)
            self.recording = False
            if self.stream: self.stream.close()
            self.stream = None
            return False, None

    def _recording_callback(self, in_data, frame_count, time_info, status):
        """Internal callback for the PyAudio recording stream."""
        if self.recording:
            self.frames.append(in_data)
            return (in_data, pyaudio.paContinue)
        else:
            return (in_data, pyaudio.paComplete)

    def stop_recording(self, filepath: str) -> bool:
        """
        Stop the audio recording stream and save the buffered frames to a WAV file.

        Args:
            filepath: The path to save the WAV file.

        Returns:
            True if recording stopped and saved successfully, False otherwise.
        """
        if not self.recording:
            return False

        self.recording = False # Signal the callback to complete
        time.sleep(0.1) # Allow callback to process last chunk

        if self.stream:
            try:
                if self.stream.is_active(): self.stream.stop_stream()
                self.stream.close()
                self.log("Recording stream stopped and closed.")
            except Exception as e:
                self.log(f"Error stopping/closing recording stream: {e}", logging.WARNING)
            finally:
                self.stream = None

        if not self.frames:
            self.log("No frames recorded.", logging.WARNING)
            return False

        # --- Save the recording ---
        try:
            with wave.open(filepath, 'wb') as wf:
                wf.setnchannels(self.channels)
                wf.setsampwidth(self.p.get_sample_size(self.format))
                wf.setframerate(self.rate)
                wf.writeframes(b''.join(self.frames))
            self.log(f"Recording successfully saved to {filepath}")
            self.frames = []
            return True
        except wave.Error as e:
             self.log(f"Wave library error saving recording to {filepath}: {e}", logging.ERROR)
             return False
        except Exception as e:
            self.log(f"Unexpected error saving recording to {filepath}: {e}", logging.ERROR)
            return False
        finally:
            self.frames = [] # Clear buffer even on failure


    def start_playback(self, filepath: str) -> bool:
        """
        Start audio playback from a WAV file using a non-blocking stream callback.

        Args:
            filepath: The path to the WAV file to play.

        Returns:
            True if playback started successfully, False otherwise.
        """
        if not self.p:
             self.log("Cannot play: PyAudio not initialized.", logging.ERROR)
             return False
        if self.playing:
            self.log("Already playing.", logging.WARNING)
            return False
        if not os.path.isfile(filepath): # More specific check
            self.log(f"Playback file not found or is not a file: {filepath}", logging.ERROR)
            return False

        self.playing = True
        try:
            self.wf = wave.open(filepath, 'rb')
            self.stream = self.p.open(format=self.p.get_format_from_width(self.wf.getsampwidth()),
                                      channels=self.wf.getnchannels(),
                                      rate=self.wf.getframerate(),
                                      output=True,
                                      frames_per_buffer=self.chunk,
                                      stream_callback=self._playback_callback)
            self.log(f"Playing {os.path.basename(filepath)}...")
            self.stream.start_stream()
            return True
        except wave.Error as e:
             self.log(f"Error opening WAV file {filepath}: {e}. Corrupted or invalid format?", logging.ERROR)
             self.playing = False
             if self.wf: self.wf.close()
             self.wf = None
             if self.stream: self.stream.close()
             self.stream = None
             return False
        except OSError as e:
             self.log(f"OS Error starting playback stream (device issue?): {e}", logging.ERROR)
             self.playing = False
             if self.wf: self.wf.close()
             self.wf = None
             if self.stream: self.stream.close()
             self.stream = None
             return False
        except Exception as e:
            self.log(f"Error starting playback stream for {filepath}: {e}", logging.ERROR)
            self.playing = False
            if self.wf: self.wf.close()
            self.wf = None
            if self.stream: self.stream.close()
            self.stream = None
            return False

    def _playback_callback(self, in_data, frame_count, time_info, status):
        """Internal callback for the PyAudio playback stream."""
        if not self.playing or not self.wf:
            return (None, pyaudio.paComplete)

        try:
            data = self.wf.readframes(frame_count)
        except Exception as e:
             self.log(f"Error reading frames during playback: {e}", logging.ERROR)
             data = b'' # Treat as end of file on error

        playback_status = pyaudio.paContinue if data else pyaudio.paComplete
        if not self.playing and playback_status == pyaudio.paContinue:
             playback_status = pyaudio.paComplete
             # Calculate silence bytes needed
             bytes_per_frame = self.wf.getsampwidth() * self.wf.getnchannels()
             silence = b'\x00' * (frame_count * bytes_per_frame)
             data = silence

        return (data, playback_status)

    def stop_playback(self):
        """Stop the currently playing audio stream."""
        if not self.playing:
            return
        self.playing = False
        self.log("Playback stop requested.")

    def playback_finished(self):
        """Clean up resources after playback finishes or is stopped."""
        was_playing = self.playing
        self.playing = False

        if self.stream:
            try:
                is_active = False
                try: is_active = self.stream.is_active()
                except Exception: pass # Ignore errors if stream is bad

                if is_active: self.stream.stop_stream()
                self.stream.close()
                if was_playing: self.log("Playback stream stopped and closed.")
            except Exception as e:
                self.log(f"Error stopping/closing playback stream during cleanup: {e}", logging.WARNING)
            finally:
                self.stream = None
        if self.wf:
            try: self.wf.close()
            except Exception as e: self.log(f"Error closing wave file during cleanup: {e}", logging.WARNING)
            finally: self.wf = None

    def compress_audio(self, wav_path: str, quality: str) -> bytes | None:
        """
        Compress audio file for transmission using the selected quality setting.
        """
        self.log(f"Compressing '{os.path.basename(wav_path)}' with quality '{quality}'")
        try:
            # --- 1. Read WAV File ---
            with wave.open(wav_path, 'rb') as wf:
                channels = wf.getnchannels()
                original_sample_width = wf.getsampwidth()
                original_rate = wf.getframerate()
                num_frames = wf.getnframes()
                frames = wf.readframes(num_frames)
                original_size = len(frames)
                self.log(f"Read WAV: {original_rate}Hz, {original_sample_width*8}-bit, "
                         f"{channels}ch, {num_frames} frames, {original_size} bytes")

            # --- 2. Determine Target Parameters ---
            target_rate = self.quality_rates.get(quality, self.rate) # Fallback to current rate
            self.log(f"Target Rate: {target_rate}Hz")

            # --- 3. Downsample (if necessary) ---
            current_frames = frames
            current_rate = original_rate
            if original_rate > target_rate:
                self.log(f"Downsampling from {original_rate}Hz to {target_rate}Hz...")
                try:
                    current_frames, _ = audioop.ratecv(frames, original_sample_width, channels,
                                                       original_rate, target_rate, None)
                    current_rate = target_rate
                    self.log(f"Downsampled size: {len(current_frames)} bytes")
                except audioop.error as e:
                    self.log(f"Audioop error during downsampling: {e}. Skipping.", logging.WARNING)
                    current_frames = frames
                    current_rate = original_rate
            else:
                 self.log("Skipping downsampling (Original rate <= Target rate)")

            # --- 4. Reduce Bit Depth (Optional: Only for Ultra Low) ---
            current_sample_width = original_sample_width
            if quality == "Ultra Low" and original_sample_width > 1:
                self.log("Converting to 8-bit for Ultra Low quality...")
                try:
                    current_frames = audioop.lin2lin(current_frames, original_sample_width, 1)
                    current_sample_width = 1
                    self.log(f"Size after 8-bit conversion: {len(current_frames)} bytes")
                except audioop.error as e:
                     self.log(f"Audioop error during bit depth reduction: {e}. Skipping.", logging.WARNING)
            else:
                 self.log(f"Keeping original bit depth ({current_sample_width*8}-bit)")

            # --- 5. Create Header ---
            header_str = f"{current_rate},{channels},{current_sample_width}"
            header_bytes = header_str.encode('utf-8')
            header_size = len(header_bytes)
            if header_size > 255:
                raise ValueError(f"Header size ({header_size}) exceeds 1 byte limit.")

            data_with_header = struct.pack('!B', header_size) + header_bytes + current_frames
            self.log(f"Created header: '{header_str}' ({header_size} bytes)")

            # --- 6. Compress with zlib ---
            self.log("Compressing data with zlib (level 9)...")
            compressed_data = zlib.compress(data_with_header, level=9)

            compressed_size = len(compressed_data)
            if original_size > 0:
                 compression_ratio = original_size / compressed_size
                 self.log(f"Compression complete. Original: {original_size} bytes, Compressed: {compressed_size} bytes (Ratio: {compression_ratio:.2f}x)")
            else:
                 self.log(f"Compression complete. Original: 0 bytes, Compressed: {compressed_size} bytes")

            return compressed_data

        except FileNotFoundError:
            self.log(f"Error: Input WAV file not found: {wav_path}", logging.ERROR)
            return None
        except wave.Error as e:
            self.log(f"Error reading WAV file '{os.path.basename(wav_path)}': {e}", logging.ERROR)
            return None
        except Exception as e:
            self.log(f"Unexpected error during audio compression for '{os.path.basename(wav_path)}': {e}", logging.ERROR)
            import traceback
            self.log(traceback.format_exc(), logging.ERROR)
            return None

    def create_wav_from_compressed(self, compressed_data: bytes, filename: str) -> bool:
        """
        Decompress zlib data, parse the prepended header, and create a WAV file.
        """
        self.log(f"Decompressing and creating WAV file: {filename}")
        try:
            # --- 1. Decompress zlib data ---
            data_with_header = zlib.decompress(compressed_data)

            # --- 2. Parse Header ---
            header_size = struct.unpack('!B', data_with_header[0:1])[0]
            header_bytes = data_with_header[1 : 1 + header_size]
            audio_data = data_with_header[1 + header_size :]
            header_str = header_bytes.decode('utf-8')
            header_parts = header_str.split(',')
            if len(header_parts) != 3:
                raise ValueError(f"Invalid header format after decompression: '{header_str}'")

            sample_rate = int(header_parts[0])
            channels = int(header_parts[1])
            sample_width = int(header_parts[2])
            self.log(f"Parsed Header - Rate: {sample_rate}, Channels: {channels}, Width: {sample_width}")

            # --- 3. Create WAV file ---
            with wave.open(filename, 'wb') as wf:
                wf.setnchannels(channels)
                wf.setsampwidth(sample_width)
                wf.setframerate(sample_rate)
                wf.writeframes(audio_data)

            self.log(f"Successfully created WAV file: {filename}")
            return True

        except zlib.error as e:
            self.log(f"Zlib decompression error for {filename}: {e}", logging.ERROR)
            return False
        except (struct.error, ValueError, IndexError, UnicodeDecodeError) as e:
            self.log(f"Error parsing header or data for {filename}: {e}", logging.ERROR)
            return False
        except wave.Error as e:
             self.log(f"Error writing WAV file {filename}: {e}", logging.ERROR)
             return False
        except Exception as e:
            self.log(f"Unexpected error creating WAV file {filename}: {e}", logging.ERROR)
            import traceback
            self.log(traceback.format_exc(), logging.ERROR)
            return False

    def cleanup(self):
        """Clean up PyAudio resources upon application exit."""
        self.log("Cleaning up AudioHandler...")
        if self.recording: self.stop_recording("dummy_cleanup.wav")
        if self.playing: self.stop_playback()

        if self.p:
            try:
                self.p.terminate()
                self.log("PyAudio terminated.")
            except Exception as e:
                 self.log(f"Error terminating PyAudio: {e}", logging.WARNING)
        else:
             self.log("PyAudio was not initialized.", logging.WARNING)

