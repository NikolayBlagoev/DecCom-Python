import asyncio
import random
import traceback
from deccom.protocols.peerdiscovery.fixedpeers import FixedPeers
from deccom.protocols.wrappers import *
from deccom.utils.common import ternary_comparison
from typing import Any, Callable, List
from sys import maxsize
from deccom.peers.peer import Peer
import struct
from os import urandom
from deccom.protocols.abstractprotocol import AbstractProtocol
from flownode_ss import *
# flowprotocol ONLY for a source-sink (since they are equivalent)
class FlowProtocolSS(AbstractProtocol):
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
    NOTIFY_SWITCH = int.from_bytes(b'\xda', byteorder="big")
    CHECK_FLOW = int.from_bytes(b'\x11', byteorder="big")
    EVAL = int.from_bytes(b'\x22', byteorder="big")
    required_lower = AbstractProtocol.required_lower + ["get_al", "broadcast"]
    def __init__(self, stage: int, max_stage: int, capacity: int, flow: int, minflow: int, maxflow: int, costmap, submodule=None, callback: Callable[[tuple[str, int], bytes], None] = ...):
        super().__init__(submodule, callback)
        
        self.iteration = 0 
        self.iterationsss = []

        self.flow_node = FlowNode_SS(flow,minflow,maxflow,capacity,stage)
        self.stage = stage
        self.attempts = 0
        self.max_stage = max_stage
        self.requested_flows: RequestForChange | RequestForRedirect | RequestForFlow = None
        self.costmap = costmap
        self.T = 2
        self.idles_with_flow = 10
        self.checked = dict()


    async def start(self, p : Peer):
        await super().start(p)
        if self.stage == 0:
            self.flow_node.targets[self.peer.id_node] = 0
        self.flow_node.myid = self.peer.id_node
        self.periodic()
        print(self.peer.pub_key,"starting ")
    
    @bindto("get_al")
    def get_al(self, addr) -> Peer:
        return None
    
    
    def process_datagram(self, addr: tuple[str, int], data: bytes):
        p: Peer = self.get_al(addr)
        if p == None:
            print("unknown peer")
            return
        if data[0] == FlowProtocolSS.INTRODUCTION:
            # print("peer introducing", addr)
            desired_flow = int.from_bytes(data[1:9], byteorder="big", signed=True)
            stage = int.from_bytes(data[9:17], byteorder="big")
            # print("their stage", stage)
            if stage == (self.stage-1) % self.max_stage:
                if self.flow_node.prev.get(p.id_node) == None:
                    fp = FlowPeer(p, stage, desired_flow, self.costmap(self.peer.pub_key, p.pub_key))
                    self.flow_node.prev[p.id_node] = fp
            elif stage == (self.stage + 1) % self.max_stage:
                if self.flow_node.next.get(p.id_node) == None:
                    if stage == 0:
                        print("MET A SINK")
                        fp = FlowPeer(p,stage,desired_flow, self.costmap(self.peer.pub_key, p.pub_key))
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
        elif data[0] == FlowProtocolSS.INTRODUCTION + 1:
            # print("Introducing to", p.addr)
            if self.flow_node.next.get(p.id_node) != None:
                msg = bytearray([FlowProtocolSS.INTRODUCTION])
                msg += self.flow_node.desired_flow_source.to_bytes(8, byteorder="big", signed=True)
                msg += self.stage.to_bytes(8, byteorder="big")
                loop = asyncio.get_running_loop()
                loop.create_task(self._lower_sendto(msg, p.addr))
            else:
                msg = bytearray([FlowProtocolSS.INTRODUCTION])
                msg += self.flow_node.desired_flow_sink.to_bytes(8, byteorder="big", signed=True)
                msg += self.stage.to_bytes(8, byteorder="big")
                loop = asyncio.get_running_loop()
                loop.create_task(self._lower_sendto(msg, p.addr))
        elif data[0] == FlowProtocolSS.FLOW_REQUEST:
            print("received request from ",p.pub_key)
            mnstg = int.from_bytes(data[1:9], byteorder="big")
            target = data[9:41]
            cost = struct.unpack(">f", data[41:45])[0]
            theirid = data[45:49] # their flow id
            cst_to_me = struct.unpack(">f", data[49:53])[0]
            
            if mnstg % self.max_stage != self.stage: # WRONG STAGE
                print("wrong stage")
                return self.reject_flow(addr,theirid,target)
            if self.flow_node.prev.get(p.id_node) == None:
                loop = asyncio.get_event_loop()
                msg = bytearray([FlowProtocolSS.INTRODUCTION + 1])
                loop.create_task(self._lower_sendto(msg, p.addr))
            if self.flow_node.targets.get(target) == None: # UNKNOWN
                print("dont know taget")
                return self.reject_flow(addr,theirid,target)
            
            if self.flow_node.targets[target] != cost: # WRONG COST
                print("wrong cost",cost,self.flow_node.targets[target])
                return self.reject_flow(addr,theirid,target) 

            if self.flow_node.desired_flow_sink >= 0: # CANT TAKE THIS ANYMORE
                print("CANT TAKE")
                return self.reject_flow(addr,theirid,target)
            if self.flow_node.inflow.get(p.id_node) != None and self.flow_node.inflow[p.id_node].get(theirid) != None:
                return
            #print("we dont have", p.id_node, theirid)
            with open(f"log{self.peer.pub_key}.txt", "a") as log:
                log.write(f"flow given to {p.pub_key}\n")
            self.flow_node.add_inflow(p.id_node, theirid, target, cst_to_me)
            self.accept_flow(addr, theirid, target,cost)
            
        elif data[0] == FlowProtocolSS.CHECK_FLOW:
            theirid = data[1:5]
            if self.flow_node.prev.get(p.id_node) != None:
                if self.flow_node.inflow.get(p.id_node) == None or self.flow_node.inflow[p.id_node].get(theirid) == None:
                    msg = bytearray([FlowProtocolSS.PUSH_BACK_FLOW])
                    msg += theirid
                    loop = asyncio.get_event_loop()
                    loop.create_task(self._lower_sendto(msg, addr))
            elif self.flow_node.next.get(p.id_node) != None:
                if self.flow_node.outflow.get(theirid) == None:
                    self.cancel_flow(theirid,p)
        elif data[0] == FlowProtocolSS.FLOW_RESPONSE - 1:
            print("rejection")
            stg = int.from_bytes(data[1:9],  byteorder="big")
            target = data[9:41]
            cst = struct.unpack(">f", data[41:45])[0]
            mid = data[45:49]
            if isinstance(self.requested_flows, RequestForFlow):
                if self.requested_flows.uniqueid == mid and self.requested_flows.to.p.id_node == p.id_node:
                    self.requested_flows = None
                    
                    self.attempts = 0
            if self.flow_node.next.get(p.id_node) != None:
                
                theirflow = int.from_bytes(data[49:57],  byteorder="big", signed=True)
                self.flow_node.update_peer(p.id_node, target, cst, theirflow)

        elif data[0] == FlowProtocolSS.FLOW_RESPONSE:
            print("they accepted")
            stg = int.from_bytes(data[1:9],  byteorder="big")
            target = data[9:41]
            cst = struct.unpack(">f", data[41:45])[0]
            mid = data[45:49]
            theirflow = int.from_bytes(data[49:57],  byteorder="big", signed=True)
            if self.requested_flows == None:
                self.cancel_flow(mid,p)
                print("dont have request")
                return
            if not isinstance(self.requested_flows, RequestForFlow):
                self.cancel_flow(mid,p)
                print("incorrect request")
                return
            if self.requested_flows.to.p.id_node != p.id_node or self.requested_flows.uniqueid != mid:
                self.cancel_flow(mid,p)
                print("wrong receiver", self.requested_flows.uniqueid, mid)
                return 
            self.idles_with_flow = 7
            with open(f"log{self.peer.pub_key}.txt", "a") as log:
                log.write("-----------\n")
                cnt = 0
                for k,v in self.flow_node.inflow.items():
                    cnt += len(v.items())
                log.write(f"{self.flow_node.desired_flow_source} {len(self.flow_node.outflow.items())},{cnt}, {len(self.flow_node.outstanding_outflow.items())},{len(self.flow_node.outstanding_inflow.items())}\n")

                
            ret = self.flow_node.add_outflow(mid, p.id_node, target, cst, self.costmap(self.peer.pub_key, p.pub_key))
            if not ret:
                with open(f"log{self.peer.pub_key}.txt", "a") as log:
                    log.write("WRONG ID???\n")
                self.cancel_flow(mid,p)
                self.requested_flows = None
                return
            with open(f"log{self.peer.pub_key}.txt", "a") as log:
                log.write(f"our flow was accepted by {p.pub_key}\n")
                cnt = 0
                for k,v in self.flow_node.inflow.items():
                    cnt += len(v.items())
                log.write(f"{self.flow_node.desired_flow_source} {len(self.flow_node.outflow.items())},{cnt}, {len(self.flow_node.outstanding_outflow.items())},{len(self.flow_node.outstanding_inflow.items())}\n")

                log.write("-----------\n")
                
            self.requested_flows = None
            self.attempts = 0
            msg = bytearray([FlowProtocolSS.CHANGE])
            msg += self.flow_node.desired_flow_sink.to_bytes(8, byteorder="big", signed=True)
            msg += target
            msg += struct.pack(">f", self.flow_node.min_cost_to_target(target))
            # print("correctly at that")
            loop = asyncio.get_event_loop()
            loop.create_task(self._lower_broadcast(msg))
            
        elif data[0] == FlowProtocolSS.CHANGE:
            if self.flow_node.next.get(p.id_node) == None:
                return
            dflow = int.from_bytes(data[1:9], byteorder="big", signed=True)
            target = data[9:41]
            cst = struct.unpack(">f", data[41:45])[0]
            self.flow_node.update_peer(p.id_node,target,cst,dflow)
        elif data[0] == FlowProtocolSS.QUERY_FLOWS:
            if self.flow_node.same.get(p.id_node) == None:
                return
            self.flow_node.update_same(p.id_node, data[1:])
        
        elif data[0] == FlowProtocolSS.NOTIFY_CHANGE_IN_COST:
            flowid = data[1:5]
            cst = struct.unpack(">f",data[5:9])[0]
            #print("notified of change of cost... to", cst)
            if self.flow_node.outflow.get(flowid) == None:
                print("dont have such flow")
                return
            
            ret = self.flow_node.perform_change(flowid,p.id_node, p.id_node, cst + self.flow_node.next[p.id_node].costto)
            if ret and self.flow_node.outstanding_outflow.get(flowid) == None:
                loop = asyncio.get_event_loop()
                prvid,prvpr = self.flow_node.map[flowid]
                prvpr = self.flow_node.prev[prvpr]
                msg = bytearray([FlowProtocolSS.NOTIFY_CHANGE_IN_COST])
                msg += prvid
                # print("notifying of change of cost to",new_next_cost_to_target + self.flow_node.next[their_curr].costto)
                msg += struct.pack(">f", cst + self.flow_node.next[p.id_node].costto)
                loop.create_task(self._lower_sendto(msg, prvpr.p.addr))
                
            return
        elif data[0] == FlowProtocolSS.NOTIFY_SWITCH:
            curr_id = data[1:5]
            new_id = data[5:9]
            new_prv = data[9:41]
            cst = struct.unpack(">f", data[41:45])[0]
            if self.flow_node.inflow.get(p.id_node) == None or self.flow_node.inflow[p.id_node].get(curr_id) == None:
                msg = bytearray([FlowProtocolSS.PUSH_BACK_FLOW])
                msg += new_id
                loop = asyncio.get_event_loop()
                if (self._lower_get_peer(new_prv)) != None:
                    loop.create_task(self._lower_sendto(msg, self._lower_get_peer(new_prv).addr))
                return
            self.flow_node.parent_change(curr_id, p.id_node, new_id, new_prv, cst)
            return
        
        
        elif data[0] == FlowProtocolSS.EVAL:
            theirid = data[1:5]
            if self.flow_node.inflow.get(p.id_node) == None or self.flow_node.inflow[p.id_node].get(theirid) == None:
                return
            myid = self.flow_node.inflow[p.id_node][theirid][0]
            cst  = struct.unpack(">f",data[5:9])[0]

            self.checked[theirid] = cst
            if self.flow_node.outflow.get(myid) == None:
                return
            nxtpr = self.flow_node.outflow[myid][0]

            msg = bytearray([FlowProtocolSS.EVAL])
            msg += myid
            msg += struct.pack(">f", self.flow_node.next.get(nxtpr).costto + cst)
            loop = asyncio.get_event_loop()
            loop.create_task(self._lower_sendto(msg, self.flow_node.next[nxtpr].p.addr))

        elif data[0] == FlowProtocolSS.CANCEL_FLOW:
            theirid = data[1:5]
            self.flow_node.remove_inflow(p.id_node, theirid)
        elif data[0] == FlowProtocolSS.PUSH_BACK_FLOW:
           myid = data[1:5]
           with open(f"log{self.peer.pub_key}.txt", "a") as log:
            
                cnt = 0
                for k,v in self.flow_node.inflow.items():
                    cnt += len(v.items())
                log.write("-----------\n")
                log.write(f"{self.flow_node.desired_flow_source} {len(self.flow_node.outflow.items())},{cnt}, {len(self.flow_node.outstanding_outflow.items())},{len(self.flow_node.outstanding_inflow.items())}\n")

                log.write("our flow was pushed back...removing\n")
                
           self.flow_node.remove_outflow(myid) 
           with open(f"log{self.peer.pub_key}.txt", "a") as log:
            
                cnt = 0
                for k,v in self.flow_node.inflow.items():
                    cnt += len(v.items())
                
                log.write(f"{self.flow_node.desired_flow_sink} {len(self.flow_node.outflow.items())},{cnt}, {len(self.flow_node.outstanding_outflow.items())},{len(self.flow_node.outstanding_inflow.items())}\n")
                log.write("-----------\n")
    
        
    def perform_change(self, their_curr, theirid, my_curr_nxt, myid,new_next_cost_to_target  , who, their_cost_to_next):
        fp = self.flow_node.next[self.flow_node.outflow[myid][0]]
        self.T = self.T * 0.95
        loop = asyncio.get_event_loop()
        if self.flow_node.map.get(myid):
            prvid,prvpr = self.flow_node.map[myid]
            prvpr = self.flow_node.prev[prvpr]
            msg = bytearray([FlowProtocolSS.NOTIFY_CHANGE_IN_COST])
            msg += prvid
            # print("notifying of change of cost to",new_next_cost_to_target + self.flow_node.next[their_curr].costto)
            msg += struct.pack(">f", new_next_cost_to_target + self.flow_node.next[their_curr].costto)
            loop.create_task(self._lower_sendto(msg, prvpr.p.addr))
        
        msg = bytearray([FlowProtocolSS.NOTIFY_SWITCH])
        msg += myid
        msg += theirid
        msg += who
        msg += struct.pack(">f", their_cost_to_next)
        loop.create_task(self._lower_sendto(msg, fp.p.addr))


        
        

        self.flow_node.perform_change(myid,my_curr_nxt,their_curr,new_next_cost_to_target + self.flow_node.next[their_curr].costto)
        
        return
    def accept_change(self, addr, their_curr, theirid, my_curr_nxt, myid, nxt_cost,who,their_new):
        
        msg = bytearray([FlowProtocolSS.RESPOND_CHANGE])
        msg += theirid
        msg += my_curr_nxt
        msg += myid
        msg += struct.pack(">f", self.flow_node.outflow[myid][2] - self.flow_node.next[my_curr_nxt].costto)
        msg += struct.pack(">f", self.flow_node.next[their_curr].costto)
        loop = asyncio.get_event_loop()
        loop.create_task(self._lower_sendto(msg, addr))
        self.perform_change(their_curr,theirid,my_curr_nxt,myid,nxt_cost,who,their_new)
        return
    @bindto("broadcast")
    async def _lower_broadcast(self, msg):
        return None    
    def reject_flow(self, addr, theirid, target):
        msg = bytearray([FlowProtocolSS.FLOW_RESPONSE - 1])
        msg += self.stage.to_bytes(8, byteorder="big")
        msg += target
        if self.flow_node.targets.get(target) == None:
            msg += struct.pack(">f", float("inf"))
        else:
            msg += struct.pack(">f", self.flow_node.targets[target])
        msg += theirid
        msg += self.flow_node.desired_flow_sink.to_bytes(8, byteorder="big",signed=True)
        print("sending rejection")
        loop = asyncio.get_event_loop()
        loop.create_task(self._lower_sendto(msg, addr))
    
    def accept_flow(self, addr, theirid, target, cost):
        msg = bytearray([FlowProtocolSS.FLOW_RESPONSE])
        msg += self.stage.to_bytes(8, byteorder="big")
        msg += self.peer.id_node
        msg += struct.pack(">f", cost)
        msg += theirid
        msg += self.flow_node.desired_flow_sink.to_bytes(8, byteorder="big",signed=True)
        loop = asyncio.get_event_loop()
        loop.create_task(self._lower_sendto(msg, addr))
    def request_flow(self, chc: FlowPeer, cst: float):
        self.attempts = 5
        uniqid = self.flow_node.gen_new_uniqid()
        self.requested_flows = RequestForFlow(uniqueid = uniqid, to = chc, cost =  chc.mincostto, target = chc.mincostis, stg = (self.stage + 1) % self.max_stage)
        msg = bytearray([FlowProtocolSS.FLOW_REQUEST])
        msg += ((self.stage + 1) % self.max_stage).to_bytes(8, byteorder="big")
        msg += chc.mincostis
        msg += struct.pack(">f", chc.mincostto)
        msg += uniqid
        msg += struct.pack(">f", chc.costto)
        loop = asyncio.get_event_loop()
        loop.create_task(self._lower_sendto(msg, chc.p.addr))

    def cancel_flow(self, myid, nxtpr: Peer, remove = False):
        if remove:
            self.flow_node.remove_outflow(myid)
        msg = bytearray([FlowProtocolSS.CANCEL_FLOW])
        msg += myid
        loop = asyncio.get_event_loop()
        loop.create_task(self._lower_sendto(msg, nxtpr.addr))

    def periodic(self):
        
        loop = asyncio.get_event_loop()
        # loop.create_task(self._caller())
        asyncio.run_coroutine_threadsafe(self._caller(), loop)
    
    def request_switch(self, offer: RequestForChange):
        print("requesting switch")
        self.attempts = 5
        self.requested_flows = offer
        msg = bytearray([FlowProtocolSS.PROPOSE_CHANGE])
        msg += offer.my_flow
        msg += offer.new_next
        msg += offer.curr_next
        msg += offer.target
        msg += struct.pack(">f", offer.curr_cost)
        msg += struct.pack(">f", offer.new_cost)
        msg += struct.pack(">f", offer.nxt_cost)
        loop = asyncio.get_event_loop()
        loop.create_task(self._lower_sendto(msg, offer.smp.p.addr))
    def push_back(self, myid, theirid, prvpr):
        self.flow_node.push_back(theirid, prvpr)
        msg = bytearray([FlowProtocolSS.PUSH_BACK_FLOW])
        msg += theirid
        loop = asyncio.get_event_loop()
        if (self._lower_get_peer(prvpr)) != None:
            loop.create_task(self._lower_sendto(msg, self._lower_get_peer(prvpr).addr))

    def request_redirect(self, request: RequestForRedirect):
        self.attempts = 5
        self.requested_flows = request
        msg = bytearray([FlowProtocolSS.PROPOSE_REDIRECT])
        msg += request.curr_pev
        msg += request.curr_next
        msg += request.target
        msg += struct.pack(">f", request.proof[0])
        msg += struct.pack(">f", request.proof[1])
        request.myid = self.flow_node.gen_new_uniqid()
        msg += request.myid
        loop = asyncio.get_event_loop()
        loop.create_task(self._lower_sendto(msg, request.smp.p.addr))
    async def _caller(self):
        with open(f"log{self.peer.pub_key}.txt", "a") as log:

            try:
                #
                await self._periodic()
            except Exception:
                traceback.print_exc(file=log)
    async def _periodic(self):
        assert len(self.flow_node.outflow.items()) <= self.flow_node.capacity
        with open(f"log{self.peer.pub_key}.txt", "a") as log:
            cnt = 0
            for k,v in self.flow_node.inflow.items():
                cnt += len(v.items())
            log.write(f"{self.flow_node.desired_flow_source} {len(self.flow_node.outflow.items())},{cnt}, {len(self.flow_node.outstanding_outflow.items())},{len(self.flow_node.outstanding_inflow.items())}\n")

        if True:
            cost = 0
            flow = len(self.flow_node.outflow.items())
            for k,v in self.flow_node.outflow.items():
                cost+= v[2]
            
            self.iterationsss.append((self.iteration,flow,cost))
            self.iteration+=1
            if self.peer.pub_key == "0":
                print(self.iterationsss)
            if len(self.iterationsss) % 6 == 2:
                loop = asyncio.get_event_loop()
                target = self.flow_node.get_random_target()
                if target != None:
                    msg = bytearray([FlowProtocolSS.CHANGE])
                    msg += self.flow_node.desired_flow_sink.to_bytes(8, byteorder="big", signed=True)
                    msg += target[0]
                    msg += struct.pack(">f", target[1])
                    
                    
                    loop.create_task(self._lower_broadcast(msg))
                
            elif len(self.iterationsss) % 12 == 3:
                loop = asyncio.get_event_loop()
                for k, d in self.flow_node.inflow.items():
                    for idflow, v in d.items():
                        if self.flow_node.outflow.get(v[0])!=None:
                            msg = bytearray([FlowProtocolSS.NOTIFY_CHANGE_IN_COST])
                            msg += idflow
                            # print("notifying of change of cost to",v[2])
                            msg += struct.pack(">f", self.flow_node.outflow[v[0]][2])
                            loop.create_task(self._lower_sendto(msg, self._lower_get_peer(k).addr))
            elif len(self.iterationsss) % 12 == 5 or len(self.iterationsss) % 12 == 1:
                loop = asyncio.get_event_loop()
                msg = bytearray([FlowProtocolSS.INTRODUCTION])
                msg += self.flow_node.desired_flow_sink.to_bytes(8, byteorder="big", signed=True)
                msg += self.stage.to_bytes(8, byteorder="big")
                loop.create_task(self._lower_broadcast(msg))
            elif len(self.iterationsss) % 12 == 7 or len(self.iterationsss) % 12 == 9:
                loop = asyncio.get_event_loop()
                for k, v in self.flow_node.outflow.items():
                    msg = bytearray([FlowProtocolSS.CHECK_FLOW])
                    msg += k
                    loop.create_task(self._lower_sendto(msg, self.flow_node.next[v[0]].p.addr))
                for k,dv in self.flow_node.inflow.items():
                    for theirid,_ in dv.items():
                        msg = bytearray([FlowProtocolSS.CHECK_FLOW])
                        msg += theirid
                        loop.create_task(self._lower_sendto(msg, self.flow_node.prev[k].p.addr))

            if len(self.iterationsss) > 127: # takes ~7 iterations to start processes
                loop = asyncio.get_event_loop()
                if self.stage == 0:
                    for k, v in self.flow_node.outflow.items():
                        msg = bytearray([FlowProtocolSS.EVAL])
                        msg += k
                        msg += struct.pack(">f", self.flow_node.next.get(v[0]).costto)
                        loop.create_task(self._lower_sendto(msg, self.flow_node.next[v[0]].p.addr))
                sum_l  = 0
                i = 0
                for k,v in self.checked.items():
                    i+=1
                    sum_l+=v
                print(i, sum_l)
                self.refresh_loop = loop.call_later(2, self.periodic)
                return



            print(f"sending {flow} at cost {cost}, {self.flow_node.flow} {self.flow_node.capacity}" )
            print(f"desiredflow {self.flow_node.desired_flow_sink}" )
         
        if self.flow_node.desired_flow_source >= 0:
            if self.requested_flows != None:
                self.attempts -= 1
                print("outstanding request")
                if self.attempts > 0:
                    t = self.attempts
                    if isinstance(self.requested_flows, RequestForFlow):
                        msg = bytearray([FlowProtocolSS.FLOW_REQUEST])
                        msg += ((self.stage + 1) % self.max_stage).to_bytes(8, byteorder="big")
                        msg += self.requested_flows.to.mincostis
                        msg += struct.pack(">f", self.requested_flows.to.mincostto)
                        msg += self.requested_flows.uniqueid
                        msg += struct.pack(">f", self.requested_flows.to.costto)
                        loop = asyncio.get_event_loop()
                        loop.create_task(self._lower_sendto(msg, self.requested_flows.to.p.addr))
                    self.attempts = t
            else:
                self.attempts = 0
            if self.attempts <= 0:
   
                self.requested_flows = None
                self.attempts = 0
                chc, cst = self.flow_node.get_next_node()
                if chc != None and self.flow_node.flow < self.flow_node.capacity:
                    print("creating request")
                    self.request_flow(chc,cst)
                else:
                    print("dont know anyone that can take")
        
        loop = asyncio.get_running_loop()
        self.refresh_loop = loop.call_later(2, self.periodic)
    
    
    
    
    @bindto("get_peer")
    def _lower_get_peer(self, idx: bytes) -> Peer:
        return None
     
    @bindfrom("disconnected_callback")
    def remove_peer(self, addr: tuple[str, int], node_id: bytes):
        return
        
    @bindfrom("connected_callback")
    def peer_connected(self, addr, p: Peer):
        print("Introducing to", p.addr)
        msg = bytearray([FlowProtocolSS.INTRODUCTION])
        msg += self.flow_node.desired_flow_sink.to_bytes(8, byteorder="big", signed=True)
        msg += self.stage.to_bytes(8, byteorder="big")
        loop = asyncio.get_running_loop()
        loop.create_task(self._lower_sendto(msg, p.addr))
        

    
        