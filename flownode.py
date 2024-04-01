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
        
class FlowNode(object):
    def __init__(self, flow, minflow, maxflow, capacity, stage) -> None:
        self.prev: dict[bytes, FlowPeer] = dict()
        self.next: dict[bytes, FlowPeer] = dict()
        self.same: dict[bytes, SamePeer] = dict()
        self.capacity = capacity
        self.flow = flow
        self.outstanding_outflow: dict[bytes, tuple[bytes, float]] = dict() # unique id - > target, cost
        self.outstanding_inflow: dict[bytes, tuple[bytes, bytes,int]] = dict() # unique id -> previous peer, their id, count
        self.inflow: dict[bytes, dict[bytes,tuple[bytes, bytes, float]]] = dict() # previous peer -> their unique id -> my unique id, target, intermediate cost
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
        self.same_attempts = dict()
        pass

    def add_inflow(self, prvpr, theirid, target, cost) -> Union[float, None]:
        uniqid = None
        minc = float("inf")
        # self.flow += 1
        self.desired_flow += 1
        for k,v in self.outstanding_outflow.items():
            if v[0] == target and v[1] < minc:
                minc = v[1]
                uniqid = k
        if uniqid == None:
            uniqid = urandom(4)
            while uniqid in self.uniqueids:
                uniqid = urandom(4)
            self.uniqueids.append(uniqid)
            self.outstanding_inflow[uniqid] = (prvpr, theirid, 12)
            
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
        self.inflow[prvpr][theirid] = (uniqid, target, cost)
        return self.targets[target]
    def ignore_same(self, id_node):
        self.same_attempts[id_node] = 5
    def min_cost_to_target(self, target):
        minv = float("inf")
        if self.targets.get(target) == None:
            return minv
        
        for k,v in self.outstanding_outflow.items():
            if v[0] == target:
                minv = min(minv, v[1])
        return minv

    def add_outflow(self, uniqueid, nxtpr, target, cost: float, costto_next: float):
        # if self.uniqueids
        costto_next = self.next[nxtpr].costto
        if uniqueid not in self.uniqueids:
            self.uniqueids.append(uniqueid)
        else:
            return False
        self.flow += 1
        nwid = None
        prvpr = None
        
        self.desired_flow -= 1
        # Match outflow with inflow here...
        for k, v in self.outstanding_inflow.items():
            if self.inflow[v[0]][v[1]][1] == target:
                nwid = k
                prvpr = v[0]
                break
        if nwid == None:
        
        
            self.targets[target] = min(self.targets[target] if self.targets.get(target) != None else float("inf"), cost + costto_next)
            self.outflow[uniqueid] = (nxtpr, target, cost + costto_next)
            self.outstanding_outflow[uniqueid] = (target, cost + costto_next)

        else:
            theirid, prvpr = self.map[nwid]
            #assert trgt == target
            assert self.inflow[prvpr][theirid][0] == nwid
            assert self.outflow.get(uniqueid) == None
            self.outflow[uniqueid] = (nxtpr, target, cost + costto_next)
            self.inflow[prvpr][theirid] = (uniqueid, target, self.inflow[prvpr][theirid][2])
            del self.outstanding_inflow[nwid]
            del self.map[nwid]
            self.uniqueids.remove(nwid)
            
            self.map[uniqueid] = (theirid,prvpr)
            # Notify previous of change here
        return True
    def get_next_node(self):
        smlst_cost = float("inf")
        chc = None
        trgts = []
        for k,v in self.outstanding_inflow.items():
            prvpr, theirid, _ = v
            _,trgt,_ = self.inflow[prvpr][theirid]
            if trgt not in trgts:
                trgts.append(trgt)
        for nodeid, node in self.next.items():
            
            if node.desired_flow < 0 and node.mincostto + node.costto < smlst_cost and (len(trgts) == 0 or node.mincostis in trgts):
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
        if self.next.get(pid) != None:
            to_remove = []
            for k,v in self.outflow.items():
                if v[0] == pid:
                    to_remove.append(k)
            for t in to_remove:
                self.remove_outflow(t)
            del self.next[pid]
            
        elif self.inflow.get(pid) != None:
            to_remove = []
            dv = self.inflow[pid]
            for k,v in dv.items():
            
                to_remove.append(k)
            for t in to_remove:
                self.remove_inflow(pid, t)
            del self.prev[pid]
            
        elif self.same.get(pid) != None:
            del self.same[pid]
        
        return
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
    def get_same(self, temperature):
        mxmm_chng = 0
        chng_request = None
        flw_per_peer: dict[bytes, list[bytes]] = dict()
        print("CHECKING FOR SAME")
        for mid, flow in self.outflow.items():
            if flw_per_peer.get(flow[0]) == None:
                flw_per_peer[flow[0]] = []
            flw_per_peer[flow[0]].append(mid)
        for idx, p in self.same.items():
            #print("considering peer")
            if self.same_attempts.get(p.p.id_node) != None:
                if self.same_attempts[p.p.id_node] > 0:
                    print("more than 0")
                    self.same_attempts[p.p.id_node] -= 1
                    continue
            #print(p.inflows)
            #print(p.outflows)
            for flid, flw in p.outflows.items():
                
                to,trgt,cst = flw
                #print("considering their outflow with cost ", cst)
                if self.next.get(to) == None:
                    continue # we dont know
                
                if p.inflows.get(flid) != None and self.capacity > self.flow:
                    prvpr, _, cst_prv = p.inflows[flid]
                    if self.prev.get(prvpr) != None:
                        mcstprv = self.prev[prvpr].costto
                        mcstnxt = self.next[to].costto
                        if (cst_prv + cst) - (mcstprv + mcstnxt) > mxmm_chng:
                            mxmm_chng = (cst_prv + cst) - (mcstprv + mcstnxt)
                            chng_request = RequestForRedirect(p, to, prvpr, trgt, (mcstprv, mcstnxt))
                            print("MINIMISATION FOR REDIRECT")
                        elif  mxmm_chng <= 0 and exp(((cst_prv + cst) - (mcstprv + mcstnxt))/temperature) > random.uniform(0,1):
                            mxmm_chng = (cst_prv + cst) - (mcstprv + mcstnxt)
                            chng_request = RequestForRedirect(p, to, prvpr, trgt, (mcstprv, mcstnxt))
                            print("WRONG MINIMISATION FOR REDIRECT")
                        else:
                            print("MINIMISATION OF ", cst_prv, cst, mcstprv , mcstnxt)
                
                
                for mid, flow in self.outflow.items():#223, 258
                    if flow[0] == to:
                        continue
                    if p.next.get(flow[0]) == None:
                        continue # they don't know
                    if flow[1] != trgt:
                        continue # different target
                    
                    if (cst + self.next[flow[0]].costto) - (p.next[flow[0]] + self.next[to].costto) > mxmm_chng:
                        mxmm_chng = (cst + self.next[flow[0]].costto) - (p.next[flow[0]] + self.next[to].costto)
                        chng_request = RequestForChange(p, flw_per_peer[flow[0]][0], flow[0], to, trgt, self.next[flow[0]].costto, self.next[to].costto, flow[2] - self.next[flow[0]].costto)
                        print("MINIMISATION FOUND!!", cst, self.next[flow[0]].costto,  p.next[flow[0]], self.next[to].costto)
                    elif mxmm_chng <= 0 and exp(((cst + self.next[flow[0]].costto) - (p.next[flow[0]] + self.next[to].costto))/temperature) > random.uniform(0,1):
                        mxmm_chng = (cst + self.next[flow[0]].costto) - (p.next[flow[0]] + self.next[to].costto)
                        chng_request = RequestForChange(p, flw_per_peer[flow[0]][0], flow[0], to, trgt, self.next[flow[0]].costto, self.next[to].costto, flow[2] - self.next[flow[0]].costto)
                        print("WRONG MINIMISATION FOUND!!")

        return chng_request
                    
    def perform_change(self, curr_id, curr_nxt, nw_nxt, nw_cost):
        if self.outflow.get(curr_id) == None:
            return False
        _,_,curr_cost = self.outflow[curr_id]
        self.outflow[curr_id] = (nw_nxt, self.outflow[curr_id][1], nw_cost)
        if self.outstanding_outflow.get(curr_id) != None:
            self.outstanding_outflow[curr_id] = (self.outstanding_outflow[curr_id][0], nw_cost)
        return curr_cost != nw_cost
    def remove_outflow(self, myid, set_val = 12):
        
        if self.outflow.get(myid) == None:
            return
        self.flow -= 1
        self.desired_flow += 1
        if self.outstanding_outflow.get(myid) == None:
            theirid, them = self.map[myid]
            del self.outflow[myid]
            self.outstanding_inflow[myid] = (them, theirid,set_val)
        else:
            nxt,trgt,cst = self.outflow[myid]
            del self.outstanding_outflow[myid]
            del self.outflow[myid]
            self.uniqueids.remove(myid)
            mincost = float("inf")
            for k,v in self.outstanding_outflow.items():
                if v[0] == trgt:
                    mincost = min(mincost, v[1])
            self.targets[trgt] = mincost
    
    def remove_inflow(self, them, theirid):
        
        if self.inflow.get(them) == None or self.inflow[them].get(theirid) == None:
            return
        myid, trgt, cst  = self.inflow[them][theirid]
        self.desired_flow -= 1
        if self.outstanding_inflow.get(myid) == None:
            nxtpr, trgt2, cost = self.outflow[myid]
            assert trgt == trgt2
            self.outstanding_outflow[myid] = (trgt,cost)
            mincost = float("inf")
            for k,v in self.outstanding_outflow.items():
                if v[0] == trgt:
                    mincost = min(mincost, v[1])
            self.targets[trgt] = mincost
            del self.inflow[them][theirid]
        else:
            del self.outstanding_inflow[myid]
            del self.inflow[them][theirid]
            self.uniqueids.remove(myid)

    def push_back(self, flow_id, prvpr):
        # if self.inflow.get(prvpr) == None or self.inflow[prvpr].get(flow_id) == None:
        #     if self.outstanding_inflow.get(myid) != None:
        #         del self.outstanding_inflow[myid]
        #     return
        myid, target, cst = self.inflow[prvpr][flow_id]
        self.desired_flow -= 1
        if self.outstanding_inflow.get(myid) != None:
            del self.outstanding_inflow[myid]
            del self.inflow[prvpr][flow_id]
            if self.map.get(myid) != None:
                del self.map[myid]
            self.uniqueids.remove(myid)
        else:
            nxptpr, target, cost = self.outflow[myid]
            self.outstanding_outflow[myid] = (target, cost)
            del self.inflow[prvpr][flow_id]
            if self.map.get(myid) != None:
                del self.map[myid]
    def parent_change(self, curr_id, curr_prv, new_id, new_prv, new_cost):
        myid, target, cst = self.inflow[curr_prv][curr_id]
        del self.inflow[curr_prv][curr_id]
        self.map[myid] = (new_id, new_prv)
        if self.inflow.get(new_prv) == None:
            self.inflow[new_prv] = dict()
        self.inflow[new_prv][new_id] = (myid, target, new_cost)
        if self.outstanding_inflow.get(myid) != None:
            self.outstanding_inflow[myid] = (new_prv, new_id, 12)
    
        
                    
                    
                    
