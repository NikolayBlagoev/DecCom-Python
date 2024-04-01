import asyncio
from copy import copy
from math import exp
import random
import struct
from typing import Callable
from deccom.peers.peer import Peer
from deccom.protocols.abstractprotocol import AbstractProtocol
from deccom.protocols.wrappers import *

class ChangeOffer(object):
    def __init__(self, to: bytes, theirstage: int) -> None:
        self.to = to
        self.theirstage = theirstage
        pass
class StagePeer(object):
    def __init__(self, p: Peer, stage: int, capacity: int) -> None:
        self.p = p
        self.stage = stage
        self.max_cost = float("inf")
        self.their_same: list[bytes] = []
        self.their_different: list[bytes] = []
        self.asked_before = 0
        self.counter = 0
        self.capacity = capacity
        pass
class Arpegio(AbstractProtocol):
    INTRODUCTION = int.from_bytes(b'\xe3', byteorder="big")
    PROPOSE_CHANGE = int.from_bytes(b'\xe4', byteorder="big")
    ANSWER_CHANGE = int.from_bytes(b'\xe5', byteorder="big")
    def __init__(self, costmap, stage, flow = 0, capacity = 0, submodule=None, callback: Callable[[tuple[str, int], bytes], None] = lambda *args: ...):
        super().__init__(submodule, callback)
        self.costmap = costmap
        self.stage = stage
        self.peer_connected = lambda *args: ...
        self.stage_peers: dict[bytes, int] = dict()
        self.per_stage: dict[int, list[StagePeer]] = dict()
        self.peers: dict[bytes, StagePeer] = dict()
        self.T = 3
        self.cooling = 0.992
        self.flow = flow
        self.capacity = capacity
        self.curr_costs = []
        self.max_cost = float("inf")
        self.offer = None
        self.can_switch = True
        self.alpha = 2
        self.counter = 1
        self.attemps = 0
        self.iterations = [(0, self.stage)]
        self.pob = []
        self.prev_switch = None
        self.representing = None
    
    def broadcast_introduction(self, send_to_all = True):
        loop = asyncio.get_event_loop()
        msg = bytearray([Arpegio.INTRODUCTION])
        msg += self.peer.id_node
        msg += self.stage.to_bytes(1, byteorder = "big")
        msg += self.counter.to_bytes(4, byteorder="big")
        msg += self.capacity.to_bytes(2, byteorder="big")
        for k, v in self.peers.items():
            if send_to_all or v.stage == self.stage or (self.prev_switch != None and self.prev_switch[0] == v.stage):
                loop.create_task(self._lower_sendto(msg,v.p.addr))
            elif v.stage == self.stage + 1 or v.stage == self.stage - 1 or (self.prev_switch != None and self.prev_switch[0] == v.stage + 1) or (self.prev_switch != None and self.prev_switch[0] == v.stage - 1):
                loop.create_task(self._lower_sendto(msg,v.p.addr))

    @bindto("find_peer")
    async def find_peer(self, pid):
        return None
    async def add_a_new_peer(self, stage, pid, counter, capacity):
        if pid != self.peer.id_node:
            if self.peers.get(pid) != None:
                
                return self.update_peer(stage,pid,counter, capacity)
            if self.stage_peers.get(pid) != None:
                currstage = self.stage_peers.get(pid)
                self.per_stage[currstage].remove(self.peers[pid])
            
            if self.per_stage.get(stage) == None:
                self.per_stage[stage] = []
            p = await self.find_peer(pid)
            self.stage_peers[pid] = stage
            pobj = StagePeer(p, stage, capacity)
            pobj.counter = counter
            self.per_stage[stage].append(pobj)
            self.peers[pid] = pobj
            self.calculate_cost()
    def update_peer(self, stage, pid, counter, capacity = None):
        # return
        if pid == self.peer.id_node:
            return
        if self.peers.get(pid) != None:
                stg = self.peers[pid]
                if stg.counter > counter:
                    return
                # print("updating peer\n\n")
                stg.counter = counter
                if capacity != None:
                    stg.capacity = capacity
                if self.stage_peers.get(pid) != None:
                    currstage = self.stage_peers.get(pid)
                    self.per_stage[currstage].remove(stg)
                stg.stage = stage
                if self.per_stage.get(stage) == None:
                    self.per_stage[stage] = []
                self.per_stage[stage].append(stg)
                self.stage_peers[pid] = stage
        else:
            loop = asyncio.get_event_loop()
            loop.create_task(self.find_peer(pid))
    def calculate_cost(self, k = 100):
        self.max_cost = 0
        if self.per_stage.get(self.stage) == None:
            return
        tmp = []
        for p in self.per_stage[self.stage]:
            tmp.append(100*self.costmap(self.peer.pub_key, p.p.pub_key))
        tmp.sort()
        tmp = tmp[:k]
        for c in tmp:
            self.max_cost += c
        ttp = 0
        for k,v in self.per_stage.items():
            ttp += len(v)
        print("new cost ", self.max_cost,len(self.per_stage[self.stage]), ttp, self.stage)
    
        
    def process_datagram(self, addr: tuple[str, int], data: bytes):
        if data[0] == Arpegio.INTRODUCTION:
            stage = data[33]
            counter = int.from_bytes(data[34:38], byteorder="big")
            capacity = int.from_bytes(data[38:40], byteorder="big")
            pid = data[1:33]
            loop = asyncio.get_event_loop()
            loop.create_task(self.add_a_new_peer(stage, pid, counter, capacity))
            if stage != self.stage and self.prev_switch != None and self.prev_switch[0] == stage:
                print("forwarding...")
                loop.create_task(self._lower_sendto(data, self.prev_switch[1]))
        elif data[0] == Arpegio.PROPOSE_CHANGE:
            print("proposal received")
            i = 1
            them = data[i:i+32]
            if them == self.peer.id_node:
                print("thats me")
                exit()
            elif self.get_peer(them) == None:
                self.reject_proposal(addr,self.max_cost, self.stage)
                loop = asyncio.get_event_loop()
                loop.create_task(self.find_peer(them))
                return
            i+=32
            their_flow = int.from_bytes(data[i:i+2],byteorder="big")
            i+=2
            their_capacity = int.from_bytes(data[i:i+2],byteorder="big")
            i+=2
            if self.capacity < their_flow or self.flow > their_capacity:
                return self.reject_proposal(addr,self.max_cost, self.stage)
                
            len_pob = int.from_bytes(data[i:i+2],byteorder="big")
            their_pob = []
            i += 2
            for _ in range(len_pob):
                their_pob.append(int.from_bytes(data[i:i+2],byteorder="big", signed=True))
                i += 2
            representing = data[i: i+32]
            i+=32
            mystage = data[i]
            i += 1
            their_stage = data[i]
            i+=1
            
            if self.stage != mystage:
                print("wrong stage", self.stage, mystage)
                self.reject_proposal(addr, self.max_cost, self.stage)
                return
            if isinstance(self.offer, ChangeOffer):
                if self.offer.to != them:
                    print(" already have an offer, not to them tho...")
                    self.reject_proposal(addr,self.max_cost, self.stage)
                    return
                else:
                    if them > self.peer.id_node:
                        self.reject_proposal(addr,self.max_cost, self.stage)
                        return
                    else:
                        
                        self.counter += 1
                        
                        self.accept_proposal(addr, self.max_cost, self.stage)
                        self.T = self.cooling*self.T
                        self.alpha = max(1, self.alpha * 0.9)
                        self.pob = their_pob
                        self.flow = their_flow
                        self.representing = representing
                        self.max_cost = -1
                        self.per_stage[self.peers[them].stage].remove(self.peers[them])
                        self.stage_peers[them] = self.stage
                        self.peers[them].stage = self.stage
                        if self.per_stage.get(self.stage) == None:
                            self.per_stage[self.stage] = []
                        self.per_stage[self.stage].append(self.peers[them])

                        self.stage = their_stage
                        self.broadcast_introduction()
                        return
            mycost = self.max_cost
            theircost = 0
            costs: dict[bytes, float] = dict()
            max_l = int.from_bytes(data[i:i+4], byteorder="big")
            i+=4
            for _ in range(max_l):
                pr = data[i:i+32]
                i+=32
                theircost = struct.unpack(">f", data[i:i+4])[0]
                i+=4
                theircounter = int.from_bytes(data[i:i+4], byteorder="big")
                i+=4
                if self.peers.get(pr) != None:
                    self.update_peer(self.stage, pr, theircounter)

                costs[pr] = theircost
                
            
            their_max_same = 0
            
            
            
            
            # print(costs, max_l)
            mysame = self.per_stage.get(self.stage) if self.per_stage.get(self.stage) != None else []
            
            
            
            costs_tmp = []
            for p in mysame:
                if costs.get(p.p.id_node) == None:
                    their_max_same = 0
                    
                    print("same: ooops they dont know ", p.p.pub_key)
                    break
                costs_tmp.append(costs.get(p.p.id_node))
                their_max_same += costs.get(p.p.id_node)
            costs_tmp.sort()
            costs_tmp = costs_tmp[:5]
            if (their_max_same == 0 and len(mysame) > 0) or len(mysame) == 0:
                print("they dont know enough peers", their_max_same == 0 and len(mysame) > 0, len(mysame) == 0)
                self.reject_proposal(addr, self.max_cost, self.stage)
                return
            

            max_l = int.from_bytes(data[i:i+4], byteorder="big")
            i+=4
            my_same_max = 0
            costs_tmp = []
            for _ in range(max_l):
                pr = data[i:i+32]
                i+=32
                counter = int.from_bytes(data[i:i+4], byteorder="big")
                i += 4
                if self.peers.get(pr) == None and self.peer.id_node != pr:
                    my_same_max = -float("inf")
                    loop = asyncio.get_event_loop()
                    loop.create_task(self.find_peer(pr))
                    print("maxl ooops... i dont know", pr)

                    continue
                self.update_peer(their_stage, pr, counter)
                # if self.peers.get(pr).stage != their_stage:
                #     continue
                cost = 100*self.costmap(self.peer.pub_key, self.peers[pr].p.pub_key)
                costs_tmp.append(cost)
                my_same_max += cost
            if my_same_max >= 0:
                my_same_max  = 0
                for p in self.per_stage[their_stage]:
                    my_same_max += 100*self.costmap(self.peer.pub_key, self.peers[p.p.id_node].p.pub_key)

            costs_tmp.sort()
            costs_tmp = costs_tmp[:5]
            
            # self.calculate_cost()
            their_max_cost_reported = struct.unpack(">f",data[i:])[0]
            if (my_same_max < 0 and max_l > 0) or self.per_stage.get(self.stage) == None or len(self.per_stage[self.stage]) != 3:
                print("i dont know enough peers :/")
                self.reject_proposal(addr, self.max_cost, self.stage)
                return
            mycost = self.max_cost
            # if self.T * (mycost)**self.alpha > their_max_same**self.alpha and self.T * (their_max_cost_reported)**self.alpha > my_same_max**self.alpha:
            # if mycost > their_max_same and their_max_cost_reported > my_same_max:
            if max(my_same_max,their_max_same) < max(mycost,their_max_cost_reported):
                print("perform switch", self.T * mycost, their_max_same, self.T * their_max_cost_reported, my_same_max, self.T, len(mysame),self.stage)
                print("going from ", self.stage," to ", their_stage)
                #perform switch 2.9763498325156017 0.8402053564786911 3.3682570280230477 0.037882558746736295
                # perform switch 1.726714622962025 0 4.15973953745985 0.014725477178423239 1.9405979999999998
