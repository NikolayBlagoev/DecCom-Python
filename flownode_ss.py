from dataclasses import dataclass
from math import exp
from os import urandom
import os
import random
import struct
from typing import Callable, Union

from deccom.peers.peer import Peer
class FlowPeer(object):
    def __init__(self, p: Peer, s: int, desired_flow: int, cost: float) -> None:
        self.p = p
        self.s = s
        self.desired_flow = desired_flow
        self.costto: float = cost
        self.mincostto: float = float("inf")
        self.mincostis: bytes = None
        self.dist_to_targ: dict[bytes,float] = dict()
        self.nextbest: float = float("inf")
    def updatemin(self):
        self.mincostto = float("inf")
        for k,v in self.dist_to_targ.items():
            if v < self.mincostto:
                self.mincostto = v
                self.mincostis = k
class SamePeer(object):
    def __init__(self, p: Peer) -> None:
        self.p = p
        self.inflows: dict[bytes, tuple[bytes, bytes,float]] = dict() # uniqueid -> prvpr, target, cost
        self.outflows: dict[bytes, tuple[bytes, bytes,float]]  = dict()  # uniqueid -> nxtpr, target, cost
        self.outflow_list: dict[bytes, list[bytes]] = dict()
        self.next: dict[bytes, float] = dict()
        pass
@dataclass
class RequestForFlow:
    uniqueid: bytes = None
    to: FlowPeer = None
    cost: float = 0
    target: bytes = None
    stg: int = 0
        
class RequestForChange(object):
    # randcc, to_from[0], to_from[1], proof[0], proof[1], repalcemenet_flow
    def __init__(self, smp: SamePeer, my_flow: bytes, curr_next: bytes, new_next: bytes, target: bytes, curr_cost: float, new_cost: float, nxt_cost: float) -> None:
        self.smp = smp
        self.my_flow = my_flow
        self.curr_next = curr_next
        self.new_next = new_next
        self.curr_cost = curr_cost
        self.new_cost = new_cost
        self.target = target
        self.nxt_cost = nxt_cost
        pass
class RequestForRedirect(object):
    def __init__(self,smp: SamePeer, curr_next: bytes, curr_prev: bytes, target: bytes, proof:float) -> None:
        self.smp = smp
        self.curr_pev = curr_prev
        self.curr_next = curr_next
        self.proof = proof
        self.target = target
        self.myid = None
