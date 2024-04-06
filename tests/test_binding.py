
import unittest
from deccom.protocols.securityprotocols import Noise
from deccom.protocols.streamprotocol import StreamProtocol
from deccom.protocols.peerdiscovery import KademliaDiscovery, GossipDiscovery
from deccom.protocols.defaultprotocol import DefaultProtocol
class test_bindings(unittest.TestCase):
    


    def test_binding_1(self):
        
        lowest = DefaultProtocol()
        
        disc = KademliaDiscovery()
        
        disc.set_lower(lowest)
        
        noise = Noise()
        
        noise.set_lower(disc)
        stream = StreamProtocol(False)
        stream.set_lower(noise)
        self.assertEqual(stream._lower_sendto, noise.sendto)
        self.assertEqual(disc._lower_ping, lowest.send_ping)
        self.assertEqual(disc.connected_callback, stream.peer_connected)
        self.assertEqual(disc.disconnected_callback, stream.remove_peer)
        self.assertEqual(lowest.callback, disc.datagram_received)
        self.assertEqual(disc.callback, noise.datagram_received)
        self.assertEqual(noise.callback, stream.datagram_received)
        self.assertEqual(noise.approve_peer, disc.connection_approval)
    def test_binding_2(self):
        
        lowest = DefaultProtocol()
        
        disc = GossipDiscovery()
        
        disc.set_lower(lowest)
        
        noise = Noise()
        
        noise.set_lower(disc)
        stream = StreamProtocol(False)
        stream.set_lower(noise)
        self.assertEqual(stream._lower_sendto, noise.sendto)
        self.assertEqual(disc._lower_ping, lowest.send_ping)
        self.assertEqual(disc.connected_callback, stream.peer_connected)
        self.assertEqual(disc.disconnected_callback, stream.remove_peer)
        self.assertEqual(lowest.callback, disc.datagram_received)
        self.assertEqual(disc.callback, noise.datagram_received)
        self.assertEqual(noise.callback, stream.datagram_received)
        self.assertEqual(noise.approve_peer, disc.connection_approval)
    def test_bad_binding(self):
        
        lowest = DefaultProtocol()
        
        disc = KademliaDiscovery()
        
        disc.set_lower(lowest)
        
        noise = Noise()
        try:
            noise.set_lower(lowest)
            self.assertEqual(1,2)
        except:
            self.assertEqual(1,1)
        
        


   

if __name__ == '__main__':
    unittest.main()
