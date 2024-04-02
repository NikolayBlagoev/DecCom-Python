import asyncio
import time
import unittest
from deccom.peers.peer import byte_reader
from deccom.peers.peer import Peer
from deccom.protocols.holepuncher import HolePuncher
from deccom.protocols.peerdiscovery.kademliadiscovery import KademliaDiscovery
from stubs.node_stub import NodeStub
from stubs.nat_stub import NatStub

class test_nat(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        NatStub.connections = {}
        self.p1 = Peer(None, pub_key=str(0))
        self.loop = asyncio.new_event_loop()
        pl = NatStub()
        pnchr = HolePuncher()
        pnchr.set_lower(pl)
        kl = KademliaDiscovery()
        kl.set_lower(pnchr)
        self.n1 = NodeStub(self.p1, kl, port = 10)
        self.loop.run_until_complete(self.n1.listen())
        print(self.p1.addr)
    async def test_generic(self):
        # loop = asyncio.get_event_loop()
        prlist = []
        kls: list[KademliaDiscovery] = []
        for i in range(10):
            p = Peer(None, pub_key=str(i+1))
            prlist.append(p)
            pl = NatStub()
            
            pnchr = HolePuncher()
            pnchr.set_lower(pl)
            kl = KademliaDiscovery()
            kl.max_warmup = -1

            kls.append(kl)
            kl.bootstrap_peers.append(self.p1)
            kl.set_lower(pnchr)
            nl = NodeStub(p, kl, ip_addr=f"0.0.0.{i + 1}", port=i*2 + 1)
            await nl.listen()
            print(p.addr)
        loop = asyncio.get_event_loop()
        await asyncio.sleep(3)
        for k in kls:
            if k.peer.id_node == prlist[0].id_node:
                continue
            print("need to look for")
            loop.create_task(k.find_peer(prlist[0].id_node))
        await asyncio.sleep(6)
        for k in kls:
            if k.peer.id_node == prlist[0].id_node:
                continue
                print("lookibg")
                # self.loop.run_until_complete(k.find_peer(bytes(p.id_node)))
                # self.assertIsNone(k.get_peer(p.id_node))
            p = prlist[0]
            self.assertEqual(p.id_node, k.get_peer(bytes(p.id_node)).id_node)
        
class test_nat_no_punching(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        NatStub.connections = {}
        self.p1 = Peer(None, pub_key=str(0))
        self.loop = asyncio.new_event_loop()
        pl = NatStub()
        # pnchr = HolePuncher()
        # pnchr.set_lower(pl)
        kl = KademliaDiscovery()
        kl.set_lower(pl)
        self.n1 = NodeStub(self.p1, kl, port = 10)
        self.loop.run_until_complete(self.n1.listen())
        print(self.p1.addr)
    async def test_generic(self):
        # loop = asyncio.get_event_loop()
        prlist = []
        kls:list[KademliaDiscovery] = []
        for i in range(10):
            p = Peer(None, pub_key=str(i+1))
            prlist.append(p)
            pl = NatStub()
            # pnchr = HolePuncher()
            # pnchr.set_lower(pl)
            kl = KademliaDiscovery(interval=5)
            kl.max_warmup = -1
            kls.append(kl)
            kl.bootstrap_peers.append(self.p1)
            kl.set_lower(pl)
            nl = NodeStub(p, kl, ip_addr=f"0.0.0.{i + 1}", port=i*2 + 1)
            await nl.listen()
            print(p.addr)
        loop = asyncio.get_event_loop()
        for k in kls:
            if k.peer.id_node == prlist[0].id_node:
                continue
            loop.create_task(kls[-1].find_peer(prlist[0].id_node))
        await asyncio.sleep(15)
        for k in kls:
            for p in prlist:
                if p.id_node == k.peer.id_node:
                    continue
                print("lookibg")
                # self.loop.run_until_complete(k.find_peer(bytes(p.id_node)))
                self.assertIsNone(k.get_peer(p.id_node))

        

if __name__ == '__main__':
    unittest.main()
