import asyncio
from typing import Callable, Union
from deccom.peers.peer import Peer
from deccom.protocols.abstractprotocol import AbstractProtocol
from deccom.protocols.streamprotocol import StreamProtocol
from deccom.protocols.wrappers import bindfrom, bindto
from deccom.utils.common import *

class DelayProtocol(AbstractProtocol):
    def __init__(self, delay_map, submodule=None, callback: Callable[[tuple[str, int], bytes], None] = ...):

        self.delay_map = delay_map
        super().__init__(submodule, callback)

    
        #self.stream_callback(data,node_id,addr)
    async def send_stream(self,node_id,data, ignore_sz = 0):
        # print("delay...")
        p = self.get_peer(node_id)
        # print(p)
        loop = asyncio.get_event_loop()
        dl = self.delay_map(p.pub_key, self.peer.pub_key)
        sz = len(data) - ignore_sz
        # print(dl)
        # print("will send in ",dl[0]/1000 + sz/(1024**3*dl[1]))
        await asyncio.sleep(dl[0]/1000 + sz/(1024**3*dl[1]))
        if self.started:
            return await self._lower_send_to(node_id,data)
    @bindto("send_stream")
    async def _lower_send_to(self, nodeid, data):
        return
    @bindto("get_peer")
    def get_peer(self, id: bytes) -> Union[Peer,None]:
        return None