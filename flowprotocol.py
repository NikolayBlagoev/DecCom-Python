import asyncio
import random
from deccom.protocols.peerdiscovery.fixedpeers import FixedPeers
from deccom.protocols.wrappers import *
from deccom.utils.common import ternary_comparison
from typing import Any, Callable, List
from sys import maxsize
from deccom.peers.peer import Peer
import struct
from os import urandom
from deccom.protocols.abstractprotocol import AbstractProtocol
from flownode import *
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
    PROPOSE_REDIRECT = int.from_bytes(b'\xd8', byteorder="big")
    RESPOND_REDIRECT = int.from_bytes(b'\xd9', byteorder="big")
    def __init__(self, stage: int, max_stage: int, capacity: int, flow: int, minflow: int, maxflow: int, costmap, submodule=None, callback: Callable[[tuple[str, int], bytes], None] = ...):
        super().__init__(submodule, callback)
        
        self.iteration = 0
        
        self.iterationsss = []
        
        
        self.flow_node = FlowNode(flow,minflow,maxflow,capacity,stage)
        self.stage = stage
        self.max_stage = max_stage

        self.requested_flows: tuple[bytes,FlowPeer,float, bytes] = None
        self.costmap = costmap
        self.attempts = 0
        self.T = 1.7
        self.postpone = 0
    async def start(self, p : Peer):
        await super().start(p)
        if self.stage == self.max_stage:
            self.flow_node.targets[self.peer.id_node] = 0
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
                self.flow_node.prev[p.id_node] = fp
            elif stage == self.stage + 1:
                if stage == self.max_stage:
                    fp = FlowPeer(p,stage,int.from_bytes(data[1:9], byteorder="big", signed=True), self.costmap(self.peer.pub_key, p.pub_key))
                    fp.mincostto = 0
                    fp.dist_to_targ[p.id_node] = 0
                    fp.mincostis = p.id_node
                    self.flow_node.targets[p.id_node] = self.costmap(self.peer.pub_key, p.pub_key)

                    self.flow_node.next[p.id_node] = fp
                else:
                    fp = FlowPeer(p, stage, desired_flow, self.costmap(self.peer.pub_key, p.pub_key))
                    self.flow_node.next[p.id_node] = fp
            elif stage == self.stage:
                self.flow_node.same[p.id_node] = SamePeer(p)
        
        elif data[0] == FlowProtocol.FLOW_REQUEST:
            bts = data[1:5]
            target = data[5:37]
            cst = struct.unpack(">f", data[37:])[0]
            loop = asyncio.get_running_loop()
            if self.flow_node.desired_flow >= 0 or self.flow_node.flow>= self.flow_node.capacity or self.flow_node.targets.get(target) == None:
                print("too much, cant accept, or dont know")
                msg = bytearray([FlowProtocol.FLOW_RESPONSE])
                msg += bts
                msg += self.flow_node.desired_flow.to_bytes(8, byteorder="big", signed=True)
                msg += target
                msg += struct.pack(">f", float("inf"))
                loop.create_task(self._lower_sendto(msg, addr))
                return
            elif self.flow_node.targets.get(target) != cst:
                print("wrong cost", cst, self.flow_node.targets.get(target))
                msg = bytearray([FlowProtocol.FLOW_RESPONSE])
                msg += bts
                msg += self.flow_node.desired_flow.to_bytes(8, byteorder="big", signed=True)
                msg += target
                msg += struct.pack(">f", self.flow_node.targets.get(target))
                loop.create_task(self._lower_sendto(msg, addr))
                return
            else:
                self.flow_node.add_inflow(p.id_node, bts, target)
                   
                
                self.flow_node.desired_flow += 1
                self.attempts = 0
                msg = bytearray([FlowProtocol.FLOW_RESPONSE])
                print("accepted flow ", bts)
                msg += bts
                msg += self.flow_node.desired_flow.to_bytes(8, byteorder="big", signed=True)
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
                self.flow_node.desired_flow -= 1
 
                self.flow_node.add_outflow(bts,p.id_node, target, cst, self.flow_node.next[p.id_node].costto)
                minc = float("inf")
                for k,v in self.flow_node.outstanding_outflow.items():
                        if v[0] == target:
                            if minc > v[1]:
                                minc = v[1]
                msg = bytearray([FlowProtocol.CHANGE])
                msg += self.flow_node.desired_flow.to_bytes(8, byteorder="big", signed=True)
                msg += target
                msg += struct.pack(">f", minc)
                print("broadcasting...")
                loop = asyncio.get_event_loop()
                loop.create_task(self.broadcast(msg))
                self.broadcast_query()
    
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
            if self.flow_node.next.get(p.id_node) != None:
                self.flow_node.next.get(p.id_node).desired_flow = desired_flow
                self.flow_node.next.get(p.id_node).dist_to_targ[target] = cst
                self.flow_node.next.get(p.id_node).updatemin()
            elif self.flow_node.prev.get(p.id_node) != None:
                self.flow_node.prev.get(p.id_node).desired_flow = desired_flow
                self.flow_node.prev.get(p.id_node).dist_to_targ[target] = cst
                self.flow_node.prev.get(p.id_node).updatemin()
        elif data[0] == FlowProtocol.QUERY_FLOWS:
            if self.flow_node.same.get(p.id_node) == None:
                return
            smp = self.flow_node.same[p.id_node]
            i = 1
            smp.outflows = dict()
            smp.inflows = dict()
            smp.next = dict()
            smp.prev = dict()
            smp.total_flows = []
            sz_next = int.from_bytes(data[i:i+4], byteorder="big")
            i+=4
            for _ in range(sz_next):
                smp.next[data[i:i+32]] = struct.unpack(">f", data[i+32:i+36])[0]
                i+=36
            sz_prev= int.from_bytes(data[i:i+4], byteorder="big")
            i+=4
            for _ in range(sz_prev):
                smp.prev[data[i:i+32]] = struct.unpack(">f", data[i+32:i+36])[0]
                i+=36
            flows = int.from_bytes(data[i:i+4], byteorder="big")
            i+=4
            for _ in range(flows):
                prv = data[i:i+32]
                i+=32
                nxt = data[i:i+32]
                i+=32
                target = data[i:i+32]
                i+=32
                if  smp.inflows.get((prv, target)) == None:
                    smp.inflows[(prv, target)] = 1
                else:
                    smp.inflows[(prv, target)] = smp.inflows[(prv, target)] + 1

                if  smp.outflows.get((nxt, target)) == None:
                    smp.outflows[(nxt, target)] = 1
                else:
                    smp.outflows[(nxt, target)] = smp.outflows[(nxt, target)] + 1
                smp.total_flows.append((prv,nxt, target))

        elif data[0] == FlowProtocol.PUSH_BACK_FLOW:
            print("they pushing back!")
            # exit()
            bts = data[1:5]
            target = data[5:37]
            if self.flow_node.outflow.get(bts) == None or self.flow_node.next[self.flow_node.outflow.get(bts)[0]].p.addr != addr:
                print("dont got this batch", bts, self.flow_node.outflow)
                return
            ret = self.flow_node.remove_outflow(bts)
            if ret != None:
                loop = asyncio.get_event_loop()
                loop.create_task(self.notify_change_in_cost(self.flow_node.prev[ret[0]],ret[1],cost,0))
                self.flow_node.desired_flow -= 1

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
            if self.flow_node.next.get(new_flow) == None:
                loop.create_task(self.reject_switch(new_unique, addr))
                return
            if self.requested_flows != None:          
                if self.requested_flows.smp.p.id_node != p.id_node:
                    loop.create_task(self.reject_switch(new_unique, addr))
                    return
                if self.requested_flows.new_next == new_flow and self.requested_flows.curr_next == curr_flow and self.requested_flows.target == target:
                    print("ACCEPT")
                    msg = bytearray([FlowProtocol.RESPOND_CHANGE])
                    msg += int(0).to_bytes(1, byteorder="big")
                    msg += self.requested_flows.my_flow
                    msg += struct.pack(">f",self.flow_node.outflow[self.requested_flows.my_flow][2] - self.flow_node.next[self.requested_flows.curr_next].costto)
                    loop.create_task(self._lower_sendto(msg, addr))
                    return
                loop.create_task(self.reject_switch(new_unique, addr))
                return
            
            # flt_me_now = struct.unpack(">f", data[97:101])
            flt_them_now = struct.unpack(">f", data[101:105])[0]
            # flt_me_then = struct.unpack(">f", data[105:109])
            flt_them_then = struct.unpack(">f", data[105:109])[0]
            
            if flt_them_then + self.costmap(self.peer.pub_key, self.flow_node.next[new_flow].p.pub_key) < self.T*(flt_them_now + self.costmap(self.peer.pub_key, self.flow_node.next[curr_flow].p.pub_key)):
                
                tellthem = None
                tellthem_cost = 0
                for k, v in self.flow_node.outflow.items():
                    if v[0] == curr_flow and v[1] == target:
                        tellthem = k
                        tellthem_cost = v[2] - self.flow_node.next[v[0]].costto
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
                loop.create_task(self.perform_switch(tellthem,new_unique,cost_new + self.costmap(self.peer.pub_key, self.flow_node.next[new_flow].p.pub_key), new_flow, p.id_node))
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
            self.attempts = 0
            print("They accepted our proposal")
            new_flow = data[2:6]
            new_cost = struct.unpack(">f",data[6:10])[0]
            loop = asyncio.get_event_loop()
            loop.create_task(self.perform_switch(self.requested_flows.my_flow,new_flow,new_cost + self.costmap(self.peer.pub_key, self.flow_node.next[self.requested_flows.new_next].p.pub_key) ,self.requested_flows.new_next, p.id_node))
            
            return
        elif data[0] == FlowProtocol.NOTIFY_CHANGE_IN_COST:
            if data[1] == 0: # back
                
                print("our cost to someone was changed")
                curr_id = data[2:6]
                if self.flow_node.outflow.get(curr_id) == None:
                    # cancel flow
                    return
                loop = asyncio.get_event_loop()
                nxt, target, cost = self.flow_node.outflow[curr_id]
                self.flow_node.outflow[curr_id] = (nxt, target, struct.unpack(">f", data[10:14])[0] + self.costmap(self.peer.pub_key, p.pub_key))
                if self.flow_node.outstanding_outflow.get(curr_id) == None:
                    
                    prev = self.flow_node.prev[self.flow_node.map[curr_id][1]]
                    loop.create_task(self.notify_change_in_cost(prev, self.flow_node.map[curr_id][0], self.flow_node.outflow[curr_id][2],0))
                else:
                    self.flow_node.outstanding_outflow[curr_id] = (target, struct.unpack(">f", data[10:14])[0] + self.costmap(self.peer.pub_key, p.pub_key))
                    self.flow_node.targets[target] = float("inf")
                    minc = float("inf")
                    for idx, rets in self.flow_node.outstanding_outflow.items():
                        if target == rets[0] and rets[1] < minc:
                            minc = rets[1]
                    self.flow_node.targets[target] = minc
                # else:
                #     return
                
            else:
                # forward
                
                curr_id = data[2:6]
                new_id = curr_id
                new_parent = data[10:42]
                print("forward",curr_id,"becomes", new_id, "with parent", self.flow_node.prev[new_parent].p.pub_key, "based on",p.pub_key)
                print(self.flow_node.inflow)
                # self.inflow: dict[bytes, dict[bytes,tuple[bytes, bytes]]] = dict() # previous peer -> unique id -> unique id, target
                idx, target = self.flow_node.inflow[p.id_node][curr_id]
                del self.flow_node.inflow[p.id_node][curr_id]
                if self.flow_node.inflow.get(new_parent) == None:
                    self.flow_node.inflow[new_parent] = dict()
                self.flow_node.inflow[new_parent][new_id] = (idx,target)
                del self.flow_node.map[idx]
                self.flow_node.map[idx] = (new_id, new_parent)
        elif data[0] == FlowProtocol.PROPOSE_REDIRECT:
            nxtpr = data[1:33]
            print("redirect proposal!")
            prvpr = data[33:65]
            trgt = data[65:97]
            if self.requested_flows != None:
                if p.id_node < self.peer.id_node:
                    self.attempts = 2
                print("rejecting redirect")
                self.reject_redirect(nxtpr, prvpr, trgt, addr)
                return
            if self.flow_node.prev.get(prvpr) == None:
                print("dont know previous")
                print(prvpr)
                print(self.flow_node.prev)
                self.reject_redirect(nxtpr, prvpr, trgt, addr)
                return
            if self.flow_node.next.get(nxtpr) == None:
                print("dont know next")
                self.reject_redirect(nxtpr, prvpr, trgt, addr)
                return
            proof = struct.unpack(">f", data[97:101])[0]
            if proof >= self.T * (self.flow_node.prev[prvpr].costto + self.flow_node.next[nxtpr].costto):
                self.reject_redirect(nxtpr, prvpr, trgt, addr)
                print("INCORRECT PROOF",proof,self.flow_node.prev[prvpr].costto + self.flow_node.next[nxtpr].costto)
                return
            if self.flow_node.inflow.get(prvpr) == None:
                self.reject_redirect(nxtpr, prvpr, trgt, addr)
                print("NO INFLOW FROMTHAT PEER")
                return
            for k,v in self.flow_node.inflow[prvpr].items():
                if v[1] == trgt:
                    if self.flow_node.outflow.get(v[0]) == None:
                        continue
                    nxt, _, cost = self.flow_node.outflow[v[0]]
                    if nxt != nxtpr:
                        continue
                    
                    
                    # send my flow
                    print("APPROVED REDIRECT! they want my flow", )
                    msg = bytearray([FlowProtocol.RESPOND_REDIRECT])
                    msg += nxtpr
                    msg += prvpr
                    msg += trgt
                    msg += v[0]
                    msg += struct.pack(">f", cost - self.flow_node.next[nxtpr].costto)
                    print("the peer serves at", cost - self.flow_node.next[nxtpr].costto)
                    loop = asyncio.get_event_loop()
                    loop.create_task(self._lower_sendto(msg, addr))
                    del self.flow_node.outflow[v[0]]
                    # inform next
                    loop.create_task(self.notify_change_in_cost(self.flow_node.next[nxt],v[0],0,1, new_parent=p.id_node))
                    # push back flow
                    msg = bytearray([FlowProtocol.PUSH_BACK_FLOW])
                    msg += k
                    msg += trgt
                    self.flow_node.flow-= 1
                    
                    del self.flow_node.inflow[self.flow_node.prev[prvpr].p.id_node][k]
                    del self.flow_node.map[v[0]]
                    self.flow_node.uniqueids.remove(v[0])
                    loop = asyncio.get_running_loop()
                    loop.create_task(self._lower_sendto(msg,self.flow_node.prev[prvpr].p.addr))
                    
                    return
            print("dont have such flow :/ from",self.flow_node.prev[prvpr].p.pub_key, " to ",self.flow_node.next[nxtpr].p.pub_key )
            for k,v in self.flow_node.outflow.items():
                print("sending to ",self.flow_node.next[v[0]].p.pub_key,k)
            for k,v in self.flow_node.inflow.items():
                for a,_ in v.items():
                    print("receiving from ",self.flow_node.prev[k].p.pub_key,a)
            for k, v in self.flow_node.outstanding_inflow.items():
                print("outstanding ",k)
            for k, v in self.flow_node.outstanding_outflow.items():
                print("outstanding ",k)
            self.reject_redirect(nxtpr, prvpr, trgt, addr)
            return
        elif data[0] == FlowProtocol.RESPOND_REDIRECT:
            if self.requested_flows != None and not isinstance(self.requested_flows, RequestForRedirect):
                return
            nxtpr = data[1:33]
            prvpr = data[33:65]
            trgt = data[65:97]
            if self.requested_flows.curr_pev != prvpr or self.requested_flows.curr_next != nxtpr or self.requested_flows.target != trgt:
                print("wrong request")
                return
            if len(data) < 98:
                print("we were rejected...")
                self.requested_flows = None
                return
            new_id = data[97:101]
            new_cost = struct.unpack(">f",data[101:105])[0]
            print("change was approved! I will message", self.flow_node.next[nxtpr].p.pub_key,"at new cost",new_cost + self.flow_node.next[nxtpr].costto,self.flow_node.desired_flow)
            
            self.flow_node.outflow[new_id] = (nxtpr, trgt, new_cost + self.flow_node.next[nxtpr].costto)
            self.flow_node.outstanding_outflow[new_id] = (trgt, new_cost + self.flow_node.next[nxtpr].costto)
            self.flow_node.desired_flow -= 1
            self.flow_node.uniqueids.append(new_id)
            self.T = max(self.T*0.99,1)
            minc = float("inf")
            for k,v in self.flow_node.outstanding_outflow.items():
                if v[0] == trgt:
                    if minc > v[1]:
                        minc = v[1]
            self.flow_node.targets[trgt] = min(self.flow_node.targets[trgt] if self.flow_node.targets.get(trgt) != None else float("inf"), new_cost + self.flow_node.next[nxtpr].costto)
            msg = bytearray([FlowProtocol.CHANGE])
            msg += self.flow_node.desired_flow.to_bytes(8, byteorder="big", signed=True)
            msg += trgt
            msg += struct.pack(">f", self.flow_node.targets[trgt])
            loop = asyncio.get_event_loop()
            loop.create_task(self.broadcast(msg))

            # msg = bytearray([FlowProtocol.CHANGE])
            #         msg += self.flow_node.desired_flow.to_bytes(8, byteorder="big", signed=True)
            #         msg += target
            #         msg += struct.pack(">f", minc)
            #         print("broadcasting...")
            #         loop = asyncio.get_event_loop()
            #         loop.create_task(self.broadcast(msg))
            self.requested_flows = None
                 
        # return super().process_datagram(addr, data)
    def reject_redirect(self, nxtpr, prvpr, trgt, addr):
        msg = bytearray([FlowProtocol.RESPOND_REDIRECT])
        msg += nxtpr
        msg += prvpr
        msg += trgt
        loop = asyncio.get_event_loop()
        loop.create_task(self._lower_sendto(msg, addr))
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
        print("performing switch", curr_flow, "to",new_flow)
        self.T = max(self.T*0.99,1)
        nxt, trgt, cost  = self.flow_node.outflow[curr_flow]
        loop = asyncio.get_event_loop()
        flag = True
        if self.flow_node.outstanding_outflow.get(curr_flow) != None:
            self.flow_node.outstanding_outflow[new_flow] = (trgt, cost_new)
            msg = bytearray([FlowProtocol.CHANGE])
            msg += self.flow_node.desired_flow.to_bytes(8, byteorder="big", signed=True)
            msg += trgt
            msg += struct.pack(">f", cost_new)
            loop.create_task(self.broadcast(msg))
            flag = False
            del self.flow_node.outstanding_outflow[curr_flow]
        self.flow_node.outflow[new_flow] = (new_next, trgt, cost_new)
        del self.flow_node.outflow[curr_flow]
        self.flow_node.uniqueids.remove(curr_flow)
        self.flow_node.uniqueids.append(new_flow)
        self.broadcast_query()
        if flag and self.flow_node.map.get(curr_flow) != None:
            their, them = self.flow_node.map[curr_flow]
            del self.flow_node.map[curr_flow]
            self.flow_node.map[new_flow] = (their, them)
            idx, trtmp = self.flow_node.inflow[them][their]
            self.flow_node.inflow[them][their] = (new_flow, trtmp)
            await self.notify_change_in_cost(self.flow_node.prev[them],their,cost_new,0)
        await self.notify_change_in_cost(self.flow_node.next[nxt],curr_flow,cost_new,1,new_flow, switched_with)
        if self.requested_flows != None and isinstance(self.requested_flows, RequestForChange):
            self.requested_flows = None
        return
    async def push_back_flow(self, fp: FlowPeer, uniqid_their, uniqid_ours, target):
        msg = bytearray([FlowProtocol.PUSH_BACK_FLOW])
        msg += uniqid_their
        msg += target
        self.flow_node.flow-= 1
        
        del self.flow_node.inflow[fp.p.id_node][uniqid_their]
        if self.flow_node.outstanding_inflow.get(uniqid_ours) == None:
            self.flow_node.outstanding_outflow[uniqid_ours] = (self.flow_node.outflow[uniqid_ours][1], self.flow_node.outflow[uniqid_ours][2])
        else:
            self.flow_node.desired_flow -= 1
            del self.flow_node.outstanding_inflow[uniqid_ours]
            self.flow_node.uniqueids.remove(uniqid_ours)
        loop = asyncio.get_running_loop()
        loop.create_task(self._lower_sendto(msg,fp.p.addr))
    async def request_flow(self, fp: FlowPeer, cost: float, to: bytes):
        print("requesting flow from",fp.p.pub_key)
        uniqid = None
        for idx, trgtcst in self.flow_node.outstanding_inflow.items():
            if to == trgtcst:
                uniqid = idx
                break
        if uniqid == None:
            uniqid = urandom(4)
            while uniqid in self.flow_node.uniqueids:
                uniqid = urandom(4)

            self.flow_node.uniqueids.append(uniqid)
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
        cost_to_next = self.flow_node.outflow[requested_change.my_flow][2] - self.flow_node.next[nxt_pnew].costto
        print("the cost the next guy offers at is", cost_to_next)
        msg += target
        msg += nxt_pcurr
        msg += nxt_pnew
        msg += requested_change.my_flow
        msg += struct.pack(">f", flt_me_now)
        msg += struct.pack(">f", flt_me_then)
        msg += struct.pack(">f", cost_to_next)
        await self._lower_sendto(msg, smp.p.addr)
    
    
    async def request_redirect(self, requested_change: RequestForRedirect):
        print("requesting redirect from",requested_change.smp.p.pub_key)
        
        smp = requested_change.smp
        target= requested_change.target
        nxtpr = requested_change.curr_next
        prvpr = requested_change.curr_pev
        proof = requested_change.proof
        msg = bytearray([FlowProtocol.PROPOSE_REDIRECT])
        msg += nxtpr
        msg+=prvpr
        msg+=target
        print("their prvpr: ", prvpr)
        msg += struct.pack(">f", proof)
        await self._lower_sendto(msg, smp.p.addr)
    async def look_for_change(self):
                    if self.postpone > 0:
                        self.postpone -= 1
                        return
                    # print("trying to change flows")
                    randcc = random.sample(list(self.flow_node.same.values()), k=1)[0]
                    bestminimasation = 0
                    repalcemenet_flow = None
                    to_from = (None, None)
                    endt = None
                    proof = (None, None)
                    flag = False
                    for k, v in randcc.outflows.items():
                        theirpeer, target = k
                        if self.flow_node.next.get(theirpeer) == None:
                            continue
                        for k1, v1 in self.flow_node.outflow.items():
                            mpr = v1[0]
                            if mpr == theirpeer:
                                continue
                            if randcc.next.get(mpr) == None:
                                continue
                            if v1[1] != target:
                                continue
                            curr_cost_me = self.flow_node.next[mpr].costto
                            curr_cost_them = randcc.next[theirpeer]
                            new_cost_me = self.flow_node.next[theirpeer].costto
                            new_cost_them = randcc.next[mpr]
                            diff = self.T*(curr_cost_me + curr_cost_them) - (new_cost_me + new_cost_them)
                            if diff > bestminimasation:
                                bestminimasation = diff
                                repalcemenet_flow = k1
                                to_from = (mpr, theirpeer)
                                endt = target
                                proof = (curr_cost_me, new_cost_me)
                    path = (None, None)
                    trgtReflow = None   
                    proofReflow = float("inf")       
                    if self.flow_node.flow< self.flow_node.capacity and self.flow_node.desired_flow >= 0:
                        print(self.flow_node.flow, self.flow_node.capacity)
                        for fl in randcc.total_flows:
                            prv, nxt, trgt = fl
                            if prv == bytes(bytearray([0 for _ in range(32)])):
                                continue
                            if self.flow_node.next.get(nxt) == None or self.flow_node.prev.get(prv) == None:
                                continue
                            curr_cost = randcc.prev[prv] 
                            
                            curr_cost += randcc.next[nxt]
                            through_me = self.flow_node.prev[prv].costto + self.flow_node.next[nxt].costto
                            if self.T*curr_cost - through_me > bestminimasation:
                                bestminimasation = self.T*curr_cost - through_me
                                flag = True
                                path = (prv, nxt)
                                trgtReflow = trgt
                                proofReflow = through_me

                        
                    # print(flag,"trying to change flows", bestminimasation, " i take over route from ",self.prev[path[0]].p.pub_key, " to ", self.next[path[1]].p.pub_key)
                    if bestminimasation != 0:
                        if flag:
                            print(flag,"trying to change flows", bestminimasation, " i take over route from ",self.flow_node.prev[path[0]].p.pub_key, " to ", self.flow_node.next[path[1]].p.pub_key)
                            self.requested_flows = RequestForRedirect(randcc, path[1], path[0], trgtReflow, proofReflow)
                            
                            await self.request_redirect(self.requested_flows)
                        else:
                            print("change, ",bestminimasation)
                            self.requested_flows = RequestForChange(randcc, repalcemenet_flow,to_from[0], to_from[1], endt, proof[0], proof[1])
                            
                            await self.request_change(self.requested_flows)
                            # request change
    def broadcast_query(self):
                    msg = bytearray([FlowProtocol.QUERY_FLOWS])
                    cststo = dict()
                    cstsfrom = dict()
                    flows = []
                    for _, fp in self.flow_node.next.items():
                        cststo[fp.p.id_node] = fp.costto
                    for _, fp in self.flow_node.prev.items():
                        cstsfrom[fp.p.id_node] = fp.costto
                    
                    for k, v in self.flow_node.outflow.items():
                        if self.flow_node.map.get(k) != None:
                            flows.append((self.flow_node.map[k][1],v[0],v[1]))
                        else:
                            flows.append((bytes(bytearray([0 for _ in range(32)])),v[0],v[1]))
                    msg += len(cststo).to_bytes(4, byteorder="big")
                    for k,v in cststo.items():
                        msg += k
                        msg += struct.pack(">f",v)
                    msg += len(cstsfrom).to_bytes(4, byteorder="big")
                    for k,v in cstsfrom.items():
                        msg += k
                        msg += struct.pack(">f",v)
                    msg += len(flows).to_bytes(4, byteorder="big")
                    for fl in flows:
                        msg += fl[0]
                        msg += fl[1]
                        msg += fl[2]
                    
                    # print("broadcasting... query flows")
                    loop = asyncio.get_event_loop()
                    loop.create_task(self.broadcast(msg))
    async def periodic(self):
        print(self.flow_node.desired_flow)
        self.iteration+=1
        if self.iteration % 3 == 0:
            # for k,v in self.flow_node.outflow.items():
            #     print("sending to ",self.flow_node.next[v[0]].p.pub_key)
            for k,v in self.flow_node.inflow.items():
                for _,_ in v.items():
                    print("receiving from ",self.flow_node.prev[k].p.pub_key)
            self.broadcast_query()
        if self.peer.pub_key == "9" and self.iteration == 10:
            to_push_back = []
            self.to_send_exit = []
            for p, v in self.flow_node.inflow.items():
                
                for flw, mp in v.items():
                    to_push_back.append((self.flow_node.prev[p],flw,mp[0], mp[1]))
                self.to_send_exit.append((bytes(bytearray([FixedPeers.EXIT])),p))
                
            # for k in to_push_back:
            #     await self.push_back_flow(k[0],k[1],k[2],k[3])
            
            # print("PPUSHING BACK!")
            loop = asyncio.get_event_loop()
            self.refresh_loop = loop.call_later(5, self._periodic)
            return
        if self.peer.pub_key == "9" and self.iteration == 11:
            for k in self.to_send_exit:
                await self.sendto_id(k[0],k[1]) 
            loop=asyncio.get_event_loop() 
            loop.create_task(self.stop_receiving())
            return
        if self.requested_flows == None:
            if True:
                cost = 0
                flow = len(self.flow_node.outflow.items())
                for k,v in self.flow_node.outflow.items():
                    cost+= v[2]
                self.iterationsss.append((self.iteration,flow,cost))
                print(f"sending {flow} at cost {cost}")
                print(self.iterationsss)
            if len(self.flow_node.outstanding_inflow.items()) > 0:
                if self.stage == self.max_stage:
                    return
                uniqid, prvtrgt = list(self.flow_node.outstanding_inflow.items())[0]
                mx = float("inf")
                chc = None
                nxstg = True
                for _, fp in self.flow_node.next.items():
                    if fp.mincostto + fp.costto <= mx and fp.desired_flow < 0 and fp.mincostis == prvtrgt[1]:
                        mx = fp.mincostto + fp.costto
                        chc = fp
                if mx != float("inf") and nxstg and chc.mincostto != float("inf"):
                        await self.request_flow(chc, chc.mincostto, chc.mincostis)
                else:
                    self.attempts += 1
                    if self.attempts > 4:
                        self.attempts = 0
                        await self.push_back_flow(self.flow_node.prev[prvtrgt[0]], self.flow_node.map[uniqid][0], uniqid, prvtrgt[1])
            elif self.flow_node.desired_flow >= 0 and self.flow_node.flow< self.flow_node.capacity:
                mx = float("inf")
                chc = None
                nxstg = True
                for _, fp in self.flow_node.next.items():
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
                
                elif len(list(self.flow_node.same.values())) > 0:
                    # print("wont be next stage for some reason")
                    await self.look_for_change()
            elif len(list(self.flow_node.same.values())) > 0:
                print(self.flow_node.desired_flow)
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
    def remap(self):
        return
        connect_two = (None, None)
        for k,v in self.flow_node.outstanding_inflow.items():
            for k1,v1 in self.flow_node.outstanding_outflow.items():
                print(v)
                if self.flow_node.inflow[v[0]][v[1]][1] == v1[0]:
                    connect_two = (v[0], v[1], k1, k, self.flow_node.inflow[v[0]][v[1]][1])
                    break
        if connect_two[0] != None:
            print("successfully connected two!")
            prevp = connect_two[0]
            previd = connect_two[1]
            myid = connect_two[2]
            oldflow = connect_two[3]
            target = connect_two[4]
            self.flow_node.inflow[prevp][previd] = (myid, target)
            self.flow_node.map[myid] = (previd, prevp)
            del self.flow_node.map[oldflow]
            trgt, cost = self.flow_node.outstanding_outflow[myid]
            # notify previous of changed cost:
            loop = asyncio.get_event_loop()
            loop.create_task(self.notify_change_in_cost(self.flow_node.prev[prevp],previd,cost,0))        
            del self.flow_node.outstanding_outflow[myid]
            del self.flow_node.outstanding_inflow[oldflow]
            return self.remap()

        return
    @bindfrom("disconnected_callback")
    def remove_peer(self, addr: tuple[str, int], node_id: bytes):
        print("removing peer")
        if self.flow_node.prev.get(node_id) != None:
            
            if self.flow_node.inflow.get(node_id) != None:
                
                for theirid, v in self.flow_node.inflow[node_id].items():
                    uniqid, target = v
                    self.flow_node.desired_flow -= 1
                    if self.flow_node.outstanding_inflow.get(uniqid) != None:
                        
                        del self.flow_node.outstanding_inflow[uniqid]
                        continue
                    else:
                        self.flow_node.outstanding_outflow[uniqid] = (self.flow_node.outflow[uniqid][1], self.flow_node.outflow[uniqid][2])
            del self.flow_node.inflow[node_id]
            self.remap()
            del self.flow_node.prev[node_id]
        if self.flow_node.next.get(node_id)!=None:
            
            to_del = []
            for uniqid, v in self.flow_node.outflow.items():
                    nxtpr, target, cost = v
                    
                    if nxtpr != node_id:
                        continue
                    self.flow_node.desired_flow += 1
                    print("we had flow from him")
                    to_del.append(uniqid)
                    if self.flow_node.outstanding_outflow.get(uniqid) != None:
                        
                        del self.flow_node.outstanding_outflow[uniqid]
                        continue
                    else:
                        theirid, prvpr = self.flow_node.map[uniqid]
                        
                        self.flow_node.outstanding_inflow[uniqid] = (prvpr, theirid)
            for v in to_del:
                self.flow_node.remove_outflow(v)
            self.remap()
            del self.flow_node.next[node_id]
        if self.flow_node.same.get(node_id)!=None:
            del self.flow_node.same[node_id]
        if isinstance(self.requested_flows, RequestForChange):
            if self.requested_flows.smp.p.id_node == node_id:
                self.requested_flows = None

        elif isinstance(self.requested_flows, RequestForFlow):
            if self.requested_flows.to.p.id_node == node_id:
                self.requested_flows = None
    @bindfrom("connected_callback")
    def peer_connected(self, p: Peer):
        print("Introducing to", p.addr)
        msg = bytearray([FlowProtocol.INTRODUCTION])
        msg += self.flow_node.desired_flow.to_bytes(8, byteorder="big", signed=True)
        msg += self.stage.to_bytes(8, byteorder="big")
        loop = asyncio.get_running_loop()
        loop.create_task(self._lower_sendto(msg, p.addr))
        

    
        