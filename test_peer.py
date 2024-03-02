import unittest
from deccom.peers.peer import byte_reader

class test_byte_reader(unittest.TestCase):
    def setUp(self):
        self.data = b'\x00\x00\x00\x05hello\x00\x00\x00\x06world'
        self.reader = byte_reader(self.data)

    def test_read_next_variable(self):
        self.assertEqual(self.reader.read_next_variable(4), b'hello')

    def test_read_next_variable_out_of_bounds(self):
        with self.assertRaises(IndexError):
            self.assertEqual(self.reader.read_next_variable(4), b'hello')

            # world is 4 letters, but marked as 5, so it will trigger an error.
            self.assertEqual(self.reader.read_next_variable(4), b'world')

    def test_read_next(self):
        self.assertEqual(self.reader.read_next(5), b'\x00\x00\x00\x05h')
        self.assertEqual(self.reader.read_next(6), b'ello\x00\x00')

    def test_read_next_out_of_bounds(self):
        with self.assertRaises(IndexError):
            self.reader.read_next(100)

if __name__ == '__main__':
    unittest.main()
