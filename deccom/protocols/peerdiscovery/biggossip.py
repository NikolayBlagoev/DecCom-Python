import asyncio
import random
from typing import Callable, Union
from deccom.peers.peer import Peer
from deccom.protocols.peerdiscovery.abstractpeerdiscovery import AbstractPeerDiscovery
from deccom.protocols.wrappers import *

class BigGossip(AbstractPeerDiscovery):
    INTRODUCTION = int.from_bytes(b'\xe1', byteorder="big") # english opening king's variation
    RESPOND_FIND = int.from_bytes(b'\xc4', byteorder="big")
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
    def __init__(self, bootstrap_peers: list[Peer] = [], interval: int = 60, k: int = 20, submodule=None, callback: Callable[[tuple[str, int], bytes], None] = None, disconnected_callback=lambda *args:..., connected_callback: Callable[[Peer], None] =lambda *args:...):
        super().__init__(bootstrap_peers, interval, submodule, callback, disconnected_callback, connected_callback)
        self.k = k
        self.peer_crawls = dict()
        self.sent_finds = dict()
        self.warmup = 0
        self.max_warmup = 60
        self.searches: dict[bytes,bytes] = dict()
        
    async def start(self, p: Peer):
        await super().start(p)
        
        for p in self.bootstrap_peers:
            await self.introduce_to_peer(p)
            msg = bytearray([BigGossip.ASK_FOR_ID])
            await self.send_datagram(msg,p.addr)
        loop = asyncio.get_event_loop()
        loop.call_later(2, self.refresh_table)
    
    def refresh_table(self):
        
        loop = asyncio.get_event_loop()

        loop.create_task(self._refresh_table())

    async def _refresh_table(self):
        # print("refreshing")
        loop = asyncio.get_running_loop()
        if len(self.peers.items()) == 0:
            print("i dont know anyone still")
            for p in self.bootstrap_peers:
                await self.introduce_to_peer(p)
                await asyncio.sleep(1)
                msg = bytearray([BigGossip.ASK_FOR_ID])
                await self.send_datagram(msg,p.addr)
            self.refresh_loop = loop.call_later(2, self.refresh_table)
            return
        

        prs = list(self.peers.items())
        if len(prs) > 0:
            prs = random.sample(prs,min(len(prs),2))
            for k,v in prs:
                msg = bytearray([BigGossip.PULL])
                await self.send_datagram(msg,v.addr)
        self.refresh_loop = loop.call_later(self.interval, self.refresh_table)
    
    def remove_peer(self, addr: tuple[str, int], node_id: bytes):
        if  self.peers.get(node_id) == None:
            return
        del self.peers[node_id]
        return super().remove_peer(addr, node_id)
    
    async def introduce_to_peer(self, peer: Peer):
        # print("introducing to", peer.id_node)
        msg = bytearray([BigGossip.INTRODUCTION])
        msg = msg + bytes(self.peer)
        await self.send_datagram(msg, peer.addr)

      
    def process_datagram(self, addr: tuple[str, int], data: bytes):
        # print("processing...")
        asyncio.set_event_loop(self.loop)
        if data[0] == BigGossip.INTRODUCTION:

            other, i = Peer.from_bytes(data[1:])
            # print(self.peer.pub_key,": introduction form", other.pub_key)
            other.addr = addr
            self.connection_approval(addr,other,self.add_peer,self.ban_peer)
            

        
        elif data[0] == BigGossip.PULL:
            prs = list(self.peers.items())
            if len(prs) > 0:
                prs = random.sample(prs,min(len(prs),self.k))
                i = 0
                while i < len(prs):
                    msg = bytearray([BigGossip.PULLED])
                    for k,v in prs[i:i+10]:
                        msg += bytes(v)
                    loop = asyncio.get_event_loop()
                    loop.create_task(self.send_datagram(msg, addr))
                    i += 10

        elif data[0] == BigGossip.PULLED:
            i = 1
            loop = asyncio.get_event_loop()
            while i < len(data):
                #print(i, len(data))
                other, k = Peer.from_bytes(data[i:])
                i+= k
                if other.id_node == self.peer.id_node:
                    continue
                if self.peers.get(other.id_node) == None:
                    loop.create_task(self.introduce_to_peer(other))
                    
                    msg = bytearray([BigGossip.ASK_FOR_ID])
                    loop.create_task(self.send_datagram(msg, other.addr))
                    
        
        elif data[0] == BigGossip.FIND:
            
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
                l = list(self.get_peers())[:10]
                for p in l:
                    if self.get_peers().get(p) is None:
                        continue
                    loop = asyncio.get_running_loop()
                    loop.create_task(self.send_datagram(
                        data, self.peers[p].addr))

            else:
                peer = self.peers.get(id)
                loop = asyncio.get_running_loop()
                loop.create_task(self.send_datagram(data, peer.addr))    
        elif data[0] == BigGossip.ASK_FOR_ID:
            # print("ASKING FOR ID")
            msg = bytearray([BigGossip.INTRODUCTION])
            # print("PUBKEY", self.peer)
            
            # pprint(vars(self.peer))

            msg = msg + bytes(self.peer)
            loop = asyncio.get_running_loop()
            loop.create_task(self.send_datagram(msg, addr))
            
        else:
            return self.callback(addr, data[1:])
        
    
    
    async def send_ping(self, addr, success, fail, timeout):
        await self._lower_ping(addr, success, fail, timeout)
    
    
        
    def add_peer(self, addr: tuple[str,int], p: Peer):
        # print(p)
        
        self.peers[p.id_node] = p

    
    

    async def _find_peer(self, fut, id: bytes):
        self.peer_crawls[id] = fut
        msg = bytearray([BigGossip.FIND])
        
        msg = msg + bytes(self.peer) + id
        l = list(self.get_peers())
        for p in l:
            if self.get_peers().get(p) is None:
                continue
            await self.send_datagram(msg, self.peers[p].addr)

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
        
    def get_peer(self, id) -> Union[Peer,None]:
        return self.peers.get(id)
    
    @bindto("send_ping")
    async def _lower_ping(self, addr, success, failure, timeout):
        return