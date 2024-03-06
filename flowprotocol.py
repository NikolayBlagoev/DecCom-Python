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

    def __init__(self, stage, max_stage, capacity, flow, minflow, maxflow, costmap, submodule=None, callback: Callable[[tuple[str, int], bytes], None] = ...):
        super().__init__(submodule, callback)
        self.flow = flow
        self.minflow = minflow
        self.maxflow = maxflow
        self.desired_flow = 0
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
        self.outstanding_inflow: dict[tuple[bytes, bytes], bytes] = dict() # previous peer, unique id - > target
        self.inflow: dict[bytes, dict[bytes,tuple[bytes, bytes]]] = dict() # previous peer -> unique id -> unique id, target
        self.outflow: dict[bytes, tuple[bytes, bytes, float]] = dict() # unique id -> next peer, target, cost
        self.uniqueids: list[bytes] = []
        self.map: dict[bytes, tuple[bytes,bytes]] = dict()
        self.requested_flows:tuple[bytes,FlowPeer,float, bytes] = None
        self.costmap = costmap
        self.T = 0.5
    async def start(self):
        await super().start()
        if self.stage == self.max_stage:
            self.targets[Peer.me.id_node] = 0
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
            print("peer introducing!",addr)
            stage = int.from_bytes(data[9:17], byteorder="big")
            if stage == (self.stage-1):

                fp = FlowPeer(p,stage,int.from_bytes(data[1:9], byteorder="big", signed=True), self.costmap(Peer.me.pub_key, p.pub_key))
                self.prev[p.id_node] = fp
            elif stage == (self.stage+1):
                if stage == self.max_stage:
                    fp = FlowPeer(p,stage,int.from_bytes(data[1:9], byteorder="big", signed=True), self.costmap(Peer.me.pub_key, p.pub_key))
                    fp.mincostto = 0
                    fp.dist_to_targ[p.id_node] = 0
                    fp.mincostis = p.id_node
                    self.targets[p.id_node] = 1

                    self.next[p.id_node] = fp
                else:
                    fp = FlowPeer(p,stage,int.from_bytes(data[1:9], byteorder="big", signed=True), self.costmap(Peer.me.pub_key, p.pub_key))
                    self.next[p.id_node] = fp
            elif stage == self.stage:
                self.same[p.id_node] = SamePeer(p)
        elif data[0] == FlowProtocol.FLOW_REQUEST:
            
            bts = data[1:5]
            target = data[5:37]
            cst = struct.unpack(">f", data[37:])[0]
            loop = asyncio.get_running_loop()
            if self.desired_flow >= 0 or self.flow >= self.capacity:
                print("too much, cant accept")
                msg = bytearray([FlowProtocol.FLOW_RESPONSE])
                msg += bts
                msg += self.desired_flow.to_bytes(8, byteorder="big", signed=True)
                msg += target
                msg += struct.pack(">f", float("inf"))
                loop.create_task(self._lower_sendto(msg, addr))
                
            elif self.targets.get(target) == None:
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
                    p = self.get_al(addr)
                    self.uniqueids.append(uniqid)
                    self.outstanding_inflow[(p,bts)] = uniqid
                else:
                    self.map[uniqid] = (bts, self.get_al(addr).id_node)
                    trgtcst = self.outstanding_outflow[uniqid]
                    del self.outstanding_outflow[uniqid]
                    self.targets[trgtcst[0]] = float("inf")
                    minc = float("inf")
                    for idx, trgtcst2 in self.outstanding_outflow.items():
                        if target == trgtcst2[0] and trgtcst2[1] < minc:
                            minc = trgtcst2[1]
                    self.targets[trgtcst[0]] = minc
                   
                    # might need to rebroadcast
                p = self.get_al(addr)
                self.desired_flow += 1
                self.flow += 1
                if self.inflow.get(p.id_node) == None:
                    self.inflow[p.id_node] = dict()
                self.inflow[p.id_node][bts] = (uniqid, target)
                
                msg = bytearray([FlowProtocol.FLOW_RESPONSE])
                print("accepted flow")
                msg += bts
                msg += self.desired_flow.to_bytes(8, byteorder="big", signed=True)
                msg += target
                msg += struct.pack(">f", cst)
                loop.create_task(self._lower_sendto(msg, addr))
        elif data[0] == FlowProtocol.FLOW_RESPONSE:
            print("flow response received")
            if self.requested_flows == None or len(self.requested_flows) != 4:
                # CANCEL THAT FLOW
                return
            bts = data[1:5]
            desired_flow = int.from_bytes(data[5:13], byteorder="big", signed=True)
            target = data[13:45]
            cst = struct.unpack(">f", data[45:])[0]
            if self.requested_flows[0] != bts:
                return
            self.requested_flows[1].desired_flow = desired_flow
            if self.requested_flows[2] == cst:
                self.desired_flow -= 1
                
                self.targets[target] = cst + self.next[self.get_al(addr).id_node].costto
                

                uniqid = None
                
                for idx, trgtcst in self.outstanding_inflow.items():
                    if target == trgtcst:
                        uniqid = idx
                        break
                if uniqid == None:
                    uniqid = urandom(4)
                
                
                    while uniqid in self.uniqueids:
                        uniqid = urandom(4)
                    p = self.get_al(addr)
                    self.uniqueids.append(uniqid)
                    self.outstanding_outflow[bts] = (target, cst + self.next[self.get_al(addr).id_node].costto)
                    msg = bytearray([FlowProtocol.CHANGE])
                    msg += self.desired_flow.to_bytes(8, byteorder="big", signed=True)
                    msg += target
                    msg += struct.pack(">f", cst + self.next[self.get_al(addr).id_node].costto)
                    # msg += "next_best"
                    
                    # broadcast change
                    print("broadcasting...")
                    loop = asyncio.get_event_loop()
                    loop.create_task(self.broadcast(msg))

                    self.outflow[uniqid] = (self.get_al(addr).id_node, target, cst + self.next[self.get_al(addr).id_node].costto)

                    msg = bytearray([FlowProtocol.QUERY_FLOWS])
                    for _, fp in self.next.items():
                        
                        cstto = dict()
                        for k, v in self.outflow.items():
                            if v[0] == fp.p.id_node:
                                if cstto.get(v[1]) == None:
                                    cstto[v[1]] = (1, fp.costto)
                                else:
                                    cstto[v[1]] = (cstto[v[1]] + 1, fp.costto)
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
                    # might need to notify previous of this change
                    self.map[trgtcst] = (idx[1],idx[0])
                    trgtcst = self.outstanding_inflow[idx]
                    del self.outstanding_inflow[idx]
                    self.outflow[trgtcst] = (self.get_al(addr).id_node, target, cst + self.next[self.get_al(addr).id_node].costto)
                    # might need to notify previous of this change



                    # self.targets[trgtcst[0]] = float("inf")
                    # minc = float("inf")
                    # for idx, trgtcst2 in self.outstanding_outflow.items():
                    #     if target == trgtcst2[0] and trgtcst2[1] < minc:
                    #         minc = trgtcst2[1]
                    # self.targets[trgtcst[0]] = minc
                    # notify the previous of this change ?




                
                
                
            else:
                self.requested_flows[1].dist_to_targ[target] = cst
                self.requested_flows[1].updatemin()
                print("setting target",self.requested_flows[1].dist_to_targ[target])
            self.requested_flows = None
        elif data[0] == FlowProtocol.CHANGE:
            desired_flow = int.from_bytes(data[1:9], byteorder="big", signed=True)
            target = data[9:41]
            cst = struct.unpack(">f", data[41:])[0]
            if self.next.get(self.get_al(addr).id_node) != None:
                self.next.get(self.get_al(addr).id_node).desired_flow = desired_flow
                self.next.get(self.get_al(addr).id_node).dist_to_targ[target] = cst
                self.next.get(self.get_al(addr).id_node).updatemin()
            elif self.prev.get(self.get_al(addr).id_node) != None:
                self.prev.get(self.get_al(addr).id_node).desired_flow = desired_flow
                self.prev.get(self.get_al(addr).id_node).dist_to_targ[target] = cst
                self.prev.get(self.get_al(addr).id_node).updatemin()
        elif data[0] == FlowProtocol.QUERY_FLOWS:
            p = self.get_al(addr)
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

        elif data[0] == FlowProtocol.PUSH_BACK_FLOW:
            bts = data[1:5]
            target = data[5:37]
            if self.outflow.get(bts) == None or self.next[self.outflow.get(bts)[0]].p.addr != addr:
                return
            infl = self.map.get(bts)
            self.desired_flow += 1
            if infl == None:
                del self.outstanding_outflow[bts]
            else:
                _, trgt = self.inflow[infl[1]][infl[0]]
                assert target == trgt
                nwflw = None
                mn = float("inf")
                for k,v in self.outstanding_outflow.items():
                    if v[0] == target and v[1] < mn:
                        mn = v[1]
                        nwfl = k
                if nwflw == None:
                    self.outstanding_inflow[(infl[1],infl[0])] = target
                    del self.inflow[infl[1]][infl[0]]
                else:
                    self.inflow[infl[1]][infl[0]] = (nwflw, target)
                    self.map[nwflw] = (bts, infl[1])
                    del self.map[bts]
                    trgt, cost = self.outstanding_outflow[nwflw]
                    # notify previous of changed cost:
                    self.desired_flow -= 1
                    del self.outstanding_outflow[nwflw]
        elif data[0] == FlowProtocol.PROPOSE_CHANGE:
            if self.requested_flows != None:
                if len(self.requested_flows) != 6:
                    return
            
            target = data[1:33]
            curr_flow = data[33:65]
            new_flow = data[65:97]
            if self.requested_flows != None:          
                if self.requested_flows[0].p.id_node != self.get_al(addr).id_node:
                    # REJECT
                    return
                if self.requested_flows[1][0] == new_flow and self.requested_flows[1][1] == curr_flow:
                    print("ACCEPT")
                    return
                # REJECT
                return
            
            # flt_me_now = struct.unpack(">f", data[97:101])
            flt_them_now = struct.unpack(">f", data[101:105])[0]
            # flt_me_then = struct.unpack(">f", data[105:109])
            flt_them_then = struct.unpack(">f", data[109:113])[0]
            if flt_them_then + self.costmap(Peer.me.pub_key, self.next[new_flow].p.pub_key) < flt_them_now + self.costmap(Peer.me.pub_key, self.next[curr_flow].p.pub_key):
                replacement_flow = data[113:117]
                tellthem = None
                for k, v in self.outflow.items():
                    if v[0] == curr_flow and v[1] == target:
                        tellthem = k
                        break
                if tellthem == None:
                    print("rejecting")
                    return
                print("accepting change")
                msg = bytearray([FlowProtocol.RESPOND_CHANGE])
                msg += int(0).to_bytes(1, byteorder="big")
                msg += tellthem
                loop = asyncio.get_event_loop()
                loop.create_task(self._lower_sendto(msg, addr))
                return
                #accept
            print("rejecting")
            # reject
            return


        # return super().process_datagram(addr, data)
    async def push_back_flow(self, fp: FlowPeer, uniqid_their, uniqid_ours, target):
        msg = bytearray([FlowProtocol.PUSH_BACK_FLOW])
        msg += uniqid_their
        msg += target
        self.flow -= 1
        del self.inflow[fp.p.id_node][uniqid_their]
        if self.outstanding_inflow.get((fp.p.id_node, uniqid_their)) == None:
            self.outstanding_outflow[uniqid_ours] = (self.outflow[uniqid_ours][1], self.outflow[uniqid_ours][2])
        else:
            del self.outstanding_inflow[(fp.p.id_node, uniqid_their)]
            self.uniqueids.remove(uniqid_ours)
        loop = asyncio.get_running_loop()
        loop.create_task(self._lower_sendto(msg,fp.p.addr))
    async def request_flow(self, fp: FlowPeer, cost: float, to: bytes):
        print("requesting flow from",fp.p.pub_key)
        uniqid = urandom(4)
        while uniqid in self.uniqueids:
            uniqid = urandom(4)

        self.uniqueids.append(uniqid)
        self.requested_flows = (uniqid, fp, cost, to)
        msg = bytearray([FlowProtocol.FLOW_REQUEST])
        msg += uniqid
        msg += to
        msg += struct.pack(">f", cost)
        await self._lower_sendto(msg,fp.p.addr)

    async def request_change(self, requested_change: tuple[SamePeer, tuple[bytes, bytes], tuple[bytes, bytes], tuple[float, float], tuple[float,float], bytes]):
        print("requesting change from")
        msg = bytearray([FlowProtocol.PROPOSE_CHANGE])
        smp = requested_change[0]
        target= requested_change[1][1]
        nxt_pcurr = requested_change[1][0]
        nxt_pnew = requested_change[2][0]
        flt_me_now = requested_change[3][1]
        flt_them_now = requested_change[3][0]
        flt_me_then = requested_change[4][1]
        flt_them_then = requested_change[4][0]
        msg += target
        msg += nxt_pcurr
        msg += nxt_pnew
        msg += struct.pack(">f", flt_them_now)
        msg += struct.pack(">f", flt_me_now)
        msg += struct.pack(">f", flt_them_then)
        msg += struct.pack(">f", flt_me_then)
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
                                mflw = 0
                                
                                if self.next.get(k[0]) == None:
                                    print("I dont know peer")
                                    continue
                                # i know this peer
                                mcst = self.costmap(Peer.me.pub_key, self.next[k[0]].p.pub_key)
                                currcost = self.costmap(Peer.me.pub_key, self.next[v1[0]].p.pub_key)
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
                                    
                    print("trying to change flows", bestminimasation)
                    if bestminimasation != 0:
                        
                        self.requested_flows = (randcc, to_from[0], to_from[1], proof[0], proof[1], repalcemenet_flow)
                        await self.request_change(self.requested_flows)
                        # request change
    async def periodic(self):
        print(self.desired_flow)
        if self.requested_flows == None:
            if self.stage == 0:
                cost = 0
                flow = len(self.outflow.items())
                for k,v in self.outflow.items():
                    cost+= v[2]
                print(f"sending {flow} at cost {cost}")
            if len(self.outstanding_inflow.items()) > 0:
                print("I HAVE OUTSTANDING INFLOW")
                return
            elif self.desired_flow >= 0 and self.flow < self.capacity:
                mx = float("inf")
                chc = None
                nxstg = True
                for pid, fp in self.next.items():
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
        

    
        