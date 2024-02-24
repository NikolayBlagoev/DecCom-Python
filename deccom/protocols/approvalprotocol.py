import asyncio
import random
from deccom.utils.common import ternary_comparison
from asyncio import exceptions
from typing import Any, Callable, List
from deccom.peers.peer import Peer
from deccom.protocols.abstractprotocol import AbstractProtocol
class DictItem:
    def __init__(self,reader: asyncio.StreamReader,writer: asyncio.StreamWriter,fut: asyncio.Future, opened_by_me: int) -> None:
        self.reader = reader
        self.writer = writer
        self.fut = fut
        self.opened_by_me = opened_by_me
        pass
    
    
    

class ApprovalProtocol(AbstractProtocol):
    bindings = dict(AbstractProtocol.bindings, **{
                    
                    "approve_peer": "set_approve_connection"
                    
                })
    required_lower = AbstractProtocol.required_lower + ["set_approve_connection"]
    def __init__(self,submodule=None, callback: Callable[[tuple[str, int], bytes], None] = lambda addr, data: print(addr, data)):
        super().__init__(submodule, callback)


    def approve_peer(self, addr, peer, success, failure):
        
        success(addr,peer)