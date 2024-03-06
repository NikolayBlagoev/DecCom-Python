import asyncio
from typing import Callable, Union
from deccom.protocols.abstractprotocol import AbstractProtocol
from deccom.protocols.defaultprotocol import DefaultProtocol
from deccom.peers import Peer
from random import randint, sample
from deccom.protocols.wrappers import *

class AbstractPeerDiscovery(AbstractProtocol):

    offers = dict(AbstractProtocol.offers, **{
        "find_peer": "find_peer",
        "disconnected_callback": "set_disconnected_callback",
        "get_peer": "get_peer",
        "connected_callback": "set_connected_callback",
        "add_peer": "add_peer",
        "get_peers": "get_peers",
        "approve_connection": "set_approve_connection"
    })
    bindings = dict(AbstractProtocol.bindings, **{
                    "remove_peer": "set_disconnected_callback",
                    "add_peer": "set_connected_callback",

                    })
    required_lower = AbstractProtocol.required_lower

    
    def __init__(self, bootstrap_peers: list[Peer] = [], interval: int = 10, submodule=None, callback: Callable[[tuple[str, int], bytes], None] = lambda: ..., 
                 disconnected_callback=lambda addr, nodeid: None,
                 connected_callback: Callable[[Peer], None]=lambda peer: None):
        super().__init__(submodule, callback)
        self.interval = interval
        self.bootstrap_peers = bootstrap_peers
        self.disconnected_callback = disconnected_callback
        self.connected_callback = connected_callback
        self.connection_approval: Callable[[tuple[str,int], Peer, Callable[[tuple[str,int],Peer],None], Callable[[tuple[str,int],Peer],None], AbstractProtocol],None] = lambda addr, peer, success, failure: success(addr,peer)
        self.peers: dict[bytes, Peer] = dict()
    
    def set_connected_callback(self, callback: Callable[[Peer], None]):
        self.connected_callback = callback

    def set_disconnected_callback(self, callback):
        self.disconnected_callback = callback
    @bindfrom("connected_callback")
    def add_peer(self, addr: tuple[str,int], p: Peer):
        self.connected_callback(addr, p)
    
    def ban_peer(self, addr: tuple[str,int], p: Peer):
        return
    @bindfrom("disconnected_callback")
    def remove_peer(self, addr: tuple[str, int], node_id: bytes):
        self.disconnected_callback(addr, node_id)

    
    def set_approve_connection(self, callback):
        self.connection_approval = callback
    
    def get_peer(self, id) -> Union[Peer,None]:
        return self.peers.get(id)

    def get_peers(self) -> dict[bytes, Peer]:
        return self.peers
    
    async def find_peer(self, id: bytes) -> Peer:
        return self.get_peer(id)
