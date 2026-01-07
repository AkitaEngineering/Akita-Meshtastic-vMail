import sys
import importlib
import types
import os
import wave
import tempfile
from unittest import TestCase

# Create a fake minimal pyaudio module before importing the audio handler
fake_pyaudio = types.ModuleType('pyaudio')
fake_pyaudio.paInt16 = 8
fake_pyaudio.paContinue = 0
fake_pyaudio.paComplete = 1

class FakeStream:
    def __init__(self):
        self._active = False
    def start_stream(self):
        self._active = True
    def stop_stream(self):
        self._active = False
    def is_active(self):
        return self._active
    def close(self):
        self._active = False

class FakePyAudio:
    def __init__(self):
        pass
    def get_sample_size(self, fmt):
        return 2
    def get_format_from_width(self, w):
        return 1
    def open(self, *args, **kwargs):
        return FakeStream()
    def terminate(self):
        pass

fake_pyaudio.PyAudio = FakePyAudio
sys.modules['pyaudio'] = fake_pyaudio
# Provide a minimal `audioop` module for environments lacking it
fake_audioop = types.ModuleType('audioop')
def _ratecv(frames, sample_width, channels, oldrate, newrate, state):
    return frames, state
def _lin2lin(frames, oldwidth, newwidth):
    return frames
fake_audioop.ratecv = _ratecv
fake_audioop.lin2lin = _lin2lin
fake_audioop.error = Exception
sys.modules['audioop'] = fake_audioop

# Now import the module under test
from akita_vmail.audio_handler import AudioHandler

class TestAudioHandler(TestCase):
    def setUp(self):
        self.logs = []
        self.log = lambda msg, level=None: self.logs.append((msg, level))

    def test_uses_injected_config(self):
        cfg = {
            'audio': {
                'voice_message_dir': 'test_vox',
                'quality_rates_hz': {'Low': 11025},
                'default_quality': 'Low',
                'default_length_sec': 2
            }
        }
        ah = AudioHandler(self.log, config=cfg)
        self.assertEqual(ah.voice_message_dir, 'test_vox')
        self.assertEqual(ah.rate, 11025)
        # cleanup created directory
        if os.path.isdir('test_vox'):
            for f in os.listdir('test_vox'):
                os.remove(os.path.join('test_vox', f))
            os.rmdir('test_vox')

    def test_compress_and_create_wav_roundtrip(self):
        # create a small silent wav file
        fd, path = tempfile.mkstemp(suffix='.wav')
        os.close(fd)
        try:
            with wave.open(path, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(11025)
                wf.writeframes(b'\x00' * 11025 * 2)  # 1 second silence

            cfg = {'audio': {'quality_rates_hz': {'Low': 11025}, 'default_quality': 'Low'}}
            ah = AudioHandler(self.log, config=cfg)
            compressed = ah.compress_audio(path, 'Low')
            self.assertIsNotNone(compressed)

            out_path = path + '.out.wav'
            ok = ah.create_wav_from_compressed(compressed, out_path)
            self.assertTrue(ok)
            self.assertTrue(os.path.isfile(out_path))
            # verify wave parameters
            with wave.open(out_path, 'rb') as wf:
                self.assertEqual(wf.getframerate(), 11025)
        finally:
            try: os.remove(path)
            except Exception: pass
            try: os.remove(path + '.out.wav')
            except Exception: pass
