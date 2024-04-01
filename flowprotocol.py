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
    NOTIFY_SWITCH = int.from_bytes(b'\xda', byteorder="big")
    CHECK_FLOW = int.from_bytes(b'\x11', byteorder="big")
    EVAL = int.from_bytes(b'\x22', byteorder="big")
    required_lower = AbstractProtocol.required_lower + ["get_al", "broadcast"]
    def __init__(self, stage: int, max_stage: int, capacity: int, flow: int, minflow: int, maxflow: int, costmap, submodule=None, callback: Callable[[tuple[str, int], bytes], None] = ...):
        super().__init__(submodule, callback)
        
        self.iteration = 0 
        self.iterationsss = []

        self.flow_node = FlowNode(flow,minflow,maxflow,capacity,stage)
        self.stage = stage
        self.attempts = 0
        self.max_stage = max_stage
        self.requested_flows: RequestForChange | RequestForRedirect | RequestForFlow = None
        self.costmap = costmap
        self.T = 1.7
        self.idles_with_flow = 7
        self.idles_with_outflow = 10
        self.checked = dict()


    async def start(self, p : Peer):
        await super().start(p)
        if self.stage == self.max_stage:
            self.flow_node.targets[self.peer.id_node] = 0
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
        if data[0] == FlowProtocol.INTRODUCTION:
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
        elif data[0] == FlowProtocol.INTRODUCTION + 1:
            # print("Introducing to", p.addr)
            msg = bytearray([FlowProtocol.INTRODUCTION])
            msg += self.flow_node.desired_flow.to_bytes(8, byteorder="big", signed=True)
            msg += self.stage.to_bytes(8, byteorder="big")
            loop = asyncio.get_running_loop()
            loop.create_task(self._lower_sendto(msg, p.addr))
        elif data[0] == FlowProtocol.FLOW_REQUEST:
            print("received request from ",p.pub_key)
            mnstg = int.from_bytes(data[1:9], byteorder="big")
            target = data[9:41]
            cost = struct.unpack(">f", data[41:45])[0]
            theirid = data[45:49] # their flow id
            cst_to_me = struct.unpack(">f", data[49:53])[0]
            if self.requested_flows != None:
                return self.reject_flow(addr,theirid,target)

            if mnstg != self.stage: # WRONG STAGE
                print("wrong stage")
                return self.reject_flow(addr,theirid,target)
            if self.flow_node.prev.get(p.id_node) == None:
                loop = asyncio.get_event_loop()
                msg = bytearray([FlowProtocol.INTRODUCTION + 1])
                loop.create_task(self._lower_sendto(msg, p.addr))
            if self.flow_node.targets.get(target) == None: # UNKNOWN
                print("dont know taget")
                return self.reject_flow(addr,theirid,target)
            
            if self.flow_node.targets[target] != cost: # WRONG COST
                print("wrong cost",cost,self.flow_node.targets[target])
                return self.reject_flow(addr,theirid,target) 

            if self.flow_node.desired_flow >= 0: # CANT TAKE THIS ANYMORE
                print("CANT TAKE")
                return self.reject_flow(addr,theirid,target)
            if self.flow_node.inflow.get(p.id_node) != None and self.flow_node.inflow[p.id_node].get(theirid) != None:
                return
            with open(f"log{self.peer.pub_key}.txt", "a") as log:
                log.write(f"flow given to {p.pub_key}\n")
            self.flow_node.add_inflow(p.id_node, theirid, target, cst_to_me)
            self.accept_flow(addr, theirid, target,cost)
            msg = self.flow_node.construct_update_message(FlowProtocol.QUERY_FLOWS)
            loop = asyncio.get_event_loop()
            loop.create_task(self._lower_broadcast(msg))
        elif data[0] == FlowProtocol.CHECK_FLOW:
            theirid = data[1:5]
            if self.flow_node.prev.get(p.id_node) != None:
                if self.flow_node.inflow.get(p.id_node) == None or self.flow_node.inflow[p.id_node].get(theirid) == None:
                    msg = bytearray([FlowProtocol.PUSH_BACK_FLOW + 1])
                    msg += theirid
                    loop = asyncio.get_event_loop()
                    loop.create_task(self._lower_sendto(msg, addr))
            elif self.flow_node.next.get(p.id_node) != None:
                if self.flow_node.outflow.get(theirid) == None:
                    self.cancel_flow(theirid,p)
        elif data[0] == FlowProtocol.FLOW_RESPONSE - 1:
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

        elif data[0] == FlowProtocol.FLOW_RESPONSE:
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
            self.idles_with_flow = 8
            with open(f"log{self.peer.pub_key}.txt", "a") as log:
                log.write("-----------\n")
                cnt = 0
                for k,v in self.flow_node.inflow.items():
                    cnt += len(v.items())
                log.write(f"{self.flow_node.desired_flow} {len(self.flow_node.outflow.items())},{cnt}, {len(self.flow_node.outstanding_outflow.items())},{len(self.flow_node.outstanding_inflow.items())}\n")

            print("correctly at that")
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
                log.write(f"{self.flow_node.desired_flow} {len(self.flow_node.outflow.items())},{cnt}, {len(self.flow_node.outstanding_outflow.items())},{len(self.flow_node.outstanding_inflow.items())}\n")

                log.write("-----------\n")
                
            self.requested_flows = None
            self.attempts = 0
            self.idles_with_outflow = 10
            msg = bytearray([FlowProtocol.CHANGE])
            msg += self.flow_node.desired_flow.to_bytes(8, byteorder="big", signed=True)
            msg += target
            msg += struct.pack(">f", self.flow_node.min_cost_to_target(target))
            # print("correctly at that")
            loop = asyncio.get_event_loop()
            loop.create_task(self._lower_broadcast(msg))
            msg = self.flow_node.construct_update_message(FlowProtocol.QUERY_FLOWS)
            loop.create_task(self._lower_broadcast(msg))
        elif data[0] == FlowProtocol.CHANGE:
            if self.flow_node.next.get(p.id_node) == None:
                return
            dflow = int.from_bytes(data[1:9], byteorder="big", signed=True)
            target = data[9:41]
            cst = struct.unpack(">f", data[41:45])[0]
            self.flow_node.update_peer(p.id_node,target,cst,dflow)
        elif data[0] == FlowProtocol.QUERY_FLOWS:
            if self.flow_node.same.get(p.id_node) == None:
                return
            self.flow_node.update_same(p.id_node, data[1:])
        elif data[0] == FlowProtocol.PROPOSE_CHANGE:
            theirid = data[1:5]
            nxt_curr = data[5:37]
            nxt_new = data[37:69]
            target = data[69:101]
            curr_cost = struct.unpack(">f", data[101:105])[0]
            new_cost = struct.unpack(">f", data[105:109])[0]
            nxt_cost = struct.unpack(">f", data[109:113])[0]
            if self.flow_node.next.get(nxt_curr) == None or self.flow_node.next.get(nxt_new) == None:
                self.reject_change(p.addr,theirid,nxt_curr)
                return
            flw_chs = None
            for k,v in self.flow_node.outflow.items():
                to, trgt, cst = v
                if to == nxt_curr and trgt == target:
                    flw_chs = k
                    break
            if flw_chs == None:
                self.reject_change(p.addr,theirid,nxt_curr)
                return
            if self.requested_flows != None:
                if isinstance(self.requested_flows, RequestForChange):
                    if self.requested_flows.smp.p.id_node == p.id_node and self.requested_flows.curr_next == nxt_curr and self.requested_flows.new_next == nxt_new:
                        if True:
                            self.reject_change(p.addr,theirid,nxt_curr)
                            return
                        else:
                            self.accept_change(p.addr, nxt_new, theirid, nxt_curr, flw_chs, nxt_cost,p.id_node,new_cost)
                            self.requested_flows = None
                            self.attempts = 0
                            return
                self.reject_change(p.addr,theirid,nxt_curr)
                return
            my_curr_cost = self.flow_node.next[nxt_curr].costto
            my_new_cost = self.flow_node.next[nxt_new].costto
            if (curr_cost + my_curr_cost) > (my_new_cost + new_cost):
                with open(f"log{self.peer.pub_key}.txt", "a") as log:
                    log.write(f"accepting switch with {p.pub_key}\n")
                self.accept_change(p.addr, nxt_new, theirid, nxt_curr, flw_chs, nxt_cost,p.id_node,new_cost)
                return
            elif exp(((curr_cost + my_curr_cost) - (my_new_cost + new_cost))/self.T) > random.uniform(0,1):
                with open(f"log{self.peer.pub_key}.txt", "a") as log:
                    log.write(f"accepting switch with {p.pub_key}\n")
                self.accept_change(p.addr, nxt_new, theirid, nxt_curr, flw_chs, nxt_cost,p.id_node,new_cost)
                return
            self.reject_change(p.addr,theirid,nxt_curr)
            # msg += offer.my_flow
            # msg += offer.new_next
            # msg += offer.curr_next
            # msg += offer.target

        elif data[0] == FlowProtocol.RESPOND_CHANGE:
            
            myid = data[1:5]
            their_next = data[5:37]
            theirid = data[37:41]
            nw_cost = struct.unpack(">f", data[41:45])[0]
            their_new = struct.unpack(">f", data[45:49])[0]
            if self.requested_flows == None:
                if self._lower_get_peer(their_new) != None:
                    self.cancel_flow(mid,self._lower_get_peer(their_new))
                return
            if isinstance(self.requested_flows, RequestForChange):
                if self.requested_flows.my_flow != myid or self.requested_flows.smp.p.id_node != p.id_node or self.requested_flows.new_next != their_next:
                    if self._lower_get_peer(their_new) != None:
                        self.cancel_flow(mid,self._lower_get_peer(their_new))
                    return
                if self.flow_node.outflow.get(myid) == None:
                    # we dont have it anymore
                    with open(f"log{self.peer.pub_key}.txt", "a") as log:
                        log.write(f"WRONG CHANGE WITH {p.pub_key}\n")
                    self.requested_flows = None
                    self.attempts = 0
                    if self._lower_get_peer(their_new) != None:
                        self.cancel_flow(mid,self._lower_get_peer(their_new))
                    return
                # print("change accepted")
                with open(f"log{self.peer.pub_key}.txt", "a") as log:
                    log.write(f"change performed with {p.pub_key}\n")
                self.perform_change(self.requested_flows.new_next,theirid,self.requested_flows.curr_next, 
                self.requested_flows.my_flow, their_new, p.id_node, nw_cost)
                self.requested_flows = None
                self.T = self.T * 0.95
                self.attempts = 0
                
                self.flow_node.ignore_same(p.id_node)
            return
        elif data[0] == FlowProtocol.RESPOND_CHANGE - 1:
            myid = data[1:5]
            their_next = data[5:37]
            
            
            if isinstance(self.requested_flows, RequestForChange):
                if self.requested_flows.my_flow != myid or self.requested_flows.smp.p.id_node != p.id_node or self.requested_flows.new_next != their_next:
                    self.requested_flows = None
                    self.attempts = 0
                    self.flow_node.ignore_same(p.id_node)
                    return
            return
        elif data[0] == FlowProtocol.NOTIFY_CHANGE_IN_COST:
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
                msg = bytearray([FlowProtocol.NOTIFY_CHANGE_IN_COST])
                msg += prvid
                # print("notifying of change of cost to",new_next_cost_to_target + self.flow_node.next[their_curr].costto)
                msg += struct.pack(">f", cst + self.flow_node.next[p.id_node].costto)
                loop.create_task(self._lower_sendto(msg, prvpr.p.addr))
                
            return
        elif data[0] == FlowProtocol.NOTIFY_SWITCH:
            curr_id = data[1:5]
            new_id = data[5:9]
            new_prv = data[9:41]
            cst = struct.unpack(">f", data[41:45])[0]
            if self.flow_node.inflow.get(p.id_node) == None or self.flow_node.inflow[p.id_node].get(curr_id) == None:
                msg = bytearray([FlowProtocol.PUSH_BACK_FLOW])
                msg += new_id
                loop = asyncio.get_event_loop()
                if (self._lower_get_peer(new_prv)) != None:
                    loop.create_task(self._lower_sendto(msg, self._lower_get_peer(new_prv).addr))
                return
            self.flow_node.parent_change(curr_id, p.id_node, new_id, new_prv, cst)
            return
        elif data[0] == FlowProtocol.PROPOSE_REDIRECT:
            currntprv = data[1:33]
            currnxt = data[33:65]
            trgt = data[65:97]
            cst_prv_their = struct.unpack(">f", data[97:101])[0]
            cst_nxt_their = struct.unpack(">f", data[101:105])[0]
            theirid = data[105:109]
            assert len(theirid) == 4
            proof = cst_prv_their + cst_nxt_their
            if self.requested_flows != None:
                self.reject_redirect(p.addr, currntprv, currnxt, theirid)
                return
            
            
            if self.flow_node.inflow.get(currntprv) == None:
                self.reject_redirect(p.addr, currntprv, currnxt, theirid)

                return
            myid = None
            
            for k,v in self.flow_node.inflow[currntprv].items():
                if self.flow_node.outflow.get(v[0]) != None and self.flow_node.outflow[v[0]][0] == currnxt and v[1] == trgt:
                    myid = v[0]
                    break
            if myid == None:
                self.reject_redirect(p.addr, currntprv, currnxt, theirid)
                return
            cstm = self.flow_node.prev[currntprv].costto + self.flow_node.next[currnxt].costto
            if cstm > proof or exp((cstm - proof) / self.T) > random.uniform(0,1):
                self.T = self.T * 0.95
                self.accept_redirect(addr, currnxt, currntprv, self.flow_node.outflow[myid][2] - self.flow_node.next[currnxt].costto, theirid)
                prvid, prvpr = self.flow_node.map[myid]
                self.push_back(myid, prvid, prvpr)
                self.flow_node.remove_outflow(myid)
                with open(f"log{self.peer.pub_key}.txt", "a") as log:
                    log.write(f"redirectin traffic to {p.pub_key}\n")
                msg = bytearray([FlowProtocol.NOTIFY_SWITCH])
                msg += myid
                msg += theirid
                msg += p.id_node
                msg += struct.pack(">f", cst_nxt_their)
                loop = asyncio.get_event_loop()
                loop.create_task(self._lower_sendto(msg, self.flow_node.next[currnxt].p.addr))
                return

            self.reject_redirect(p.addr, currntprv, currnxt, theirid)

            return
        elif data[0] == FlowProtocol.RESPOND_REDIRECT - 7:
            currntprv = data[1:33]
            currnxt = data[33:65]
            myid = data[65:69]
            if isinstance(self.requested_flows, RequestForRedirect):
                if self.requested_flows.curr_pev == currntprv and self.requested_flows.smp.p.id_node == p.id_node and self.requested_flows.curr_next == currnxt and self.requested_flows.myid == myid:
                    self.requested_flows = None
                    self.attempts = 0
                    self.flow_node.ignore_same(p.id_node)
        elif data[0] == FlowProtocol.RESPOND_REDIRECT:
            currntprv = data[1:33]
            currnxt = data[33:65]
            cost_new = struct.unpack(">f", data[65:69])[0]
            myid = data[69:73]

            if isinstance(self.requested_flows, RequestForRedirect):
                if self.requested_flows.curr_pev == currntprv and self.requested_flows.smp.p.id_node == p.id_node and self.requested_flows.curr_next == currnxt and self.requested_flows.myid == myid:
                    
                    
                    ret = self.flow_node.add_outflow(myid, currnxt, self.requested_flows.target, cost_new, self.flow_node.next[currnxt].costto)
                    if not ret:
                        self.requested_flows = None
                        self.attemts = 0
                        print("WRONG SOMETHING")
                        with open(f"log{self.peer.pub_key}.txt", "a") as log:
                            log.write("wrong something\n")
                        return
                    self.T = self.T * 0.95
                    msg = bytearray([FlowProtocol.CHANGE])
                    target = self.requested_flows.target
                    msg += self.flow_node.desired_flow.to_bytes(8, byteorder="big", signed=True)
                    msg += target
                    msg += struct.pack(">f", self.flow_node.min_cost_to_target(target))
                    prvid = self.requested_flows.curr_pev
                    
                    self.requested_flows = None
                    self.attemts = 0

                    with open(f"log{self.peer.pub_key}.txt", "a") as log:
                        log.write(f"redirecting traffic... I now have the traffic of {p.pub_key}\n")
                    # print("correctly at that")
                    loop = asyncio.get_event_loop()
                    loop.create_task(self._lower_sendto(msg, self.flow_node.prev[prvid].p.addr))
                    #loop.create_task(self._lower_broadcast(msg))




                    


        elif data[0] == FlowProtocol.EVAL:
            theirid = data[1:5]
            if self.flow_node.inflow.get(p.id_node) == None or self.flow_node.inflow[p.id_node].get(theirid) == None:
                return
            myid = self.flow_node.inflow[p.id_node][theirid][0]
            cst  = struct.unpack(">f",data[5:9])[0]

            self.checked[theirid] = cst
            if self.flow_node.outflow.get(myid) == None:
                return
            nxtpr = self.flow_node.outflow[myid][0]

            msg = bytearray([FlowProtocol.EVAL])
            msg += myid
            msg += struct.pack(">f", self.flow_node.next.get(nxtpr).costto + cst)
            loop = asyncio.get_event_loop()
            loop.create_task(self._lower_sendto(msg, self.flow_node.next[nxtpr].p.addr))

        elif data[0] == FlowProtocol.CANCEL_FLOW:
            theirid = data[1:5]
            self.flow_node.remove_inflow(p.id_node, theirid)
        elif data[0] == FlowProtocol.PUSH_BACK_FLOW:
           myid = data[1:5]
           with open(f"log{self.peer.pub_key}.txt", "a") as log:
            
                cnt = 0
                for k,v in self.flow_node.inflow.items():
                    cnt += len(v.items())
                log.write("-----------\n")
                log.write(f"{self.flow_node.desired_flow} {len(self.flow_node.outflow.items())},{cnt}, {len(self.flow_node.outstanding_outflow.items())},{len(self.flow_node.outstanding_inflow.items())}\n")

                log.write("our flow was pushed back...removing\n")
                
           self.flow_node.remove_outflow(myid) 
           with open(f"log{self.peer.pub_key}.txt", "a") as log:
            
                cnt = 0
                for k,v in self.flow_node.inflow.items():
                    cnt += len(v.items())
                
                log.write(f"{self.flow_node.desired_flow} {len(self.flow_node.outflow.items())},{cnt}, {len(self.flow_node.outstanding_outflow.items())},{len(self.flow_node.outstanding_inflow.items())}\n")
                log.write("-----------\n")
        elif data[0] == FlowProtocol.PUSH_BACK_FLOW + 1:
           myid = data[1:5]
           with open(f"log{self.peer.pub_key}.txt", "a") as log:
            
                cnt = 0
                for k,v in self.flow_node.inflow.items():
                    cnt += len(v.items())
                log.write("-----------\n")
                log.write(f"{self.flow_node.desired_flow} {len(self.flow_node.outflow.items())},{cnt}, {len(self.flow_node.outstanding_outflow.items())},{len(self.flow_node.outstanding_inflow.items())}\n")

                log.write("our flow was pushed back...removing\n")
           self.idles_with_flow = 2
           self.flow_node.remove_outflow(myid, set_val=5) 
           with open(f"log{self.peer.pub_key}.txt", "a") as log:
            
                cnt = 0
                for k,v in self.flow_node.inflow.items():
                    cnt += len(v.items())
                
                log.write(f"{self.flow_node.desired_flow} {len(self.flow_node.outflow.items())},{cnt}, {len(self.flow_node.outstanding_outflow.items())},{len(self.flow_node.outstanding_inflow.items())}\n")
                log.write("-----------\n")
    def accept_redirect(self, addr, currnxt, currpv, cost_new, theirid):
        msg = bytearray([FlowProtocol.RESPOND_REDIRECT])
        msg += currpv
        msg += currnxt

        msg += struct.pack(">f", cost_new)
        msg += theirid
        loop = asyncio.get_event_loop()
        loop.create_task(self._lower_sendto(msg, addr))
    def reject_redirect(self, addr, currntprv, currnxt, theirid):
        msg = bytearray([FlowProtocol.RESPOND_REDIRECT - 7])
        msg += currntprv
        msg += currnxt
        msg += theirid
        loop = asyncio.get_event_loop()
        loop.create_task(self._lower_sendto(msg, addr))
    def reject_change(self, addr, theirid, my_curr_nxt):
        msg = bytearray([FlowProtocol.RESPOND_CHANGE - 1])
        msg += theirid
        msg += my_curr_nxt
        loop = asyncio.get_event_loop()
        loop.create_task(self._lower_sendto(msg, addr))
        return
        
    def perform_change(self, their_curr, theirid, my_curr_nxt, myid,new_next_cost_to_target  , who, their_cost_to_next):
        fp = self.flow_node.next[self.flow_node.outflow[myid][0]]
        self.T = self.T * 0.95
        loop = asyncio.get_event_loop()
        if self.flow_node.map.get(myid):
            prvid,prvpr = self.flow_node.map[myid]
            prvpr = self.flow_node.prev[prvpr]
            msg = bytearray([FlowProtocol.NOTIFY_CHANGE_IN_COST])
            msg += prvid
            # print("notifying of change of cost to",new_next_cost_to_target + self.flow_node.next[their_curr].costto)
            msg += struct.pack(">f", new_next_cost_to_target + self.flow_node.next[their_curr].costto)
            loop.create_task(self._lower_sendto(msg, prvpr.p.addr))
        
        msg = bytearray([FlowProtocol.NOTIFY_SWITCH])
        msg += myid
        msg += theirid
        msg += who
        msg += struct.pack(">f", their_cost_to_next)
        loop.create_task(self._lower_sendto(msg, fp.p.addr))


        
        

        self.flow_node.perform_change(myid,my_curr_nxt,their_curr,new_next_cost_to_target + self.flow_node.next[their_curr].costto)
        
        return
    def accept_change(self, addr, their_curr, theirid, my_curr_nxt, myid, nxt_cost,who,their_new):
        
        msg = bytearray([FlowProtocol.RESPOND_CHANGE])
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
        msg = bytearray([FlowProtocol.FLOW_RESPONSE - 1])
        msg += self.stage.to_bytes(8, byteorder="big")
        msg += target
        if self.flow_node.targets.get(target) == None:
            msg += struct.pack(">f", float("inf"))
        else:
            msg += struct.pack(">f", self.flow_node.targets[target])
        msg += theirid
        msg += self.flow_node.desired_flow.to_bytes(8, byteorder="big",signed=True)
        print("sending rejection")
        loop = asyncio.get_event_loop()
        loop.create_task(self._lower_sendto(msg, addr))
    
    def accept_flow(self, addr, theirid, target, cost):
        msg = bytearray([FlowProtocol.FLOW_RESPONSE])
        msg += self.stage.to_bytes(8, byteorder="big")
        msg += target
        msg += struct.pack(">f", cost)
        msg += theirid
        msg += self.flow_node.desired_flow.to_bytes(8, byteorder="big",signed=True)
        loop = asyncio.get_event_loop()
        loop.create_task(self._lower_sendto(msg, addr))
    def request_flow(self, chc: FlowPeer, cst: float):
        self.attempts = 5
        uniqid = self.flow_node.gen_new_uniqid()
        self.requested_flows = RequestForFlow(uniqueid = uniqid, to = chc, cost =  chc.mincostto, target = chc.mincostis, stg = self.stage + 1)
        msg = bytearray([FlowProtocol.FLOW_REQUEST])
        msg += (self.stage + 1).to_bytes(8, byteorder="big")
        msg += chc.mincostis
        msg += struct.pack(">f", chc.mincostto)
        msg += uniqid
        msg += struct.pack(">f", chc.costto)
        loop = asyncio.get_event_loop()
        loop.create_task(self._lower_sendto(msg, chc.p.addr))

    def cancel_flow(self, myid, nxtpr: Peer, remove = False):
        if remove:
            self.flow_node.remove_outflow(myid)
        msg = bytearray([FlowProtocol.CANCEL_FLOW])
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
        msg = bytearray([FlowProtocol.PROPOSE_CHANGE])
        msg += offer.my_flow
        msg += offer.new_next
        msg += offer.curr_next
        msg += offer.target
        msg += struct.pack(">f", offer.curr_cost)
        msg += struct.pack(">f", offer.new_cost)
        msg += struct.pack(">f", offer.nxt_cost)
        loop = asyncio.get_event_loop()
        loop.create_task(self._lower_sendto(msg, offer.smp.p.addr))
    def push_back(self, myid, theirid, prvpr, addition = 0):
        self.flow_node.push_back(theirid, prvpr)
        msg = bytearray([FlowProtocol.PUSH_BACK_FLOW + addition])
        msg += theirid
        loop = asyncio.get_event_loop()
        if (self._lower_get_peer(prvpr)) != None:
            loop.create_task(self._lower_sendto(msg, self._lower_get_peer(prvpr).addr))

    def request_redirect(self, request: RequestForRedirect):
        self.attempts = 5
        self.requested_flows = request
        msg = bytearray([FlowProtocol.PROPOSE_REDIRECT])
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
            log.write(f"{self.flow_node.desired_flow} {len(self.flow_node.outflow.items())},{cnt}, {len(self.flow_node.outstanding_outflow.items())},{len(self.flow_node.outstanding_inflow.items())}  {self.idles_with_flow}\n")

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
                    msg = bytearray([FlowProtocol.CHANGE])
                    msg += self.flow_node.desired_flow.to_bytes(8, byteorder="big", signed=True)
                    msg += target[0]
                    msg += struct.pack(">f", target[1])
                    
                    
                    loop.create_task(self._lower_broadcast(msg))
                msg = self.flow_node.construct_update_message(FlowProtocol.QUERY_FLOWS)
                loop.create_task(self._lower_broadcast(msg))
            elif len(self.iterationsss) % 12 == 3:
                loop = asyncio.get_event_loop()
                for k, d in self.flow_node.inflow.items():
                    for idflow, v in d.items():
                        if self.flow_node.outflow.get(v[0])!=None:
                            msg = bytearray([FlowProtocol.NOTIFY_CHANGE_IN_COST])
                            msg += idflow
                            # print("notifying of change of cost to",v[2])
                            msg += struct.pack(">f", self.flow_node.outflow[v[0]][2])
                            loop.create_task(self._lower_sendto(msg, self._lower_get_peer(k).addr))
            elif len(self.iterationsss) % 12 == 5 or len(self.iterationsss) % 12 == 1:
                loop = asyncio.get_event_loop()
                msg = bytearray([FlowProtocol.INTRODUCTION])
                msg += self.flow_node.desired_flow.to_bytes(8, byteorder="big", signed=True)
                msg += self.stage.to_bytes(8, byteorder="big")
                loop.create_task(self._lower_broadcast(msg))
            elif len(self.iterationsss) % 12 == 7 or len(self.iterationsss) % 12 == 9:
                loop = asyncio.get_event_loop()
                for k, v in self.flow_node.outflow.items():
                    msg = bytearray([FlowProtocol.CHECK_FLOW])
                    msg += k
                    loop.create_task(self._lower_sendto(msg, self.flow_node.next[v[0]].p.addr))
                for k,dv in self.flow_node.inflow.items():
                    for theirid,_ in dv.items():
                        msg = bytearray([FlowProtocol.CHECK_FLOW])
                        msg += theirid
                        loop.create_task(self._lower_sendto(msg, self.flow_node.prev[k].p.addr))

            if len(self.iterationsss) > 134: # takes ~14 iterations to start processes
                loop = asyncio.get_event_loop()
                if self.stage == 0:
                    for k, v in self.flow_node.outflow.items():
                        msg = bytearray([FlowProtocol.EVAL])
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
        
        if True:
            #self.idles_with_flow = 4
            buff = dict()
            to_remove = []
            
            for k, v in self.flow_node.outstanding_inflow.items():
                buff[k] = (v[0],v[1],v[2] - 1)
                if v[2] <= 1:
                    to_remove.append((k,v[0],v[1]))
            self.flow_node.outstanding_inflow = buff
            if len(to_remove) > 0:
                with open(f"log{self.peer.pub_key}.txt", "a") as log:
                    log.write(f"triggered {len(to_remove)}\n")
            for t in to_remove:
                self.push_back(t[0], t[2], t[1],addition = 1)
            
        assert self.flow_node.capacity >= len(self.flow_node.outflow.items())
        if len(self.flow_node.outstanding_outflow.items()) > 0 and self.stage != 0 and self.max_stage != self.stage:
            self.idles_with_outflow -= 1
        if self.idles_with_outflow <= 0:
            self.idles_with_outflow = 12
            to_remove = []
            with open(f"log{self.peer.pub_key}.txt", "a") as log:
                log.write("triggered\n")
            for k, v in self.flow_node.outstanding_outflow.items():
                to_remove.append(k)
            for t in to_remove:
                self.cancel_flow(t, self.flow_node.next[self.flow_node.outflow[t][0]].p,True)
            loop = asyncio.get_running_loop()
            self.refresh_loop = loop.call_later(2, self.periodic)

            return  
        if self.flow_node.desired_flow >= 0:
            if self.requested_flows != None:
                self.attempts -= 1
                print("outstanding request")
                if self.attempts > 0:
                    t = self.attempts
                    if isinstance(self.requested_flows, RequestForFlow):
                        msg = bytearray([FlowProtocol.FLOW_REQUEST])
                        msg += (self.stage + 1).to_bytes(8, byteorder="big")
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
                    print("dont know anyoen that can take")
                    if random.uniform(0,1) < 0.3:
                        chng_rqst = self.flow_node.get_same(self.T)
                        if isinstance(chng_rqst, RequestForChange):
                            self.request_switch(chng_rqst)
                        elif isinstance(chng_rqst, RequestForRedirect):
                            self.request_redirect(chng_rqst)
        else:
            if random.uniform(0,1) < 0.1:
                chng_rqst = self.flow_node.get_same(self.T)
                if isinstance(chng_rqst, RequestForChange):
                    self.request_switch(chng_rqst)
                elif isinstance(chng_rqst, RequestForRedirect):
                    self.request_redirect(chng_rqst)
            print("mine desired flow", self.flow_node.desired_flow)
        loop = asyncio.get_running_loop()
        self.refresh_loop = loop.call_later(2, self.periodic)
    
    
    
    
    @bindto("get_peer")
    def _lower_get_peer(self, idx: bytes) -> Peer:
        return None
     
    @bindfrom("disconnected_callback")
    def remove_peer(self, addr: tuple[str, int], node_id: bytes):
        self.flow_node.remove_peer(node_id)
        
        
    @bindfrom("connected_callback")
    def peer_connected(self, addr, p: Peer):
        print("Introducing to", p.addr)
        msg = bytearray([FlowProtocol.INTRODUCTION])
        msg += self.flow_node.desired_flow.to_bytes(8, byteorder="big", signed=True)
        msg += self.stage.to_bytes(8, byteorder="big")
        loop = asyncio.get_running_loop()
        loop.create_task(self._lower_sendto(msg, p.addr))
        

    
        