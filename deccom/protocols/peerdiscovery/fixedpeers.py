import asyncio
from typing import Callable, Union
from deccom.protocols.abstractprotocol import AbstractProtocol
from deccom.protocols.defaultprotocol import DefaultProtocol
from deccom.peers import Peer
from random import randint, sample

from deccom.protocols.peerdiscovery.abstractpeerdiscovery import AbstractPeerDiscovery


class FixedPeers(AbstractPeerDiscovery):
    offers = dict(AbstractPeerDiscovery.offers, **{
        "sendto_id": "sendto_id",
        "broadcast": "broadcast",
        "get_al": "get_al"
    })
    def __init__(self, peer_list: list[Peer], bootstrap_peers: list[Peer] = [], interval: int = 10, submodule=None, callback: Callable[[tuple[str, int], bytes], None] = None, disconnected_callback=..., connected_callback: Callable[[Peer], None] = ...):
        super().__init__(bootstrap_peers, interval, submodule, callback, disconnected_callback, connected_callback)
        self.p_to_a: dict[bytes,tuple[str,int]] = dict()
        self.a_to_p: dict[tuple[str,int],Peer] = dict()
        for p in peer_list:
            self.p_to_a[p.id_node] = p.addr
            self.a_to_p[p.addr] = p
            self.peers[p.id_node] = p
    
    def process_datagram(self, addr: tuple[str, int], data: bytes):
        if self.a_to_p.get(addr) == None:
            return
        super().process_datagram(addr, data)
    async def sendto(self, msg, addr):
        if self.a_to_p.get(addr) == None:
            return
        await super().sendto(msg, addr)

    async def sendto_id(self, msg, p: bytes):
        if self.p_to_a.get(p) == None:
            return
        await super().sendto(msg, self.p_to_a[p])
    async def broadcast(self, msg):
        for addr, p in self.a_to_p.items():
            await self.sendto(msg,addr)
    def get_al(self, addr: tuple[str, int]) -> Union[Peer, None]:
        return self.a_to_p.get(addr)
    