import unittest
import akita_vmail.protocol as protocol


class TestProtocolRefresh(unittest.TestCase):
    def test_getters_use_config(self):
        custom = {"meshtastic_port_num": 999, "chunking": {"sizes": {"X": 50}, "default_key": "X"}}
        port = protocol.get_private_app_port(custom)
        self.assertEqual(port, 999)


if __name__ == '__main__':
    unittest.main()
