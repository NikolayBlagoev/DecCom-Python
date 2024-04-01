import asyncio
import time
import unittest
from deccom.peers.peer import byte_reader
from deccom.peers.peer import Peer
from deccom.protocols.peerdiscovery.kademliadiscovery import KademliaDiscovery
from stubs.network_stub import NetworkStub
from stubs.node_stub import NodeStub

class test_protocol_kademlia(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        NetworkStub.connections = {}
        self.p1 = Peer(None, pub_key=str(0))
        self.loop = asyncio.new_event_loop()
        pl = NetworkStub()
        kl = KademliaDiscovery()
        kl.set_lower(pl)
        self.n1 = NodeStub(self.p1, kl)
        self.loop.run_until_complete(self.n1.listen())
        
    
    def test_kademlia_should_find(self):

        self.assertTrue(isinstance(self.p1.id_node, bytes))

        p2 = Peer(None)
        pl = NetworkStub()
        
        k2 = KademliaDiscovery([self.p1])
        k2.set_lower(pl)
        n2 = NodeStub(p2, k2)
        self.loop.run_until_complete(n2.listen())
        
        self.loop.run_until_complete(k2.find_peer(bytes(self.p1.id_node)))
        self.assertEqual(self.p1.id_node, k2.get_peer(bytes(self.p1.id_node)).id_node)

    def test_kademlia_should_find2(self):
        
        prlist = []
        kls = []
        for _ in range(10):
            

            p2 = Peer(None)
            prlist.append(p2)
            pl = NetworkStub()
            k2 = KademliaDiscovery([self.p1])
            k2.set_lower(pl)
            kls.append(k2)
            n2 = NodeStub(p2, k2)
            self.loop.run_until_complete(n2.listen())
        for k in kls:
            for p in prlist:
                if p.id_node == k.peer.id_node:
                    continue
                print("lookibg")
                self.loop.run_until_complete(k.find_peer(bytes(p.id_node)))
                self.assertEqual(p.id_node, k.get_peer(bytes(p.id_node)).id_node)
    def doCleanups(self) -> None:
        self.n1.set_listen(False)
        return super().doCleanups()
    async def test_ensure_not_central(self):
        self.n1.set_listen(True)
        prlist = []
        kls = []
        for i in range(1,6):
            

            p2 = Peer(None, pub_key=str(i))
            prlist.append(p2)
            pl = NetworkStub()
            k2 = KademliaDiscovery([self.p1], interval=2)
            k2.set_lower(pl)
            kls.append(k2)
            n2 = NodeStub(p2, k2)
            await n2.listen()
        await asyncio.sleep(3)
        self.n1.set_listen(False)
        for k in kls:
            for p in prlist:
                if p.id_node == k.peer.id_node:
                    continue
                # print("do we know?", p.pub_key)
                await k.find_peer(bytes(p.id_node)) 
                self.assertEqual(p.id_node, k.get_peer(bytes(p.id_node)).id_node)
        self.n1.set_listen(True)

class test_protocol_kademlia_2(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.p1 = Peer(None, pub_key="0")
        self.loop = asyncio.new_event_loop()
        NetworkStub.connections = {}
        pl = NetworkStub()
        kl = KademliaDiscovery()
        kl.set_lower(pl)
        self.n1 = NodeStub(self.p1, kl)
        self.loop.run_until_complete(self.n1.listen())
    async def test_small_bucket(self):
        
        prlist = []
        kls = []
        
            

        p1= Peer(None,  pub_key="10")
        prlist.append(p1)
        pl = NetworkStub()
        k1 = KademliaDiscovery([self.p1], interval=3, k = 1)
        k1.set_lower(pl)
        kls.append(k1)
        n3 = NodeStub(p1, k1)
        await n3.listen()
        print(p1.addr)
        p2 = Peer(None, pub_key="00")
        prlist.append(p2)
        pl = NetworkStub()
        k2 = KademliaDiscovery([self.p1], interval=3)
        k2.set_lower(pl)
        kls.append(k2)
        n2 = NodeStub(p2, k2)
        await n2.listen()
        print(p2.addr)
        await asyncio.sleep(5)
        print("loooking for p1",p1.pub_key)
        await k2.find_peer(p1.id_node)
        self.assertEqual(p1.id_node, k2.get_peer(bytes(p1.id_node)).id_node)
        

        p3 = Peer(None,  pub_key="1")
        prlist.append(p3)
        pl = NetworkStub()
        k3 = KademliaDiscovery([self.p1], interval=3)
        k3.set_lower(pl)
        kls.append(k3)
        n2 = NodeStub(p3, k3)
        print("starting n2...")
        await n2.listen()
        await asyncio.sleep(5)
        print("looking for p3...")
        await k1.find_peer(p3.id_node)
        
        self.assertEqual(p3.id_node, k1.get_peer(bytes(p3.id_node)).id_node)

        await k3.find_peer(bytes(p2.id_node))
        
        self.assertEqual(p2.id_node, k3.get_peer(bytes(p2.id_node)).id_node)

        
        
        
        # self.n1.set_listen(False)
        # print("lookin...")
        # await asyncio.sleep(5)
        # print("digging in...", p2.id_node)
        # await k1.find_peer(bytes(p2.id_node))
        
#         self.assertEqual(p2.id_node, k1.get_peer(bytes(p2.id_node)).id_node)
#         self.n1.set_listen(True)
#         # self.loop.run_until_complete(asyncio.sleep(3))
#         # n3.set_listen(False)
#         # for k in kls:
#         #     for p in prlist:
#         #         # print("do we know?")
#         #         self.loop.run_until_complete(k.find_peer(bytes(p.id_node)))
#         #         self.assertEqual(p.id_node, k.get_peer(bytes(p.id_node)).id_node)
#         # n3.set_listen(True)


if __name__ == '__main__':
    unittest.main()
