import sys
import types
import importlib
from unittest import TestCase
from unittest.mock import MagicMock, patch

# Prepare fake meshtastic submodules before importing handler
meshtastic = types.ModuleType('meshtastic')
meshtastic.MeshtasticError = Exception
serial_interface = types.ModuleType('meshtastic.serial_interface')
class DummySerialInterface:
    def __init__(self, devPath=None, debugOut=None):
        self.myInfo = None
        self.nodes = {}
    def close(self):
        pass
serial_interface.SerialInterface = DummySerialInterface
tcp_interface = types.ModuleType('meshtastic.tcp_interface')
class DummyTCPInterface:
    def __init__(self, hostname=None):
        self.myInfo = None
        self.nodes = {}
    def close(self):
        pass
tcp_interface.TCPInterface = DummyTCPInterface
util = types.ModuleType('meshtastic.util')
def our_hw_model_name(x):
    return str(x)
util.our_hw_model_name = our_hw_model_name

sys.modules['meshtastic'] = meshtastic
sys.modules['meshtastic.serial_interface'] = serial_interface
sys.modules['meshtastic.tcp_interface'] = tcp_interface
sys.modules['meshtastic.util'] = util

# Provide a minimal `protocol` module so meshtastic_handler can import names
protocol = types.ModuleType('protocol')
protocol.BROADCAST_ADDR = '^all'
protocol.MSG_TYPE_VOICE_CHUNK = 'voice_chunk'
protocol.MSG_TYPE_ACK = 'ack'
protocol.MSG_TYPE_TEST = 'test'
protocol.MSG_TYPE_COMPLETE_VOICE = 'complete_voice'
def dummy_create_chunk_payload(cid, num, total, data):
    return b'chunk' + data
def dummy_create_ack_payload(cid, num):
    return b'ack'
def dummy_create_test_payload(msg):
    return msg.encode('utf-8')
def dummy_create_complete_voice_payload(data, ts):
    return b'complete' + data
def dummy_parse_payload(b):
    return {'ok': True}
def dummy_verify_chunk_crc(p):
    return True, b'd'
def dummy_verify_complete_voice_crc(p):
    return True, b'd'
def dummy_split_data_into_chunks(data, size):
    return [data]
def dummy_generate_unique_id():
    return 'id'
def dummy_get_private_app_port(cfg=None):
    if isinstance(cfg, dict):
        return cfg.get('meshtastic_port_num', 256)
    return 256
def dummy_get_chunk_retry_count(cfg=None):
    return 2
def dummy_get_chunk_retry_delay(cfg=None):
    return 0.1

protocol.create_chunk_payload = dummy_create_chunk_payload
protocol.create_ack_payload = dummy_create_ack_payload
protocol.create_test_payload = dummy_create_test_payload
protocol.create_complete_voice_payload = dummy_create_complete_voice_payload
protocol.parse_payload = dummy_parse_payload
protocol.verify_chunk_crc = dummy_verify_chunk_crc
protocol.verify_complete_voice_crc = dummy_verify_complete_voice_crc
protocol.split_data_into_chunks = dummy_split_data_into_chunks
protocol.generate_unique_id = dummy_generate_unique_id
protocol.get_private_app_port = dummy_get_private_app_port
protocol.get_chunk_retry_count = dummy_get_chunk_retry_count
protocol.get_chunk_retry_delay = dummy_get_chunk_retry_delay
protocol.MSG_TYPE_VOICE_CHUNK = protocol.MSG_TYPE_VOICE_CHUNK
protocol.MSG_TYPE_ACK = protocol.MSG_TYPE_ACK
protocol.MSG_TYPE_TEST = protocol.MSG_TYPE_TEST
protocol.MSG_TYPE_COMPLETE_VOICE = protocol.MSG_TYPE_COMPLETE_VOICE
protocol.BROADCAST_ADDR = protocol.BROADCAST_ADDR

sys.modules['protocol'] = protocol

# Now import the handler module
mh = importlib.import_module('akita_vmail.meshtastic_handler')

class TestMeshtasticHandler(TestCase):
    def setUp(self):
        self.logged = []
        self.log_q = MagicMock()
        self.recv_cb = lambda t, d, f, p: None

    def test_send_data_calls_interface_when_connected(self):
        cfg = {'meshtastic_port_num': 999}
        handler = mh.MeshtasticHandler(self.log_q, self.recv_cb, config=cfg)
        # attach a fake interface with sendData
        sent = {}
        class FakeInterface:
            def sendData(self, payload, destinationId=None, portNum=None, wantAck=False, channelIndex=None):
                sent['payload'] = payload
                sent['portNum'] = portNum
        handler.interface = FakeInterface()
        handler.is_connected = True
        ok = handler.send_data(b'abc', description='unit-test')
        self.assertTrue(ok)
        self.assertEqual(sent.get('portNum'), 999)

    def test_get_available_ports_handles_exception(self):
        handler = mh.MeshtasticHandler(self.log_q, self.recv_cb, config={})
        # patch the serial.tools.list_ports.comports to raise
        with patch('akita_vmail.meshtastic_handler.serial.tools.list_ports.comports', side_effect=Exception('boom')):
            ports = handler.get_available_ports()
            self.assertEqual(ports, [])
