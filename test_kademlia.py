import asyncio
import unittest
from deccom.protocols.peerdiscovery._kademlia_routing import BucketManager

class test_kademlia_routing(unittest.TestCase):
    def setUp(self):
        self.node = bytearray([int.from_bytes(b'\x00', byteorder="big") for _ in range(32)])
        
        
        self.bucket = BucketManager(bytes(self.node), 1, print, 256)


    def test_insertion(self):
        self.bucket = BucketManager(bytes(self.node), 1, print, 256)
        node1 = bytearray([int.from_bytes(b'\x00', byteorder="big") for _ in range(31)])
        node1 +=   b'\x01' 
        self.bucket.add_peer(bytes(node1), 1)
        node2 = bytearray([int.from_bytes(b'\x00', byteorder="big") for _ in range(31)])
        node2 += b'\x02' 
        self.bucket.add_peer(bytes(node2), 2)
        self.assertEqual(self.bucket.get_peer(bytes(node1)), 1)
        self.assertEqual(self.bucket.get_peer(bytes(node2)), 2)
        node3 = bytearray([int.from_bytes(b'\x00', byteorder="big") for _ in range(31)])
        node3 += b'\x03' 
        self.bucket.add_peer(bytes(node3), 3)
        
        self.assertEqual(self.bucket.get_peer(bytes(node3)), 3)

        node4 = bytearray([int.from_bytes(b'\xff', byteorder="big") for _ in range(32)])
        
        self.bucket.add_peer(bytes(node4), 4)
        self.assertEqual(self.bucket.get_peer(bytes(node4)), 4)
        node4 = int.from_bytes(bytes(node4),byteorder="big")
        nodes = int.from_bytes(bytes(self.node),byteorder="big")
        self.assertEqual(self.bucket._get_index(node4 ^ nodes), len(self.bucket.buckets) - 1)
        node5 = bytearray([int.from_bytes(b'\xff', byteorder="big") for _ in range(31)])
        node5 += b'\x00'
        self.bucket.add_peer(bytes(node5), 5)
        self.assertEqual(self.bucket.get_peer(bytes(node5)), None)
    
    def test_removal(self):
        self.bucket = BucketManager(bytes(self.node), 1, print, 256)
        node1 = bytearray([int.from_bytes(b'\x00', byteorder="big") for _ in range(31)])
        node1 +=   b'\x01' 
        self.bucket.add_peer(bytes(node1), 1)
        self.assertEqual(self.bucket.get_peer(bytes(node1)), 1)
        
        node4 = bytearray([int.from_bytes(b'\xff', byteorder="big") for _ in range(32)])
        
        self.bucket.add_peer(bytes(node4), 4)
        self.assertEqual(self.bucket.get_peer(bytes(node4)), 4)
        node5 = bytearray([int.from_bytes(b'\xff', byteorder="big") for _ in range(31)])
        node5 += b'\x00'
        self.bucket.add_peer(bytes(node5), 5)
        self.assertEqual(self.bucket.get_peer(bytes(node5)), None)
        self.bucket.remove_peer(bytes(node4))
        self.assertEqual(self.bucket.get_peer(bytes(node4)), None)
        self.assertEqual(self.bucket.get_peer(bytes(node5)), 5)
    
    def test_range(self):
        self.bucket = BucketManager(bytes(self.node), 1, print, 256)
        node4 = bytearray([int.from_bytes(b'\xff', byteorder="big") for _ in range(32)])
        node4 = int.from_bytes(bytes(node4),byteorder="big")
        self.assertEqual(self.bucket.buckets[0].max_dist/node4, 1) # easier to spot what's wrong

    def test_range2(self):
        self.bucket = BucketManager(bytes(self.node), 1, print, 264)
        node4 = bytearray([int.from_bytes(b'\xff', byteorder="big") for _ in range(33)])
        node4 = int.from_bytes(bytes(node4),byteorder="big")
        self.assertEqual(self.bucket.buckets[0].max_dist/node4, 1) # easier to spot what's wrong
    
    def test_xor(self):
        node4 = bytearray([int.from_bytes(b'\xff', byteorder="big") for _ in range(32)])
        node4 = int.from_bytes(bytes(node4),byteorder="big")
        nodes = int.from_bytes(bytes(self.node),byteorder="big")
        
        self.assertEqual((node4 ^ nodes)/node4, 1)
        


   

if __name__ == '__main__':
    unittest.main()
