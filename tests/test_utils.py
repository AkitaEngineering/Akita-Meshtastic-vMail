import unittest

from akita_vmail.utils import _recursive_update


class TestUtils(unittest.TestCase):
    def test_recursive_update_merges_nested(self):
        base = {'a': 1, 'b': {'x': 1, 'y': 2}}
        update = {'b': {'y': 3, 'z': 4}, 'c': 5}
        expected = {'a': 1, 'b': {'x': 1, 'y': 3, 'z': 4}, 'c': 5}
        _recursive_update(base, update)
        self.assertEqual(base, expected)


if __name__ == '__main__':
    unittest.main()