# flownode for a source-sink
class FlowNode_SS(object):
    def __init__(self, flow, minflow, maxflow, capacity, stage) -> None:
        self.prev: dict[bytes, FlowPeer] = dict()
        self.next: dict[bytes, FlowPeer] = dict()
        self.same: dict[bytes, SamePeer] = dict()
        self.capacity = capacity
        self.flow = flow
        self.outstanding_outflow: dict[bytes, tuple[bytes, float]] = dict() # unique id - > target, cost
        self.outstanding_inflow: dict[bytes, tuple[bytes, bytes]] = dict() # unique id -> previous peer, their id
        self.inflow: dict[bytes, dict[bytes,tuple[bytes, bytes, float]]] = dict() # previous peer -> their unique id -> my unique id, target, intermediate cost
        self.outflow: dict[bytes, tuple[bytes, bytes, float]] = dict() # unique id -> next peer, target, cost
        self.uniqueids: list[bytes] = [] # my unique ids
        self.map: dict[bytes, tuple[bytes,bytes]] = dict() # mine -> their, them
        self.minflow = minflow
        self.maxflow = maxflow
        self.desired_flow_source = self.maxflow
        self.desired_flow_sink = -self.desired_flow_source 
        self.myid = None
        
        self.targets: dict[bytes, float] = dict()
        self.stage = stage
        self.same_attempts = dict()
        pass

    def add_inflow(self, prvpr, theirid, target, cost) -> Union[float, None]:
        uniqid = None
        
        self.desired_flow_sink += 1
        
        
        uniqid = urandom(4)
        while uniqid in self.uniqueids:
                uniqid = urandom(4)
        self.uniqueids.append(uniqid)
        self.outstanding_inflow[uniqid] = (prvpr, theirid)
        if self.inflow.get(prvpr) == None:
            self.inflow[prvpr] = dict()
        self.inflow[prvpr][theirid] = (uniqid, target, cost)
            
        
        return 0
    def ignore_same(self, id_node):
        self.same_attempts[id_node] = 5

    def min_cost_to_target(self, target):
        
        return 0

    def add_outflow(self, uniqueid, nxtpr, target, cost: float, costto_next: float):
        # if self.uniqueids
        costto_next = self.next[nxtpr].costto
        
        if uniqueid not in self.uniqueids:
            self.uniqueids.append(uniqueid)
        else:
            return False
        self.flow += 1

        self.desired_flow_source -= 1

        self.targets[target] = min(self.targets[target] if self.targets.get(target) != None else float("inf"), cost + costto_next)
        self.outflow[uniqueid] = (nxtpr, target, cost + costto_next)
        self.outstanding_outflow[uniqueid] = (target, cost + costto_next)


        return True
    def get_next_node(self):
        smlst_cost = float("inf")
        chc = None
        
        for nodeid, node in self.next.items():
            #print("evaluating",self.myid, node.mincostto)
            if node.desired_flow < 0 and node.mincostto + node.costto < smlst_cost and node.mincostis == self.myid:
                chc = node
                smlst_cost = node.mincostto + node.costto
        return chc, smlst_cost
    def gen_new_uniqid(self):
        ret = os.urandom(4)
        while ret in self.uniqueids:
            ret = os.urandom(4)
        return ret
    def get_random_target(self):
        if len(self.targets.items()) == 0:
            return None
        return random.sample(self.targets.items(), 1)[0]
    def remove_peer(self, pid):
        return # NOT IMPLEMENTED
    def update_peer(self, pid, target, cost, dflow):
        if self.next.get(pid) != None:
            self.next[pid].dist_to_targ[target] = cost
            self.next[pid].updatemin()
            self.next[pid].desired_flow = dflow

    def construct_update_message(self, header):
        msg = bytearray([header])
        tmp = bytearray()
        for k, d in self.inflow.items():
            for _, v in d.items():
                tmp += v[0]
                tmp += k
                tmp += v[1]
                tmp += struct.pack(">f", v[2])
        tmp = bytes(tmp)
        msg += len(tmp).to_bytes(4, byteorder="big")
        msg += tmp
        tmp = bytearray()
        lst = []
        for k,v in self.outflow.items():
            tmp += k
            lst.append(v[0])
            tmp += v[0]
            tmp += v[1]
            tmp += struct.pack(">f",self.next[v[0]].costto)
        msg += len(tmp).to_bytes(4, byteorder="big")
        msg += tmp
        for k,p in self.next.items():
            if p.p.id_node in lst:
                continue
            msg += p.p.id_node
            msg += struct.pack(">f", p.costto)
        return msg
    def update_same(self, pid, msg):
        p = self.same[pid].p
        del self.same[pid]
        self.same[pid] = SamePeer(p)

        i = 0
        
        dif = int.from_bytes(msg[i:i+4], byteorder="big") + i + 4
        #print("how much is ",dif)
        i += 4
        while i < dif:
            uniqid = msg[i:i+4]
            i+=4
            prvpr = msg[i:i+32]
            i+=32
            trgt = msg[i:i+32]
            i+=32
            cst = struct.unpack(">f", msg[i:i+4])[0]
            self.same[pid].inflows[uniqid] = (prvpr, trgt, cst)
            i += 4
        dif = int.from_bytes(msg[i:i+4], byteorder="big") + i + 4
        i += 4
        while i < dif:
            uniqid = msg[i:i+4]
            i+=4
            prvpr = msg[i:i+32]
            i+=32
            trgt = msg[i:i+32]
            i+=32
            cst = struct.unpack(">f", msg[i:i+4])[0]
            i += 4
            self.same[pid].outflows[uniqid] = (prvpr, trgt, cst)
            if self.same[pid].outflow_list.get(prvpr) == None:
                self.same[pid].outflow_list[prvpr] = []
            self.same[pid].outflow_list[prvpr].append(uniqid)
            self.same[pid].next[prvpr] = cst
        while i < len(msg):
            to = msg[i:i+32]
            i+=32
            cst = struct.unpack(">f", msg[i:i+4])[0]
            i += 4
            self.same[pid].next[to] = cst
    
                    
    
    def remove_outflow(self, myid):
        
        if self.outflow.get(myid) == None:
            return
        self.flow -= 1
        self.desired_flow_source += 1
        
        nxt,trgt,cst = self.outflow[myid]
        del self.outstanding_outflow[myid]
        del self.outflow[myid]
        self.uniqueids.remove(myid)
            
        self.targets[trgt] = 0
    
    def remove_inflow(self, them, theirid):
        
        if self.inflow.get(them) == None or self.inflow[them].get(theirid) == None:
            return
        myid, trgt, cst  = self.inflow[them][theirid]
        self.desired_flow_sink -= 1
        
        del self.outstanding_inflow[myid]
        del self.inflow[them][theirid]
        self.uniqueids.remove(myid)

    def push_back(self, flow_id, prvpr):
        # if self.inflow.get(prvpr) == None or self.inflow[prvpr].get(flow_id) == None:
        #     if self.outstanding_inflow.get(myid) != None:
        #         del self.outstanding_inflow[myid]
        #     return
        myid, target, cst = self.inflow[prvpr][flow_id]
        self.desired_flow_sink -= 1
        
        del self.outstanding_inflow[myid]
        del self.inflow[prvpr][flow_id]
        if self.map.get(myid) != None:
                del self.map[myid]
        self.uniqueids.remove(myid)
        
    def parent_change(self, curr_id, curr_prv, new_id, new_prv, new_cost):
        myid, target, cst = self.inflow[curr_prv][curr_id]
        del self.inflow[curr_prv][curr_id]
        self.map[myid] = (new_id, new_prv)
        if self.inflow.get(new_prv) == None:
            self.inflow[new_prv] = dict()
        self.inflow[new_prv][new_id] = (myid, target, new_cost)
        if self.outstanding_inflow.get(myid) != None:
            self.outstanding_inflow[myid] = (new_prv, new_id)
    
    def perform_change(self, curr_id, curr_nxt, nw_nxt, nw_cost):
        if self.outflow.get(curr_id) == None:
            return False
        _,_,curr_cost = self.outflow[curr_id]
        self.outflow[curr_id] = (nw_nxt, self.outflow[curr_id][1], nw_cost)
        if self.outstanding_outflow.get(curr_id) != None:
            self.outstanding_outflow[curr_id] = (self.outstanding_outflow[curr_id][0], nw_cost)
        return curr_cost != nw_cost
                    
                    
                    
