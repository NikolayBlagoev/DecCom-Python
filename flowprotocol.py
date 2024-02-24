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
                
                "disconnect_callback": "set_disconnect_callback",
                "get_peer": "get_peer",
                "connected_callback": "set_connected_callback",
                "send_ping": "send_ping"
                })
    bindings = dict(AbstractProtocol.bindings, **{
                    "remove_peer":"set_disconnect_callback",
                    "_lower_ping": "send_ping",
                    "peer_connected": "set_connected_callback",
                    "_lower_get_peer": "get_peer"
                    
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
        self._lower_ping = lambda : ...
        self._lower_get_peer = lambda : ...
        self.peer_connected_callback = lambda : ...
        self.disconnect_callback = lambda : ...
        
        self.tmp = get_cost
        if isinstance(get_cost,dict):
            self.get_cost = lambda peerid,i: self.tmp[peerid]
        else:
            self.get_cost = self.tmp
        
        
        self.target: dict[bytes, dict[bytes,float]] = dict()
        self.flowfromto: dict[tuple[bytes,bytes],int] = dict()
        self.flowto: dict[bytes,int] = dict()
        self.requests: dict[tuple[bytes,bytes],float] = dict()
        self.flow_peers: dict[bytes, FlowPeer] = dict()

        self.flows: int = 0
        self.attempt: int = 0
        self.targets = []
        
        self.capacity = capacity

    

    def process_datagram(self, addr: tuple[str, int], data: bytes):
        if data[0] == FlowProtocol.INTRODUCTION:
            peerid = data[1:33]
            stage = data[33]
            target = data[34]
            desired_flow = int.from_bytes(data[34:38],byteorder="big")
            if stage == self.stage + 1 and self.flow_peers.get(peerid) == None:
                self.flow_peers[peerid] = FlowPeer(desired_flow,peerid,addr,1)
                if target == 0:
                    self.flow_peers[peerid].min_cost_target = 0
                    self.flow_peers[peerid].minid = peerid
                    self.flow_peers[peerid].cost_target[peerid] = 0
                    self.targets.append(peerid)
                    self.target[peerid][peerid] = self.get_cost(peerid,0)
                    # update distance self??
                # reintroduce
            elif stage == self.stage - 1 and self.flow_peers.get(peerid) == None:
                self.flow_peers[peerid] = FlowPeer(desired_flow,peerid,addr,-1)
                # reintroduce
        elif data[0] == FlowProtocol.REQUEST_FLOW:
            peerid = data[1:33]
            target = data[33:65]
            stage = data[66]
            estimated_cost = struct.unpack(">f",data[67:])
            if Peer.get_current().id_node == target:
                # is me
                return
            elif self.target.get(peerid) == None or (self.flow >= self.capacity and self.flow_peers[peerid].direction == -1): # capacity matters !
                # send infinity
                return  
            elif self.target.get(peerid) != estimated_cost:
                
                # send updated cost (reject)
                return
            else:
                # accept the flow
                
                loop = asyncio.get_running_loop()
                loop.create_task(self.confirm_flow(target,peerid,addr,estimated_cost,self.flow_peers[peerid].direction))
                
        elif data[0] == FlowProtocol.ANSWER_FLOW:
            peerid = data[1:33]
            target = data[33:65]
            stage = data[65]
            cost = struct.unpack(">f",data[66:])
            if self.requests.get((peerid,target)) == None:
                # cancle flow 
                return
            elif self.requests.get((peerid,target)) == cost:
                # flow has been accepted
                self.flow += self.flow_peers[peerid].direction
                if self.flowto.get(target) == None:
                    self.flowto[target] = 0

                self.flowto[target] += self.flow_peers[peerid].direction
                if self.target[target] == None:
                    self.target[target] = dict()
                
                self.target[target][peerid] = cost + self.get_cost(peerid)
                    
                return
            else:
                # flow has been rejected
                del self.requests[(peerid,target)]
                self.flow_peers[peerid].cost_target[target] = cost
                # update cost to target
                return
                

            return
        elif data[0] == FlowProtocol.COSTTO_RESPONSE:
            return
        elif data[0] == FlowProtocol.CANCEL_FLOW:

            return

        self.callback(addr,data)
    async def start(self):
        await super().start()
    async def confirm_flow(self, target: bytes, topeerid:bytes, to, cost, direction):
        self.flow += direction
        if self.flowto.get(target) == None:
            self.flowto[target] = 0
        self.flowto[target] += direction # add flow information in case cancelled
        
        msg = bytearray([FlowProtocol.ANSWER_FLOW])
        msg += Peer.get_current().id_node + target + self.stage.to_bytes(1,byteorder = "bog") + struct.pack(">f",cost)
        await self._lower_sendto(msg,to)


    async def request_flow(self, flow_peer: FlowPeer):
        await self._lower_sendto(msg,flow_peer.addr)
        
    async def check_flow(self):
        if self.flow <= self.desired_flow:
            
            candidates: list[FlowPeer]= []
            for peerid,p in self.flow_peers.items():
                if p.desired_flow < p.flow:
                    candidates.append(p)
            

            if len(candidates) > 0:
                candidate = (candidates[0],candidates[0].min_cost_target)
                
                # request flow

            
            return
        else:
            # Do nothing I guess?
            return
        return
    def peer_connected(self,nodeid):

        self.peer_connected_callback(nodeid)

    
    def remove_peer(self, addr, nodeid):
        
        self.disconnect_callback(addr,nodeid) 
    


    def set_disconnect_callback(self, callback):
        self.disconnect_callback = callback
    def set_connected_callback(self, callback):
        self.peer_connected_callback = callback
    
        