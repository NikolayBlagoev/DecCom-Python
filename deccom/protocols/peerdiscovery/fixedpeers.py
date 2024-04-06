import asyncio
from typing import Callable, Union
from deccom.protocols.abstractprotocol import AbstractProtocol
from deccom.protocols.defaultprotocol import DefaultProtocol
from deccom.peers import Peer
from random import randint, sample

from deccom.protocols.peerdiscovery.abstractpeerdiscovery import AbstractPeerDiscovery


class FixedPeers(AbstractPeerDiscovery):
    EXIT = int.from_bytes(b'\x02', byteorder="big")
    offers = dict(AbstractPeerDiscovery.offers, **{
        "sendto_id": "sendto_id",
        "broadcast": "broadcast",
        "get_al": "get_al"
    })
    def __init__(self, peer_list: list[Peer], bootstrap_peers: list[Peer] = [], interval: int = 10, submodule=None, callback: Callable[[tuple[str, int], bytes], None] = None, disconnected_callback= lambda *args: ..., connected_callback: Callable[[Peer], None] = lambda *args: ...):
        super().__init__(bootstrap_peers, interval, submodule, callback, disconnected_callback, connected_callback)
        self.p_to_a: dict[bytes,tuple[str,int]] = dict()
        self.a_to_p: dict[tuple[str,int],Peer] = dict()
        self.peer_crawls = dict()
        self.sent_finds = dict()
        for p in peer_list:
            self.p_to_a[p.id_node] = p.addr
            self.a_to_p[p.addr] = p
            self.peers[p.id_node] = p
        self.introduced = []
    async def start(self, p: Peer):
        await super().start(p)
        loop = asyncio.get_running_loop()
        loop.call_later(2, self.introduce_to_others)
        
    def introduce_to_others(self):
        loop = asyncio.get_running_loop()
        for a in self.a_to_p:
            # self.introduced.append(a)
            loop.create_task(self.introduction(a))
    async def introduction(self, addr):
        msg = bytearray([1])
        # print("introducing to ",addr)
        await self.send_datagram(msg, addr)
    def process_datagram(self, addr: tuple[str, int], data: bytes):
        
        if self.a_to_p.get(addr) == None:
            return
        if not addr in self.introduced:
            # print("new peer MET!",addr)
            self.introduced.append(addr)
            
            if self.peer_crawls.get(self.a_to_p.get(addr)) != None:
                self.peer_crawls.get(self.a_to_p.get(addr)).set_result(True)
            else:
                self.connected_callback(self.a_to_p[addr])
        if data[0] == FixedPeers.EXIT:
            
            p = self.a_to_p[addr]
            print("\n\n\n\nsomeone is gone?", p.pub_key)
            del self.a_to_p[addr]
            self.remove_peer(addr, p.id_node)
    async def sendto(self, msg, addr):
        if self.a_to_p.get(addr) == None:
            print("dont know this peer?")

            return
        
        await super().sendto(msg, addr)
    async def stop_receiving(self):
        self.a_to_p = dict()
    async def sendto_id(self, msg, p: bytes):
        if self.p_to_a.get(p) == None:
            return
        if msg[0] == FixedPeers.EXIT:
            print("sending exit to ", self.peers[p].pub_key)
        await super().sendto(msg, self.p_to_a[p])
    async def broadcast(self, msg):
        for addr, p in self.a_to_p.items():
            await self.sendto(msg,addr)
    def get_al(self, addr: tuple[str, int]) -> Union[Peer, None]:
        return self.a_to_p.get(addr)
    async def find_peer(self, id: bytes) -> Peer:
        if self.peers.get(id) == None:
            if self.peer_crawls.get(id) == None:
                loop = asyncio.get_running_loop()
                fut = loop.create_future()
                self.peer_crawls[id] = fut
                
                await fut
            else:
                await self.peer_crawls.get(id)
        return self.get_peer(id)
        