# proposal received
# wrong stage
                self.counter += 1
                
                self.accept_proposal(addr, my_same_max, self.stage)
                self.T = self.cooling*self.T
                self.alpha = max(1, self.alpha * 0.9)
                self.pob = their_pob
                self.flow = their_flow
                self.representing = representing
                self.max_cost = -1
                self.per_stage[self.peers[them].stage].remove(self.peers[them])
                self.stage_peers[them] = self.stage
                self.peers[them].stage = self.stage
                if self.per_stage.get(self.stage) == None:
                    self.per_stage[self.stage] = []
                self.per_stage[self.stage].append(self.peers[them])

                self.stage = their_stage
                self.broadcast_introduction()

                
            else:
                r = random.uniform(0,1)
                if exp((max(mycost,their_max_cost_reported) - max(my_same_max,their_max_same))/self.T) > r:
                    print("WRONG! perform switch", self.T * mycost, their_max_same, self.T * their_max_cost_reported, my_same_max, self.T, len(mysame),self.stage)
                    print("going from ", self.stage," to ", their_stage)
                    print(exp((mycost + their_max_cost_reported - my_same_max - their_max_same)/self.T), r)
                    #perform switch 2.9763498325156017 0.8402053564786911 3.3682570280230477 0.037882558746736295
                    # perform switch 1.726714622962025 0 4.15973953745985 0.014725477178423239 1.9405979999999998
    # proposal received
    # wrong stage
                    self.counter += 1
                    
                    self.accept_proposal(addr, my_same_max, self.stage)
                    
                    self.T = self.cooling * self.T
                    self.alpha = max(1, self.alpha * 0.9)
                    self.pob = their_pob
                    self.flow = their_flow
                    self.representing = representing
                    self.max_cost = -1
                    self.per_stage[self.peers[them].stage].remove(self.peers[them])
                    self.stage_peers[them] = self.stage
                    self.peers[them].stage = self.stage
                    if self.per_stage.get(self.stage) == None:
                        self.per_stage[self.stage] = []
                    self.per_stage[self.stage].append(self.peers[them])

                    self.stage = their_stage
                    self.broadcast_introduction()
                else:
                    # print("my cost too high", their_max_cost_reported, my_diff_max + my_same_max, mycost, their_max_same + their_max_same)
                    # print(exp((mycost + their_max_cost_reported - my_same_max - their_max_same)/self.T), r)
                    self.reject_proposal(addr, self.max_cost, self.stage)
            return
        elif data[0] == Arpegio.ANSWER_CHANGE:
            if self.offer == None:
                return
            if self.peers[self.offer.to].p.addr != addr:
                return
            if data[1] == 0:
                
                print("they accepted")
                tmp = self.stage
                if data[2] == self.offer.theirstage:
                    print("with correct stage")
                    self.prev_switch = (self.stage, addr)
                    self.counter += 1
                    self.T = self.cooling*self.T
                    self.alpha = max(1, self.alpha * 0.9)
                    self.stage = self.offer.theirstage
                    i = 7
                    their_flow = int.from_bytes(data[i:i+2],byteorder="big")
                    i+=2

                    len_pob = int.from_bytes(data[i:i+2],byteorder="big")
                    their_pob = []
                    for _ in range(len_pob):
                        their_pob.append(int.from_bytes(data[i:i+2],byteorder="big", signed=True))
                        i += 2
                    representing = data[i: i+32]
                    self.representing = representing
                    self.pob = their_pob
                    self.flow = their_flow
                    self.broadcast_introduction()
                
                self.update_peer(tmp, self.offer.to, int.from_bytes(data[3:7], byteorder="big"))
                self.offer = None
                return
                
            elif data[1] == 1:
                
                self.pob.pop()
                self.pob.append(-1)
                self.update_peer(data[2], self.offer.to, int.from_bytes(data[3:7], byteorder="big"))
                self.peers[self.offer.to].max_cost = struct.unpack(">f",data[7:11])[0]
                self.peers[self.offer.to].asked_before = 4
                self.offer = None
                i = 11
                loop = asyncio.get_event_loop()
                while i < len(data):
                    # if self.peers.get(data[i:i+32]) == None:
                        
                    #     loop.create_task(self.find_peer(data[i:i+32]))
                    #     i+=36
                    #     continue
                    pr = data[i:i+32]
                    i+=32
                    counter = int.from_bytes(data[i:i+4], byteorder="big")
                    i += 4
                    self.update_peer(data[2],pr,counter)
                    
                    
                return
        else:
            super().process_datagram(addr, data[1:])
    
    def _periodic(self):
        loop = asyncio.get_running_loop()
        loop.create_task(self.periodic())

    
    @bindto("get_peer")
    def get_peer(self, idp: bytes) -> Peer:
        return None
    def accept_proposal(self, to: tuple[str,int], my_cost: float, their_stage: int):
        msg = bytearray([Arpegio.ANSWER_CHANGE])
        self.prev_switch = (self.stage, to)
        msg += int(0).to_bytes(1, byteorder="big")
        msg += their_stage.to_bytes(1, byteorder="big")
        msg += self.counter.to_bytes(4, byteorder="big")
        msg += self.flow.to_bytes(2, byteorder="big")
        msg += len(self.pob).to_bytes(2, byteorder = "big")
        for v in self.pob:
            msg += v.to_bytes(2, byteorder = "big", signed = True)
        msg += self.representing
        loop = asyncio.get_event_loop()
        loop.create_task(self._lower_sendto(msg, to))
        return 
    def reject_proposal(self, to: tuple[str,int], my_cost: float, my_stage: int):
        msg = bytearray([Arpegio.ANSWER_CHANGE])
        msg += int(1).to_bytes(1, byteorder="big")
        msg += my_stage.to_bytes(1, byteorder="big")
        msg += self.counter.to_bytes(4, byteorder="big")
        msg+= struct.pack(">f", my_cost)
        if self.per_stage.get(self.stage) == None:
            self.per_stage[self.stage] = []
        
        for p in self.per_stage[self.stage]:
            msg += p.p.id_node
            msg += p.counter.to_bytes(4, byteorder="big")
        loop = asyncio.get_event_loop()
        loop.create_task(self._lower_sendto(msg, to))
        return 
    def send_proposal(self, to, proof: list[tuple[StagePeer, float]]):
        self.attemps = 5
        self.offer = ChangeOffer(to, self.stage_peers[to])
        self.pob.append(self.offer.theirstage)
        addr = self.get_peer(to).addr
        msg = bytearray([Arpegio.PROPOSE_CHANGE])
        msg += self.peer.id_node
        msg += self.flow.to_bytes(2, byteorder="big")
        msg += self.capacity.to_bytes(2, byteorder="big")
        print((len(self.pob)))
        msg += len(self.pob).to_bytes(2, byteorder = "big")
        for v in self.pob:
            msg += v.to_bytes(2, byteorder = "big", signed = True)
        msg += self.representing
        msg += self.offer.theirstage.to_bytes(1, byteorder="big")
        msg += self.stage.to_bytes(1, byteorder = "big")
        # print(proof)
        msg += len(proof).to_bytes(4, byteorder="big")
        for p in proof:
            msg += p[0].p.id_node
            msg += struct.pack(">f",p[1])
            msg += p[2].to_bytes(4, byteorder = "big")
        
        if self.per_stage.get(self.stage) == None:
            self.per_stage[self.stage] = []
        
        sm = self.per_stage[self.stage]
        msg += len(sm).to_bytes(4, byteorder="big")
        for p in sm:
            msg += p.p.id_node
            msg += p.counter.to_bytes(4, byteorder="big")
        
        msg += struct.pack(">f", self.max_cost)
        
        loop = asyncio.get_event_loop()
        loop.create_task(self._lower_sendto(msg, addr))
    async def periodic(self):
        print("periodic", self.stage)
        total_cost = 0
        intralayercost = 0
        summed_cost = 0
        counter_nodes = 1
        for k, v in self.per_stage.items():
            
            for vl in v:
                counter_nodes += 1
                tmo_cost = 0
                for other in v:
                    if vl == other:
                        continue
                    tmo_cost += 100*self.costmap(vl.p.pub_key, other.p.pub_key)
                    summed_cost += 100*self.costmap(vl.p.pub_key, other.p.pub_key)
                
                if k == self.stage:
                    tmo_cost += 100*self.costmap(vl.p.pub_key, self.peer.pub_key)
                    summed_cost += 2*100*self.costmap(vl.p.pub_key, self.peer.pub_key)
                total_cost = max(total_cost, tmo_cost)
                if vl.stage == self.stage + 1 or vl.stage == self.stage - 1:
                    intralayercost = max(10 * self.costmap(vl.p.pub_key, self.peer.pub_key), intralayercost)
                if self.per_stage.get(vl.stage+1) != None:
                    for other in self.per_stage[vl.stage + 1]:
                        intralayercost = max(10 * self.costmap(other.p.pub_key, vl.p.pub_key), intralayercost)
                if self.per_stage.get(vl.stage-1) != None:
                    for other in self.per_stage[vl.stage - 1]:
                        intralayercost = max(10 * self.costmap(other.p.pub_key, vl.p.pub_key), intralayercost)
            
        self.iterations.append((self.iterations[-1][0] + 1, total_cost, intralayercost, summed_cost, counter_nodes, summed_cost/(2*counter_nodes)))
        if self.peer.pub_key == "0":
            for k,v in self.per_stage.items():
                print(k, len(v))
            print(self.iterations)
        if len(self.iterations) > 315:
            for k,v in self.per_stage.items():
                print(k, len(v))
            exit()
        
        count = 1
        diff_stages: list[bytes] = []
        self.calculate_cost()
        if self.offer != None or  len(self.iterations) > 300:
            if len(self.iterations) > 300:
                self.broadcast_introduction(send_to_all=True)
            if self.attemps == 0:
                self.pob.pop()
                self.pob.append(-1)
                self.offer = None
            self.attemps -= 1
            loop = asyncio.get_event_loop()
            self.refresh_loop = loop.call_later(2, self._periodic)
            return
        for k,v in self.stage_peers.items():
            if v != self.stage: 
                diff_stages.append(k)
        
        
        rn = random.uniform(0,1) < 0.5 and self.per_stage.get(self.stage) != None and len(self.per_stage[self.stage]) == 3
        # if (count > 1 and minb == self.peer.id_node) or len(diff_stages) == 0 or self.offer != None:
        if not rn or self.offer!=None:
            print("count",count, len(diff_stages))
            self.can_switch = False

            loop = asyncio.get_event_loop()
            self.refresh_loop = loop.call_later(2, self._periodic)
            return
        self.can_switch = True
        diff_stages = random.sample(diff_stages,min(15, len(diff_stages)))
        cost_minimisation = 0
        chs = None
        proof = []
        for pt in diff_stages:
            pr = self.peers[pt]
            if pr.asked_before > 0:
                pr.asked_before -= 1
                continue
            if self.per_stage.get(pr.stage+1) == None:
                self.per_stage[pr.stage+1] = []
            if self.per_stage.get(pr.stage-1) == None:
                self.per_stage[pr.stage-1] = []
            prvpprs = self.per_stage[pr.stage-1]
            nxtprs = self.per_stage[pr.stage+1]
            smpr:list[StagePeer] = copy(self.per_stage[pr.stage])
            
            smpr.remove(pr)
            tmp_cost_same = 0
            
            tmp_proof = []
            for p in prvpprs + nxtprs:
                
                tmp_proof.append((p,100*self.costmap(self.peer.pub_key, p.p.pub_key), 0))
           
            for p in smpr:
                tmp_cost_same += 100*self.costmap(self.peer.pub_key,p.p.pub_key)
                tmp_proof.append((p,100*self.costmap(self.peer.pub_key, p.p.pub_key),p.counter))
                
            
            if self.max_cost - tmp_cost_same > cost_minimisation or (cost_minimisation<=0 and exp((self.max_cost - tmp_cost_same)/self.T) > random.uniform(0,1)):
                cost_minimisation = self.max_cost - tmp_cost_same
                chs = pt
                proof = tmp_proof
                #print("minimisation of ", tmp_cost_same, self.max_cost, pr.max_cost)
        if chs != None:
            if self.get_peer(chs) == None:
                loop = asyncio.get_event_loop()
                loop.create_task(self.find_peer(chs))
            else:
                print("sending proposal to",self.get_peer(chs).pub_key)
                
                self.send_proposal(chs, proof)
        else:
            print("No proposal")
        loop = asyncio.get_event_loop()
        self.refresh_loop = loop.call_later(2, self._periodic)



        
    async def start(self, p : Peer):
        await super().start(p)
        self.peers[p.id_node] = StagePeer(p,self.stage, self.capacity)
        self.representing = p.id_node
        self._periodic()
        


    
    @bindfrom("connected_callback")
    def add_peer(self, addr: tuple[str,int], p: Peer):
        loop = asyncio.get_event_loop()
        msg = bytearray([Arpegio.INTRODUCTION])
        msg += self.peer.id_node
        msg += self.stage.to_bytes(1, byteorder = "big")
        msg += self.counter.to_bytes(4, byteorder = "big")
        msg += self.capacity.to_bytes(2, byteorder = "big")
        print("introducing")
        loop.create_task(self._lower_sendto(msg, p.addr))
        self.peer_connected(addr, p)
