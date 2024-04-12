import asyncio
from typing import Callable
from deccom.protocols.abstractprotocol import AbstractProtocol
from deccom.protocols.wrappers import *


class KeepAlive(AbstractProtocol):
    def __init__(self, interval = 20, timeout = 10, submodule=None, callback: Callable[[tuple[str, int], bytes], None] = lambda addr,msg: ...):
        assert timeout < interval
        self.keep_alives: dict[bytes,tuple[str,int]] = dict()
        self.disconnected_callback = lambda *args: ...
        self.interval = interval
        self.timeout = timeout
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
        self.keep_alives[node_id] = addr

    def register_keep_alive(self, node_id):
        if self.keep_alives.get(node_id) != None:
            del self.keep_alives[node_id]

    def remove_peer(self, addr: tuple[str, int], node_id: bytes):
        if not self.started:
            return
        if self.keep_alives.get(node_id) != None:
            del self.keep_alives[node_id]
        self.disconnected_callback(addr,node_id)
    @bindto("send_ping")
    async def _lower_ping(self, addr, success, failure, timeout):
        return
    async def send_ping(self, addr, success, fail, timeout):
        await self._lower_ping(addr, success, fail, timeout)
    def check_each(self):
        loop = asyncio.get_event_loop()
        for k,v in self.keep_alives.items():
            loop.create_task(self.send_ping(v,lambda *args: ..., lambda addr, id_node=k, self=self: self.remove_peer(addr, id_node),self.timeout))

        self.refresh_loop = loop.call_later(self.interval, self.check_each)
            
