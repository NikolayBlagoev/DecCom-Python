from os import urandom
from typing import Union

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
        self.next: dict[bytes, float] = dict()
        self.prev: dict[bytes, float] = dict()
        self.outflows: dict[tuple[bytes,bytes], int] = dict() # next, target -> count
        self.inflows: dict[tuple[bytes,bytes], int] = dict() # prev, target -> count
        self.total_flows = []
        pass
class RequestForFlow(object):
    def __init__(self, uniqueid: bytes, to: FlowPeer, cost: float, target: bytes) -> None:
        self.uniqueid = uniqueid
        self.to = to
        self.cost = cost
        self.target = target
        pass
class RequestForChange(object):
    # randcc, to_from[0], to_from[1], proof[0], proof[1], repalcemenet_flow
    def __init__(self, smp: SamePeer, my_flow: bytes, curr_next: bytes, new_next: bytes, target: bytes, curr_cost: float, new_cost: float) -> None:
        self.smp = smp
        self.my_flow = my_flow
        self.curr_next = curr_next
        self.new_next = new_next
        self.curr_cost = curr_cost
        self.new_cost = new_cost
        self.target = target
        pass
class RequestForRedirect(object):
    def __init__(self,smp: SamePeer, curr_next: bytes, curr_prev: bytes, target: bytes, proof:float) -> None:
        self.smp = smp
        self.curr_pev = curr_prev
        self.curr_next = curr_next
        self.proof = proof
        self.target = target
        
class FlowNode(object):
    def __init__(self, flow, minflow, maxflow, capacity, stage) -> None:
        self.prev: dict[bytes, FlowPeer] = dict()
        self.next: dict[bytes, FlowPeer] = dict()
        self.same: dict[bytes, SamePeer] = dict()
        self.capacity = capacity
        self.flow = flow
        self.outstanding_outflow: dict[bytes, tuple[bytes, float]] = dict() # unique id - > target, cost
        self.outstanding_inflow: dict[bytes, tuple[bytes, bytes]] = dict() # unique id -> previous peer, their id
        self.inflow: dict[bytes, dict[bytes,tuple[bytes, bytes]]] = dict() # previous peer -> unique id -> unique id, target
        self.outflow: dict[bytes, tuple[bytes, bytes, float]] = dict() # unique id -> next peer, target, cost
        self.uniqueids: list[bytes] = [] # my unique ids
        self.map: dict[bytes, tuple[bytes,bytes]] = dict() # mine -> their, them
        self.minflow = minflow
        self.maxflow = maxflow
        self.desired_flow = 0
        if self.maxflow > 0:
            self.desired_flow = self.maxflow
        elif self.minflow < 0:
            self.desired_flow = self.minflow
        self.targets: dict[bytes, float] = dict()
        self.stage = stage
        pass

    def add_inflow(self, prvpr, theirid, target) -> Union[float, None]:
        uniqid = None
        minc = float("inf")
        self.flow += 1
        for k,v in self.outstanding_outflow.items():
            if v[0] == target and v[1] < minc:
                minc = v[1]
                uniqid = k
        if uniqid == None:
            uniqid = urandom(4)
            while uniqid in self.uniqueids:
                uniqid = urandom(4)
            self.uniqueids.append(uniqid)
            self.outstanding_inflow[uniqid] = (prvpr, theirid)
            
        else:
            del self.outstanding_outflow[uniqid]
            self.targets[target] = float("inf")
            mintt = float("inf")
            for _, rets in self.outstanding_outflow.items():
                if target == rets[0] and rets[1] < mintt:
                    mintt = rets[1]
            self.targets[target] = mintt
        self.map[uniqid] = (theirid, prvpr)
        if self.inflow.get(prvpr) == None:
            self.inflow[prvpr] = dict()
        self.inflow[prvpr][theirid] = (uniqid, target)
        return self.targets[target]
    def add_outflow(self, uniqueid, nxtpr, target, cost: float, costto_next: float):
        self.targets[target] = min(self.targets[target] if self.targets.get(target) != None else float("inf"), cost + costto_next)
        self.outflow[uniqueid] = (nxtpr, target, cost + costto_next)
        self.outstanding_outflow[uniqueid] = (target, cost + costto_next)

    def remove_outflow(self, myid):
        if self.outflow.get(myid) == None:
            return None
        ret = self.map.get(myid)
        nxt, target, cost = self.outflow[myid]
        if ret == None:
            del self.outflow[myid]
            del self.outstanding_outflow[myid]
            self.uniqueids.remove(myid)
            return None
        else:
            theirid, them = ret
            tmpid, trgt = self.inflow[them][theirid]
            assert tmpid == myid
            assert trgt == target
            nwflw = None
            mn = float("inf")
            for k,v in self.outstanding_outflow.items():
                if v[0] == target and v[1] < mn:
                    mn = v[1]
                    nwflw = k
            if nwflw == None:
                    print("dindnt match")
                    self.outstanding_inflow[myid] =(them,theirid) 
                    return None        
            else:
                    print("did match",self.prev[them].p.pub_key, "to", self.next[self.outflow[k][0]].p.pub_key)
                    self.inflow[them][theirid] = (nwflw, target)
                    self.map[nwflw] = (theirid, them)
                    del self.map[myid]
                    self.uniqueids.remove(myid)
                    trgt, cost = self.outstanding_outflow[nwflw]
                    del self.outstanding_outflow[nwflw]
                    self.inflow[them][theirid] = (nwflw,trgt)
                    return (cost, them, theirid)
                    
                    # notify previous of changed cost:
                    
                    
