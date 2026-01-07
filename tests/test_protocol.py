import unittest

from akita_vmail.protocol import split_data_into_chunks, DEFAULT_CONFIG


class TestProtocol(unittest.TestCase):
    def test_split_and_reassemble(self):
        data = b'A' * 1000
        # Choose a payload size that triggers chunking
        max_payload = 500
        chunks = split_data_into_chunks(data, max_payload)
        self.assertTrue(len(chunks) > 0)
        # Reassemble should equal original
        reassembled = b''.join(chunks)
        self.assertEqual(reassembled, data)


if __name__ == '__main__':
    unittest.main()
