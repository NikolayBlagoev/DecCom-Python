import unittest
from deccom.utils.common import byte_reader
from deccom.peers.peer import Peer

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

    def test_from_to_bytes_peer(self):
        peer = Peer(("127.0.0.1", 10015))
        peer2, i = Peer.from_bytes(bytes(peer))
        self.assertEqual(peer.id_node, peer2.id_node)
        self.assertEqual(peer.pub_key, peer2.pub_key)
        self.assertEqual(peer.addr, peer2.addr)
        self.assertEqual(peer.tcp, peer2.tcp)
    
    def test_from_to_bytes_peer_with_string(self):
        peer = Peer(("127.0.0.1", 10015), pub_key="hello")
        peer2, i = Peer.from_bytes(bytes(peer))
        self.assertEqual(peer.id_node, peer2.id_node)
        self.assertEqual(peer.pub_key, peer2.pub_key)
        self.assertEqual(peer.addr, peer2.addr)
        self.assertEqual(peer.tcp, peer2.tcp)


    def test_from_to_bytes_peer_with_tcp(self):
        peer = Peer(("127.0.0.1", 10015),tcp=42)
        peer2, i = Peer.from_bytes(bytes(peer))
        self.assertEqual(peer.id_node, peer2.id_node)
        self.assertEqual(peer.pub_key, peer2.pub_key)
        self.assertEqual(peer.addr, peer2.addr)
        self.assertEqual(peer.tcp, peer2.tcp)

    def test_from_to_bytes_multiple_peers(self):
        peer_l = []
        msg = bytearray()
        for i in range(10):
            peer = Peer((f"{i*4}.{i*5}.2.5", i*10),tcp=i, pub_key=str(i))
            peer_l.append(peer)
            msg += bytes(peer)
        result = bytes(msg)
        i = 0
        k = 0
        while i < len(result):

            peer2, offs = Peer.from_bytes(result[i:])
            self.assertEqual(peer_l[k].id_node, peer2.id_node)
            self.assertEqual(peer_l[k].pub_key, peer2.pub_key)
            self.assertEqual(peer_l[k].addr, peer2.addr)
            self.assertEqual(peer_l[k].tcp, peer2.tcp)
            k += 1
            i += offs


if __name__ == '__main__':
    unittest.main()
