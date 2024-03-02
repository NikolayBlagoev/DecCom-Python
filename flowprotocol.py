import asyncio
from deccom.utils.common import ternary_comparison
from typing import Any, Callable, List
from sys import maxsize
from deccom.peers.peer import Peer
import struct
from deccom.protocols.abstractprotocol import AbstractProtocol
class FlowPeer:
    def __init__(self, desired_flow: int, peerid: bytes, addr, direction):
        self.desired_flow = desired_flow
        self.peerid = peerid
        self.flow = 0
        self.addr = addr
        self.cost_target = dict()
        self.min_cost_target = float("inf")
        self.minid: bytes = None
        self.direction = direction
        
    


class FlowProtocol(AbstractProtocol):
    # Bird opening:
    INTRODUCTION = int.from_bytes(b'\xf4', byteorder="big")
    COSTTO_QUERY = int.from_bytes(b'\xd5', byteorder="big")
    COSTTO_RESPONSE = int.from_bytes(b'\xf3', byteorder="big")
    REQUEST_FLOW = int.from_bytes(b'\xf6', byteorder="big")
    ANSWER_FLOW = int.from_bytes(b'\xe3', byteorder="big")
    CANCEL_FLOW = int.from_bytes(b'\xc5', byteorder="big")
    offers = dict(AbstractProtocol.offers,**{  
                
                
                })
    bindings = dict(AbstractProtocol.bindings, **{
                    "_lower_broadcast":"broadcast",
                    "_lower_getal": "get_al"
                    
                })
    required_lower = AbstractProtocol.required_lower + ["send_ping","get_peer", "connected_callback", "disconnect_callback"]
    def __init__(self,  stage, max_stage, get_cost, capacity = maxsize, flow_min = 0, flow_max = 0, submodule=None, callback: Callable[[tuple[str, int], bytes], None] = ...):
        super().__init__(submodule, callback)
        self.flow = 0
        self.stage: int = stage
        self.max_stage = max_stage
        self.flow_min = flow_min
        self.flow_max = flow_max
        self.desired_flow = 0
        if flow_max == 0 and flow_min < 0:
            self.desired_flow = flow_min
        elif flow_max > 0 and flow_min == 0:
            self.desired_flow = flow_max
        self._lower_broadcast = lambda : ...
        self._lower_get_al = lambda : ...
        self.tmp = get_cost
        if isinstance(get_cost,dict):
            self.get_cost = lambda peerid,i: self.tmp[peerid]
        else:
            self.get_cost = self.tmp
        
        
        self.target: dict[bytes, dict[bytes,float]] = dict()

        self.flowfrom: dict[tuple[bytes,bytes],bytes] = dict()
        self.flowto: dict[bytes,bytes] = dict()
        self.requests: dict[tuple[bytes,bytes],float] = dict()
        self.outstanding_flow: dict[bytes, bytes] = dict()
        self.flow_peers: dict[bytes, FlowPeer] = dict()

        self.targets = []
        
        self.capacity = capacity

    

    def process_datagram(self, addr: tuple[str, int], data: bytes):
        p: Peer = self._lower_get_al(addr)
        if data[0] == FlowProtocol.INTRODUCTION:
            desired_flow = data[1]
            curr_flow = data[2]
            stage = data[3]
            direction = 1
            if stage < self.stage:
                direction = -1
            self.flow_peers[p.id_node] = FlowPeer(desired_flow, p.id_node, addr, direction)
        self.callback(addr,data)
    async def start(self):
        await super().start()
        loop = asyncio.get_event_loop()
        loop.call_later(7, self.introduce)
        loop.call_later(9, self._check_flow)
    
    def introduce(self):
        msg = bytearray([FlowProtocol.INTRODUCTION])
        msg += self.desired_flow.to_bytes(1,"big")
        msg += self.flow.to_bytes(1,"big")
        msg += self.stage.to_bytes(1,"big")
        loop = asyncio.get_event_loop()
        loop.create_task(self._lower_broadcast(msg))
        
    async def confirm_flow(self, target: bytes, topeerid:bytes, flow_id, cost, direction):
        
        await self._lower_sendto(msg,to)
    
    async def reject_flow(self, target: bytes, topeerid:bytes, flow_id, cost, direction):
        
        await self._lower_sendto(msg,to)

    async def request_flow(self, flow_peer: FlowPeer):
        await self._lower_sendto(msg,flow_peer.addr)
    def _check_flow(self):
        loop = asyncio.get_event_loop()
        loop.create_task(self.check_flow())
    async def check_flow(self):
        if self.flow <= self.desired_flow:

        loop = asyncio.get_event_loop()
        loop.call_later(5, self._check_flow)
        return
    


    
        