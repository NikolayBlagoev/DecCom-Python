import asyncio
from dataclasses import dataclass
from typing import Callable
from deccom.protocols.abstractprotocol import AbstractProtocol
from deccom.protocols.wrappers import *
@dataclass
class _KA:
    addr: tuple[str,int] = None
    attempts: int = 3

class KeepAlive(AbstractProtocol):
    def __init__(self, interval = 20, timeout = 5, submodule=None, callback: Callable[[tuple[str, int], bytes], None] = lambda addr,msg: ...):
        assert timeout < interval
        self.keep_alives: dict[bytes,_KA] = dict()
        self.disconnected_callback = lambda *args: ...
        
        self.interval = interval
        self.timeout = timeout
        self.a_to_n = dict()
        self.refresh_loop = None
        super().__init__(submodule, callback)
    
    async def start(self, p):
        await super().start(p)
        loop = asyncio.get_event_loop()
        self.refresh_loop = loop.call_later(self.interval, self.check_each)

    async def stop(self):
        self.keep_alives.clear()
        if self.refresh_loop != None:
            self.refresh_loop.cancel()
        return await super().stop()
    def register_keep_alive(self, addr,node_id):
        self.keep_alives[node_id] = _KA(addr,3)
        self.a_to_n[addr] = node_id

    def deregister_keep_alive(self, node_id):
        if self.keep_alives.get(node_id) != None:
            if self.a_to_n.get(self.keep_alives[node_id].addr) != None:
                del self.a_to_n[self.keep_alives[node_id].addr]
            del self.keep_alives[node_id]

    def remove_peer(self, addr: tuple[str, int], node_id: bytes):
        if not self.started:
            return
        
        if self.keep_alives.get(node_id) == None:
            return
        self.keep_alives[node_id].attempts -= 1
        if self.keep_alives[node_id].attempts == 1:
            return asyncio.get_event_loop().create_task(self.send_ping(addr,lambda addr, id_node = node_id, self = self: self.resp(addr,id_node), lambda addr, id_node=node_id, self=self: self.remove_peer(addr, id_node),self.timeout))
        if self.keep_alives[node_id].attempts <= 0:
            if self.a_to_n.get(addr) != None:
                del self.a_to_n[addr]
            del self.keep_alives[node_id]
            self.disconnected_callback(addr,node_id)
    def resp(self,addr,id_node):
        if not self.started:
            return
        if self.keep_alives.get(id_node) == None:
            return
        self.keep_alives[id_node].attempts = 3
    @bindto("send_ping")
    async def _lower_ping(self, addr, success, failure, timeout):
        return
    async def send_ping(self, addr, success, fail, timeout):
        await self._lower_ping(addr, success, fail, timeout)
    
    def datagram_received(self, addr: tuple[str, int], data: bytes):
        if self.a_to_n.get(addr) != None:
            self.resp(addr, self.a_to_n.get(addr))
        return super().datagram_received(addr, data)
    def check_each(self):
        loop = asyncio.get_event_loop()
        for k,v in self.keep_alives.items():
            if v.attempts <= 1:
                continue
            v.attempts = 2
            loop.create_task(self.send_ping(v.addr,lambda addr, id_node = k, self = self: self.resp(addr,id_node), lambda addr, id_node=k, self=self: self.remove_peer(addr, id_node),self.timeout))

        self.refresh_loop = loop.call_later(self.interval, self.check_each)
            
