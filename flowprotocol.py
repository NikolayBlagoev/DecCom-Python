import asyncio
import random
from deccom.protocols.wrappers import *
from deccom.utils.common import ternary_comparison
from typing import Any, Callable, List
from sys import maxsize
from deccom.peers.peer import Peer
import struct
from os import urandom
from deccom.protocols.abstractprotocol import AbstractProtocol
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
        self.flows: dict[tuple[bytes,bytes], tuple[int, float]] = dict()
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
class FlowProtocol(AbstractProtocol):
    INTRODUCTION = int.from_bytes(b'\xb3', byteorder="big") #Nimzo-Larsen Attack
    FLOW_REQUEST = int.from_bytes(b'\xe5', byteorder="big")
    FLOW_RESPONSE = int.from_bytes(b'\xb2', byteorder="big")
    CHANGE = int.from_bytes(b'\xd6', byteorder="big")
    PUSH_BACK_FLOW = int.from_bytes(b'\xc4', byteorder="big")
    CANCEL_FLOW = int.from_bytes(b'\xf5', byteorder="big")
    QUERY_FLOWS = int.from_bytes(b'\xe3', byteorder="big")
    PROPOSE_CHANGE = int.from_bytes(b'\xf6', byteorder="big")
    RESPOND_CHANGE = int.from_bytes(b'\xd4', byteorder="big")
    NOTIFY_CHANGE_IN_COST = int.from_bytes(b'\xd5', byteorder="big")
    def __init__(self, stage: int, max_stage: int, capacity: int, flow: int, minflow: int, maxflow: int, costmap, submodule=None, callback: Callable[[tuple[str, int], bytes], None] = ...):
        super().__init__(submodule, callback)
        self.flow = flow
        self.minflow = minflow
        self.maxflow = maxflow
        self.desired_flow = 0
        self.iterationsss = []
        if self.maxflow > 0:
            self.desired_flow = self.maxflow
        elif self.minflow < 0:
            self.desired_flow = self.minflow
        self.targets: dict[bytes, float] = dict()
        self.stage = stage
        self.max_stage = max_stage
        self.prev: dict[bytes, FlowPeer] = dict()
        self.next: dict[bytes, FlowPeer] = dict()
        self.same: dict[bytes, SamePeer] = dict()
        self.capacity = capacity
        self.outstanding_outflow: dict[bytes, tuple[bytes, float]] = dict() # unique id - > target, cost
        self.outstanding_inflow: dict[bytes, tuple[bytes, bytes]] = dict() # unique id -> previous peer, their id
        self.inflow: dict[bytes, dict[bytes,tuple[bytes, bytes]]] = dict() # previous peer -> unique id -> unique id, target
        self.outflow: dict[bytes, tuple[bytes, bytes, float]] = dict() # unique id -> next peer, target, cost
        self.uniqueids: list[bytes] = [] # my unique ids
        self.map: dict[bytes, tuple[bytes,bytes]] = dict() # mine -> their, them
        self.requested_flows: tuple[bytes,FlowPeer,float, bytes] = None
        self.costmap = costmap
        self.T = 1
    async def start(self, p : Peer):
        await super().start(p)
        if self.stage == self.max_stage:
            self.targets[self.peer.id_node] = 0
        self._periodic()
    
    @bindto("get_al")
    def get_al(self, addr) -> Peer:
        return None
    @bindto("broadcast")
    async def broadcast(self, msg):
        return None

    
    def process_datagram(self, addr: tuple[str, int], data: bytes):
        p: Peer = self.get_al(addr)
        if data[0] == FlowProtocol.INTRODUCTION:
            print("peer introducing", addr)
            desired_flow = int.from_bytes(data[1:9], byteorder="big", signed=True)
            stage = int.from_bytes(data[9:17], byteorder="big")
            if stage == self.stage-1:
                fp = FlowPeer(p, stage, desired_flow, self.costmap(self.peer.pub_key, p.pub_key))
                self.prev[p.id_node] = fp
            elif stage == self.stage + 1:
                if stage == self.max_stage:
                    fp = FlowPeer(p,stage,int.from_bytes(data[1:9], byteorder="big", signed=True), self.costmap(self.peer.pub_key, p.pub_key))
                    fp.mincostto = 0
                    fp.dist_to_targ[p.id_node] = 0
                    fp.mincostis = p.id_node
                    self.targets[p.id_node] = self.costmap(self.peer.pub_key, p.pub_key)

                    self.next[p.id_node] = fp
                else:
                    fp = FlowPeer(p, stage, desired_flow, self.costmap(self.peer.pub_key, p.pub_key))
                    self.next[p.id_node] = fp
            elif stage == self.stage:
                self.same[p.id_node] = SamePeer(p)
        
        elif data[0] == FlowProtocol.FLOW_REQUEST:
            bts = data[1:5]
            target = data[5:37]
            cst = struct.unpack(">f", data[37:])[0]
            loop = asyncio.get_running_loop()
            if self.desired_flow >= 0 or self.flow >= self.capacity or self.targets.get(target) == None:
                print("too much, cant accept, or dont know")
                msg = bytearray([FlowProtocol.FLOW_RESPONSE])
                msg += bts
                msg += self.desired_flow.to_bytes(8, byteorder="big", signed=True)
                msg += target
                msg += struct.pack(">f", float("inf"))
                loop.create_task(self._lower_sendto(msg, addr))
            
            elif self.targets.get(target) != cst:
                print("wrong cost", cst, self.targets.get(target))
                msg = bytearray([FlowProtocol.FLOW_RESPONSE])
                msg += bts
                msg += self.desired_flow.to_bytes(8, byteorder="big", signed=True)
                msg += target
                msg += struct.pack(">f", self.targets.get(target))
                loop.create_task(self._lower_sendto(msg, addr))
            else:
                uniqid = None
                for idx, trgtcst in self.outstanding_outflow.items():
                    if target == trgtcst[0] and cst == trgtcst[1]:
                        uniqid = idx
                        break
                if uniqid == None:
                    # This shouldn't happen unless it is a sink!
                    uniqid = urandom(4)
                
                
                    while uniqid in self.uniqueids:
                        uniqid = urandom(4)
                    self.uniqueids.append(uniqid)
                    self.outstanding_inflow[uniqid] = (p.id_node,bts)
                    self.map[uniqid] = (bts,p.id_node)
                else:
                    self.map[uniqid] = (bts, p.id_node)
                    trgtcst = self.outstanding_outflow[uniqid]
                    del self.outstanding_outflow[uniqid]
                    self.targets[target] = float("inf")
                    minc = float("inf")
                    for idx, rets in self.outstanding_outflow.items():
                        if target == rets[0] and rets[1] < minc:
                            minc = rets[1]
                    self.targets[target] = minc
                   
                    # might need to rebroadcast
                
                self.desired_flow += 1
                self.flow += 1
                if self.inflow.get(p.id_node) == None:
                    self.inflow[p.id_node] = dict()
                self.inflow[p.id_node][bts] = (uniqid, target)
                
                msg = bytearray([FlowProtocol.FLOW_RESPONSE])
                print("accepted flow ", bts)
                msg += bts
                msg += self.desired_flow.to_bytes(8, byteorder="big", signed=True)
                msg += target
                msg += struct.pack(">f", cst)
                loop.create_task(self._lower_sendto(msg, addr))

        
        elif data[0] == FlowProtocol.FLOW_RESPONSE:
            print("flow response received")
            if self.requested_flows == None or not isinstance(self.requested_flows, RequestForFlow):
                # CANCEL THAT FLOW
                return
            bts = data[1:5]
            desired_flow = int.from_bytes(data[5:13], byteorder="big", signed=True)
            target = data[13:45]
            cst = struct.unpack(">f", data[45:])[0]
            if self.requested_flows.uniqueid != bts or self.requested_flows.target !=target:
                # cancel flow
                return
            self.requested_flows.to.desired_flow = desired_flow
            if self.requested_flows.cost == cst:
                self.desired_flow -= 1
                
                self.targets[target] = min(self.targets[target] if self.targets.get(target) != None else float("inf"), cst + self.next[p.id_node].costto)
                uniqid = None
  
                if uniqid == None:
                    # uniqid = urandom(4)
                
                
                    # while uniqid in self.uniqueids:
                    #     uniqid = urandom(4)
                    
                    # self.uniqueids.append(uniqid)
                    self.outstanding_outflow[bts] = (target, cst + self.next[p.id_node].costto)
                    minc = float("inf")
                    for k,v in self.outstanding_outflow.items():
                        if v[0] == target:
                            if minc > v[1]:
                                minc = v[1]
                    msg = bytearray([FlowProtocol.CHANGE])
                    msg += self.desired_flow.to_bytes(8, byteorder="big", signed=True)
                    msg += target
                    msg += struct.pack(">f", minc)
                    print("broadcasting...")
                    loop = asyncio.get_event_loop()
                    loop.create_task(self.broadcast(msg))

                    self.outflow[bts] = (p.id_node, target, cst + self.next[p.id_node].costto)

                    msg = bytearray([FlowProtocol.QUERY_FLOWS])
                    for _, fp in self.next.items():
                        
                        cstto = dict()
                        for k, v in self.outflow.items():
                            if v[0] == fp.p.id_node:
                                if cstto.get(v[1]) == None:
                                    cstto[v[1]] = (1, fp.costto)
                                else:
                                    # print(cstto[v[1]], fp.costto)
                                    cstto[v[1]] = (cstto[v[1]][0] + 1, fp.costto)
                        for k,v in cstto.items():
                            msg += fp.p.id_node
                            msg += k
                            msg += v[0].to_bytes(1, byteorder ="big")
                            msg += struct.pack(">f", v[1])
                        msg += fp.p.id_node
                        msg += bytes(bytearray([int.from_bytes(b'\x00', byteorder="big") for _ in range(32)]))
                        msg += int(0).to_bytes(1, byteorder ="big")
                        msg += struct.pack(">f", fp.costto)
                    # msg += "next_best"
                    
                    # broadcast change
                    print("broadcasting... query flows")
                    loop = asyncio.get_event_loop()
                    loop.create_task(self.broadcast(msg))
                
                
            else:
                self.requested_flows.to.dist_to_targ[target] = cst
                self.requested_flows.to.updatemin()
                print("setting target",self.requested_flows.to.dist_to_targ[target])
            print("setting to none!")
            self.requested_flows = None
        elif data[0] == FlowProtocol.CHANGE:
            desired_flow = int.from_bytes(data[1:9], byteorder="big", signed=True)
            target = data[9:41]
            cst = struct.unpack(">f", data[41:])[0]
            if self.next.get(p.id_node) != None:
                self.next.get(p.id_node).desired_flow = desired_flow
                self.next.get(p.id_node).dist_to_targ[target] = cst
                self.next.get(p.id_node).updatemin()
            elif self.prev.get(p.id_node) != None:
                self.prev.get(p.id_node).desired_flow = desired_flow
                self.prev.get(p.id_node).dist_to_targ[target] = cst
                self.prev.get(p.id_node).updatemin()
        elif data[0] == FlowProtocol.QUERY_FLOWS:
            if self.same.get(p.id_node) == None:
                return
            smp = self.same[p.id_node]
            i = 1
            smp.flows = dict()
            while i < len(data):
                to = data[i:i+32]
                i += 32
                target = data[i:i+32]
                i += 32
                flw = data[i]
                i+=1
                cstto = struct.unpack(">f",data[i:i+4])[0]
                i+=4
                smp.flows[(to,target)] = (flw,cstto)

        # elif data[0] == FlowProtocol.PUSH_BACK_FLOW:
        #     bts = data[1:5]
        #     target = data[5:37]
        #     if self.outflow.get(bts) == None or self.next[self.outflow.get(bts)[0]].p.addr != addr:
        #         return
        #     infl = self.map.get(bts)
        #     self.desired_flow += 1
        #     if infl == None:
        #         del self.outstanding_outflow[bts]
        #     else:
        #         _, trgt = self.inflow[infl[1]][infl[0]]
        #         assert target == trgt
        #         nwflw = None
        #         mn = float("inf")
        #         for k,v in self.outstanding_outflow.items():
        #             if v[0] == target and v[1] < mn:
        #                 mn = v[1]
        #                 nwfl = k
        #         if nwflw == None:
        #             self.outstanding_inflow[(infl[1],infl[0])] = target
        #             del self.inflow[infl[1]][infl[0]]
        #         else:
        #             self.inflow[infl[1]][infl[0]] = (nwflw, target)
        #             self.map[nwflw] = (bts, infl[1])
        #             del self.map[bts]
        #             trgt, cost = self.outstanding_outflow[nwflw]
        #             # notify previous of changed cost:
        #             self.desired_flow -= 1
        #             del self.outstanding_outflow[nwflw]

        
        elif data[0] == FlowProtocol.PROPOSE_CHANGE:
            if self.requested_flows != None:
                if not isinstance(self.requested_flows, RequestForChange):
                    return
            loop = asyncio.get_event_loop()
            target = data[1:33]
            curr_flow = data[33:65]
            new_flow = data[65:97]
            new_unique = data[97:101]
            cost_new = struct.unpack(">f", data[109:113])[0]
            if self.requested_flows != None:          
                if self.requested_flows.smp.p.id_node != p.id_node:
                    loop.create_task(self.reject_switch(new_unique, addr))
                    return
                if self.requested_flows.new_next == new_flow and self.requested_flows.curr_next == curr_flow and self.requested_flows.target == target:
                    print("ACCEPT")
                    msg = bytearray([FlowProtocol.RESPOND_CHANGE])
                    msg += int(0).to_bytes(1, byteorder="big")
                    msg += self.requested_flows.my_flow
                    msg += struct.pack(">f",self.outflow[self.requested_flows.my_flow][2] - self.next[self.requested_flows.curr_next].costto)
                    loop.create_task(self._lower_sendto(msg, addr))
                    return
                loop.create_task(self.reject_switch(new_unique, addr))
                return
            
            # flt_me_now = struct.unpack(">f", data[97:101])
            flt_them_now = struct.unpack(">f", data[101:105])[0]
            # flt_me_then = struct.unpack(">f", data[105:109])
            flt_them_then = struct.unpack(">f", data[105:109])[0]
            
            if flt_them_then + self.costmap(self.peer.pub_key, self.next[new_flow].p.pub_key) < flt_them_now + self.costmap(self.peer.pub_key, self.next[curr_flow].p.pub_key):
                
                tellthem = None
                tellthem_cost = 0
                for k, v in self.outflow.items():
                    if v[0] == curr_flow and v[1] == target:
                        tellthem = k
                        tellthem_cost = v[2] - self.next[v[0]].costto
                        break
                if tellthem == None:
                    loop.create_task(self.reject_switch(new_unique, addr))
                    return
                print("accepting change",cost_new)
                msg = bytearray([FlowProtocol.RESPOND_CHANGE])
                msg += int(0).to_bytes(1, byteorder="big")
                msg += tellthem
                msg += struct.pack(">f",tellthem_cost)
                loop.create_task(self._lower_sendto(msg, addr))
                loop.create_task(self.perform_switch(tellthem,new_unique,cost_new + self.costmap(self.peer.pub_key, self.next[new_flow].p.pub_key), new_flow, p.id_node))
                return
                
            
            loop.create_task(self.reject_switch(new_unique, addr))
            return
        elif data[0] == FlowProtocol.RESPOND_CHANGE:
            
            if self.requested_flows != None and not isinstance(self.requested_flows, RequestForChange):
                    return
            if self.requested_flows == None:
                return
            if data[1] == 1:
                self.requested_flows = None
                return
            print("They accepted our proposal")
            new_flow = data[2:6]
            new_cost = struct.unpack(">f",data[6:10])[0]
            loop = asyncio.get_event_loop()
            loop.create_task(self.perform_switch(self.requested_flows.my_flow,new_flow,new_cost + self.costmap(self.peer.pub_key, self.next[self.requested_flows.new_next].p.pub_key) ,self.requested_flows.new_next, p.id_node))
            
            return
        elif data[0] == FlowProtocol.NOTIFY_CHANGE_IN_COST:
            if data[1] == 0: # back
                
                print("our cost to someone was changed")
                curr_id = data[2:6]
                if self.outflow.get(curr_id) == None:
                    # cancel flow
                    return
                loop = asyncio.get_event_loop()
                nxt, target, cost = self.outflow[curr_id]
                self.outflow[curr_id] = (nxt, target, struct.unpack(">f", data[10:14])[0] + self.costmap(self.peer.pub_key, p.pub_key))
                if self.outstanding_outflow.get(curr_id) == None:
                    
                    prev = self.prev[self.map[curr_id][1]]
                    loop.create_task(self.notify_change_in_cost(prev, self.map[curr_id][0], self.outflow[curr_id][2],0))
                else:
                    self.outstanding_outflow[curr_id] = (target, struct.unpack(">f", data[10:14])[0] + self.costmap(self.peer.pub_key, p.pub_key))
                    self.targets[target] = float("inf")
                    minc = float("inf")
                    for idx, rets in self.outstanding_outflow.items():
                        if target == rets[0] and rets[1] < minc:
                            minc = rets[1]
                    self.targets[target] = minc
                # else:
                #     return
                
            else:
                # forward
                print("forward")
                print(self.inflow)
                curr_id = data[2:6]
                new_id = data[6:10]
                new_parent = data[10:42]
                # self.inflow: dict[bytes, dict[bytes,tuple[bytes, bytes]]] = dict() # previous peer -> unique id -> unique id, target
                idx, target = self.inflow[self.get_al(addr).id_node][curr_id]
                del self.inflow[self.get_al(addr).id_node][curr_id]
                if self.inflow.get(new_parent) == None:
                    self.inflow[new_parent] = dict()
                self.inflow[new_parent][new_id] = (idx,target)
                del self.map[idx]
                self.map[idx] = (new_id, new_parent)
        # return super().process_datagram(addr, data)
    async def reject_switch(self,curr_flow, addr):
        msg = bytearray([FlowProtocol.RESPOND_CHANGE])
        msg += int(1).to_bytes(1, byteorder="big")
        msg += curr_flow
        loop = asyncio.get_event_loop()
        loop.create_task(self._lower_sendto(msg, addr))
        return
    async def notify_change_in_cost(self, fp: FlowPeer, flow_id, cost, direction, new_id = None, new_parent = None):
        msg = bytearray([FlowProtocol.NOTIFY_CHANGE_IN_COST])
        msg += int(direction).to_bytes(1, byteorder="big")
        msg += flow_id
        msg += flow_id if new_id == None else new_id
        if new_parent != None:
            print(flow_id, "to", flow_id if new_id == None else new_id)
            msg += new_parent
        msg += struct.pack(">f", cost)
        loop = asyncio.get_event_loop()
        loop.create_task(self._lower_sendto(msg, fp.p.addr))
    async def perform_switch(self, curr_flow, new_flow, cost_new, new_next, switched_with):
        
        nxt, trgt, cost  = self.outflow[curr_flow]
        loop = asyncio.get_event_loop()
        flag = True
        if self.outstanding_outflow.get(curr_flow) != None:
            self.outstanding_outflow[new_flow] = (trgt, cost_new)
            msg = bytearray([FlowProtocol.CHANGE])
            msg += self.desired_flow.to_bytes(8, byteorder="big", signed=True)
            msg += self.requested_flows.target
            msg += struct.pack(">f", cost_new)
            loop.create_task(self.broadcast(msg))
            flag = False
            del self.outstanding_outflow[curr_flow]
        self.outflow[new_flow] = (new_next, trgt, cost_new)
        del self.outflow[curr_flow]
        
        msg = bytearray([FlowProtocol.QUERY_FLOWS])
        for _, fp in self.next.items():
                        
            cstto = dict()
            for k, v in self.outflow.items():
                if v[0] == fp.p.id_node:
                    if cstto.get(v[1]) == None:
                        cstto[v[1]] = (1, fp.costto)
                    else:
                        cstto[v[1]] = (cstto[v[1]][0] + 1, fp.costto)
            for k,v in cstto.items():
                msg += fp.p.id_node
                msg += k
                msg += v[0].to_bytes(1, byteorder ="big")
                msg += struct.pack(">f", v[1])
            msg += fp.p.id_node
            msg += bytes(bytearray([int.from_bytes(b'\x00', byteorder="big") for _ in range(32)]))
            msg += int(0).to_bytes(1, byteorder ="big")
            msg += struct.pack(">f", fp.costto)
                   
                    
                    
        print("broadcasting... query flows")
                    
        loop.create_task(self.broadcast(msg))
        if flag and self.map.get(curr_flow) != None:
            their, them = self.map[curr_flow]
            del self.map[curr_flow]
            self.map[new_flow] = (their, them)
            await self.notify_change_in_cost(self.prev[them],their,cost_new,0)
        await self.notify_change_in_cost(self.next[nxt],curr_flow,cost_new,1,new_flow, switched_with)
        if self.requested_flows != None and isinstance(self.requested_flows, RequestForChange):
            self.requested_flows = None
        return
    # async def push_back_flow(self, fp: FlowPeer, uniqid_their, uniqid_ours, target):
    #     msg = bytearray([FlowProtocol.PUSH_BACK_FLOW])
    #     msg += uniqid_their
    #     msg += target
    #     self.flow -= 1
    #     del self.inflow[fp.p.id_node][uniqid_their]
    #     if self.outstanding_inflow.get((fp.p.id_node, uniqid_their)) == None:
    #         self.outstanding_outflow[uniqid_ours] = (self.outflow[uniqid_ours][1], self.outflow[uniqid_ours][2])
    #     else:
    #         del self.outstanding_inflow[(fp.p.id_node, uniqid_their)]
    #         self.uniqueids.remove(uniqid_ours)
    #     loop = asyncio.get_running_loop()
    #     loop.create_task(self._lower_sendto(msg,fp.p.addr))
    async def request_flow(self, fp: FlowPeer, cost: float, to: bytes):
        print("requesting flow from",fp.p.pub_key)
        uniqid = None
        for idx, trgtcst in self.outstanding_inflow.items():
            if to == trgtcst:
                uniqid = idx
                break
        if uniqid == None:
            uniqid = urandom(4)
            while uniqid in self.uniqueids:
                uniqid = urandom(4)

            self.uniqueids.append(uniqid)
        self.requested_flows = RequestForFlow(uniqid, fp, cost, to)
        
        msg = bytearray([FlowProtocol.FLOW_REQUEST])
        msg += uniqid
        msg += to
        msg += struct.pack(">f", cost)
        print("sending to next peer", uniqid)
        await self._lower_sendto(msg,fp.p.addr)

    async def request_change(self, requested_change: RequestForChange):
        print("requesting change from")
        msg = bytearray([FlowProtocol.PROPOSE_CHANGE])
        smp = requested_change.smp
        target= requested_change.target
        nxt_pcurr = requested_change.new_next
        nxt_pnew = requested_change.curr_next
        flt_me_now = requested_change.curr_cost

        flt_me_then = requested_change.new_cost
        cost_to_next = self.outflow[requested_change.my_flow][2] - self.next[nxt_pnew].costto
        print("the cost the next guy offers at is", cost_to_next)
        msg += target
        msg += nxt_pcurr
        msg += nxt_pnew
        msg += requested_change.my_flow
        msg += struct.pack(">f", flt_me_now)
        msg += struct.pack(">f", flt_me_then)
        msg += struct.pack(">f", cost_to_next)
        await self._lower_sendto(msg, smp.p.addr)
    async def look_for_change(self):
                    print("trying to change flows")
                    randcc = random.sample(list(self.same.values()), k=1)[0]
                    bestminimasation = 0
                    repalcemenet_flow = None
                    to_from = (None, None)
                    proof = (None, None)
                    for k, v in randcc.flows.items():
                        for k1, v1 in self.outflow.items():
                                if randcc.flows.get((v1[0],v1[1])) == None and randcc.flows.get((v1[0],bytes(bytearray([int.from_bytes(b'\x00', byteorder="big") for _ in range(32)])))) == None:
                                    print("they dont know peer", randcc.flows)
                                    continue
                                # they know this peer for that target

                                ret = randcc.flows.get((v1[0],v1[1]))
                                if ret == None:
                                    ret = randcc.flows.get((v1[0],bytes(bytearray([int.from_bytes(b'\x00', byteorder="big") for _ in range(32)]))))
                                flw, cstn = ret
                                
                                if self.next.get(k[0]) == None:
                                    print("I dont know peer")
                                    continue
                                # i know this peer
                                
                                mcst = self.costmap(self.peer.pub_key, self.next[k[0]].p.pub_key)
                                currcost = self.costmap(self.peer.pub_key, self.next[v1[0]].p.pub_key)
                                # for k2, v2 in self.outflow.items():
                                #     if v2[0] == k[0] and v2[1] == k:
                                #         mflwid = k2
                                #         mflw += 1
                                #         break
                                print(v[1], currcost , cstn , mcst)
                                if v[1] + currcost - (cstn + mcst) > bestminimasation:
                                    bestminimasation = v[1] + currcost - (cstn + mcst) 
                                    to_from = (k, (v1[0], v1[1]))
                                    proof = (( v[1], currcost), (cstn, mcst))
                                    repalcemenet_flow = k1
                                    
                    print("trying to change flows", bestminimasation)
                    if bestminimasation != 0:
                         
                        self.requested_flows = RequestForChange(randcc, repalcemenet_flow,to_from[1][0],to_from[0][0],to_from[1][1], proof[0][1], proof[1][1])
                        
                        await self.request_change(self.requested_flows)
                        # request change
    async def periodic(self):
        print(self.desired_flow)
        if self.requested_flows == None:
            if True:
                cost = 0
                flow = len(self.outflow.items())
                for k,v in self.outflow.items():
                    cost+= v[2]
                self.iterationsss.append((flow,cost))
                print(f"sending {flow} at cost {cost}")
                print(self.iterationsss)
            if len(self.outstanding_inflow.items()) > 0:
                print("I HAVE OUTSTANDING INFLOW")
                return
            elif self.desired_flow >= 0 and self.flow < self.capacity:
                mx = float("inf")
                chc = None
                nxstg = True
                for _, fp in self.next.items():
                    if fp.mincostto + fp.costto <= mx and fp.desired_flow < 0:
                        mx = fp.mincostto + fp.costto
                        chc = fp
                # for pid, fp in self.prev.items():
                #     if fp.mincostto + fp.costto <= mx and self.inflow.get(pid) != None and fp.desired_flow < 0:
                #         # we should return flow to them
                #         nxstg = False
                #         mx = fp.mincostto + fp.costto
                #         chc = fp
                if mx != float("inf") and nxstg and chc.mincostto != float("inf"):
                        await self.request_flow(chc, chc.mincostto, chc.mincostis)
                
                elif len(list(self.same.values())) > 0:
                    print("wont be next stage for some reason")
                    await self.look_for_change()
            elif len(list(self.same.values())) > 0:
                print(self.desired_flow)
                await self.look_for_change()        
                                
                                
                            
        else:
            print("outstanding request")
            print(self.requested_flows)
            # can request flow   
        loop = asyncio.get_event_loop()
        self.refresh_loop = loop.call_later(2, self._periodic)
        

    def _periodic(self):
        loop = asyncio.get_running_loop()
        loop.create_task(self.periodic())
    @bindfrom("connected_callback")
    def peer_connected(self, p: Peer):
        print("Introducing to", p.addr)
        msg = bytearray([FlowProtocol.INTRODUCTION])
        msg += self.desired_flow.to_bytes(8, byteorder="big", signed=True)
        msg += self.stage.to_bytes(8, byteorder="big")
        loop = asyncio.get_running_loop()
        loop.create_task(self._lower_sendto(msg, p.addr))
        

    
        