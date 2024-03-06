import asyncio
from typing import Callable
from deccom.protocols.abstractprotocol import AbstractProtocol
from deccom.protocols.defaultprotocol import DefaultProtocol
from deccom.peers import Peer
from random import randint, sample
from deccom.protocols.wrappers import *
from deccom.protocols.peerdiscovery.abstractpeerdiscovery import AbstractPeerDiscovery


class GossipDiscovery(AbstractPeerDiscovery):
    INTRODUCTION = int.from_bytes(b'\xe1', byteorder="big") # english opening king's variation
    PUSH = int.from_bytes(b'\xc4', byteorder="big")
    PULL = int.from_bytes(b'\xe5', byteorder="big")
    PULLED = int.from_bytes(b'\xc3', byteorder="big")
    FIND = int.from_bytes(b'\xf6', byteorder="big")
    ASK_FOR_ID = int.from_bytes(b'\xf3',byteorder="big")
    offers = dict(AbstractPeerDiscovery.offers, **{
        "send_ping": "send_ping"
    })
    bindings = dict(AbstractPeerDiscovery.bindings, **{
                    "_lower_ping": "send_ping"
                    })
    required_lower = AbstractPeerDiscovery.required_lower + ["send_ping"]

    def __init__(self, bootstrap_peers: list[Peer] = [], interval: int = 10, submodule=None, callback: Callable[[tuple[str, int], bytes], None] = None, disconnected_callback=..., connected_callback: Callable[[Peer], None] = ...):
        super().__init__(bootstrap_peers, interval, submodule, callback, disconnected_callback, connected_callback)
        self.peer_crawls = dict()
        self.sent_finds = dict()
        
    
    async def start(self, p: Peer):
        await super().start(p)
        for p in self.bootstrap_peers:
            await self.introduce_to_peer(p)
            msg = bytearray([GossipDiscovery.ASK_FOR_ID])
            await self._lower_sendto(msg,p.addr)
        self.push_or_pull()

    def push_or_pull(self):
        loop = asyncio.get_event_loop()
        loop.create_task(self._push_or_pull())

    async def _push_or_pull(self):
        # print("push or pull")
        rand = randint(0, 1)
        # print(rand)
        ids = list(self.peers.keys())
        
        if len(ids) >= 1:
            strt = randint(0, len(ids)-1)
            for i in range(strt, strt+5):
                if i >= len(ids):
                    break
                await self._lower_ping(self.peers[ids[i]].addr, lambda addr : None, lambda addr, node_id=ids[i], self=self: self.remove_peer(addr, node_id), self.interval)
        else:
            for p in self.bootstrap_peers:
                await self.introduce_to_peer(p)
                msg = bytearray([GossipDiscovery.ASK_FOR_ID])
                loop = asyncio.get_running_loop()
                loop.create_task(self._lower_sendto(msg,p.addr))
                
        if rand == 0 and len(ids) >= 2:

            p1 = ids[randint(0, len(ids)-1)]
            p2 = p1

            while p1 == p2:
                p2 = ids[randint(0, len(ids)-1)]
            msg = bytearray([GossipDiscovery.PUSH])
            msg = msg + bytes(self.peers[p2])
            await self._lower_sendto(msg, self.peers[p1].addr)

            msg = bytearray([GossipDiscovery.PUSH])
            msg = msg + bytes(self.peers[p1])
            await self._lower_sendto(msg, self.peers[p2].addr)
        elif len(ids) >= 1:

            p1 = ids[randint(0, len(ids)-1)]
            msg = bytearray([GossipDiscovery.PULL])
            msg = msg + bytes(self.peer)
            await self._lower_sendto(msg, self.peers[p1].addr)
        loop = asyncio.get_running_loop()
        self.refresh_loop = loop.call_later(self.interval+2, self.push_or_pull)
    def remove_peer(self, addr: tuple[str, int], node_id: bytes):
        if self.peers.get(node_id) != None:
            del self.peers[node_id]
        return super().remove_peer(addr, node_id)
    
    async def introduce_to_peer(self, peer: Peer):
        # print("introducing to", peer.id_node)
        msg = bytearray([GossipDiscovery.INTRODUCTION])
        msg = msg + bytes(self.peer)
        await self._lower_sendto(msg, peer.addr)

    async def sendto(self, msg, addr):
        tmp = bytearray([1])
        tmp = tmp + msg
        return await self._lower_sendto(tmp, addr)

    def process_datagram(self, addr: tuple[str, int], data: bytes):
        print("processing?")
        if data[0] == GossipDiscovery.INTRODUCTION:

            other, i = Peer.from_bytes(data[1:])
            print("introduction form", other.pub_key)
            other.addr = addr
            
            
            self.connection_approval(addr,other,self.add_peer,self.ban_peer)

        elif data[0] == GossipDiscovery.PULL:
            
            flag = False
            other, i = Peer.from_bytes(data[1:])
            
            
            
            ids = list(self.peers.keys())
            if len(ids) > 1:
                rand_node = randint(0, len(ids)-1)
                while ids[rand_node] == other.id_node:
                    rand_node = randint(0, len(ids)-1)
                msg = bytearray([GossipDiscovery.PULLED])
                msg = msg + bytes(self.peers[ids[rand_node]])
                loop = asyncio.get_running_loop()
                loop.create_task(self._lower_sendto(msg, addr))
            
            self.connection_approval(addr,other,self.add_peer,self.ban_peer)
        elif data[0] == GossipDiscovery.PULLED:
            # print("pulled")
            other, i = Peer.from_bytes(data[1:])
            # print("pulled a", other.pub_key)
            
            self.connection_approval(addr,other,self.add_peer,self.ban_peer)
            loop = asyncio.get_running_loop()
            loop.create_task(self.introduce_to_peer(other))

        elif data[0] == GossipDiscovery.PUSH:
            # print("request to push")
            other, i = Peer.from_bytes(data[1:])
            
            # self.peers[other.id_node] = other
            self.connection_approval(other.addr,other,self.add_peer,self.ban_peer)
        elif data[0] == GossipDiscovery.FIND:
            # print("peer looking")
            if self.sent_finds.get(data) != None:
                return

            seeker, i = Peer.from_bytes(data[1:])

            id = data[i+1:]
            # print(seeker.id_node," is looking for ",id)
            self.sent_finds[data] = i
            if id == self.peer.id_node:
                # print("THATS ME")
                loop = asyncio.get_running_loop()
                loop.create_task(self.introduce_to_peer(seeker))

                
                self.connection_approval(addr,seeker,self.add_peer,self.ban_peer)
            elif self.peers.get(id) == None:
                l = list(self.get_peers())
                for p in l:
                    if self.get_peers().get(p) is None:
                        continue
                    loop = asyncio.get_running_loop()
                    loop.create_task(self._lower_sendto(
                        data, self.peers[p].addr))

            else:
                peer = self.peers.get(id)
                loop = asyncio.get_running_loop()
                loop.create_task(self._lower_sendto(data, peer.addr))
        elif data[0] == GossipDiscovery.ASK_FOR_ID:
            print("ASKING FOR ID")
            msg = bytearray([GossipDiscovery.INTRODUCTION])
            msg = msg + bytes(self.peer)
            loop = asyncio.get_running_loop()
            loop.create_task(self._lower_sendto(msg, addr))
            
        else:
            self.callback(addr, data[1:])
        return

    

    async def send_ping(self, addr, success, fail, timeout):
        await self._lower_ping(addr, success, fail, timeout)

    def add_peer(self, addr: tuple[str,int], p: Peer):
        if self.peer_crawls.get(p.id_node) != None:
            self.peer_crawls[p.id_node].set_result("success")
            del self.peer_crawls[p.id_node]
        self.peers[p.id_node] = p
        print("added peer")
        super().add_peer(addr, p)
    
    async def _find_peer(self, fut, id):
        self.peer_crawls[id] = fut
        msg = bytearray([GossipDiscovery.FIND])
        if isinstance(id, str):
            id = id.encode("utf-8")
        msg = msg + bytes(self.peer) + id
        l = list(self.get_peers())
        for p in l:
            if self.get_peers().get(p) is None:
                continue
            await self._lower_sendto(msg, self.peers[p].addr)

        return

    async def find_peer(self, id) -> Peer:
        if self.peers.get(id) == None:
            if self.peer_crawls.get(id) == None:
                loop = asyncio.get_running_loop()
                fut = loop.create_future()
                await self._find_peer(fut, id)
                await fut
            else:
                await self.peer_crawls.get(id)
        return self.get_peer(id)
    @bindto("send_ping")
    async def _lower_ping(self, addr, success, failure, timeout):
        return