import asyncio
from typing import Callable, Union
from deccom.peers.peer import Peer
from deccom.protocols.abstractprotocol import AbstractProtocol
from deccom.protocols.streamprotocol import StreamProtocol
from deccom.protocols.wrappers import bindfrom, bindto
from deccom.utils.common import *

class DelayProtocol(AbstractProtocol):
    def __init__(self, delay_map, submodule=None, callback: Callable[[tuple[str, int], bytes], None] = ...):
        self.stream_callback = lambda data, node_id,addr: ...
        self.delay_map = delay_map
        super().__init__(submodule, callback)

    @bindfrom("stream_callback")
    def process_data(self,data,node_id,addr):
        print("delay...")
        p = self.get_peer(node_id)
        print(p)
        loop = asyncio.get_event_loop()
        dl = self.delay_map(p.pub_key, self.peer.pub_key)
        print(dl)
        print("will receive in ",dl[0]/1000 + len(data)/(1024**3*dl[1]))
        loop.call_later(dl[0]/1000 + len(data)/(1024**3*dl[1]), self.stream_callback, data, node_id, addr)
        #self.stream_callback(data,node_id,addr)

        
    @bindto("get_peer")
    def get_peer(self, id: bytes) -> Union[Peer,None]:
        return None