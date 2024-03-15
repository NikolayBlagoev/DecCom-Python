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
    def __init__(self, p: Peer, stage: int) -> None:
        self.p = p
        self.stage = stage
        self.max_cost = float("inf")
        self.their_same: list[bytes] = []
        self.their_different: list[bytes] = []
        self.asked_before = 0
        pass
class Arpegio(AbstractProtocol):
    INTRODUCTION = int.from_bytes(b'\xe3', byteorder="big")
    PROPOSE_CHANGE = int.from_bytes(b'\xe4', byteorder="big")
    ANSWER_CHANGE = int.from_bytes(b'\xe5', byteorder="big")
    def __init__(self, costmap, stage, submodule=None, callback: Callable[[tuple[str, int], bytes], None] = lambda *args: ...):
        super().__init__(submodule, callback)
        self.costmap = costmap
        self.stage = stage
        self.peer_connected = lambda *args: ...
        self.stage_peers: dict[bytes, int] = dict()
        self.per_stage: dict[int, list[StagePeer]] = dict()
        self.peers: dict[bytes, StagePeer] = dict()
        self.T = 2
        self.curr_costs = []
        self.max_cost = float("inf")
        self.offer = None
        self.can_switch = True
        self.alpha = 2
        self.iterations = [(0, self.stage)]
    
    def broadcast_introduction(self):
        loop = asyncio.get_event_loop()
        msg = bytearray([Arpegio.INTRODUCTION])
        msg += self.peer.id_node
        msg += self.stage.to_bytes(1, byteorder = "big")
        for k, v in self.peers.items():
            loop.create_task(self._lower_sendto(msg,v.p.addr))

    @bindto("find_peer")
    async def find_peer(self, pid):
        return None
    async def add_a_new_peer(self, stage, pid):
        if pid != self.peer.id_node:
            if self.stage_peers.get(pid) != None:
                currstage = self.stage_peers.get(pid)
                self.per_stage[currstage].remove(self.peers[pid])
            
            if self.per_stage.get(stage) == None:
                self.per_stage[stage] = []
            p = await self.find_peer(pid)
            self.stage_peers[pid] = stage
            pobj = StagePeer(p, stage)
            self.per_stage[stage].append(pobj)
            self.peers[pid] = pobj
    def process_datagram(self, addr: tuple[str, int], data: bytes):
        if data[0] == Arpegio.INTRODUCTION:
            stage = int.from_bytes(data[33:], byteorder="big")
            pid = data[1:33]
            loop = asyncio.get_event_loop()
            loop.create_task(self.add_a_new_peer(stage, pid))
            
        elif data[0] == Arpegio.PROPOSE_CHANGE:
            print("proposal received")
            i = 1
            them = data[i:i+32]
            if them == self.peer.id_node:
                print("thats me")
                exit()
            i+=32
            mystage = data[i]
            i += 1
            
            if self.stage != mystage:
                print("wrong stage")
                self.reject_proposal(addr, self.max_cost, self.stage)
                return
            if isinstance(self.offer, ChangeOffer):
                if self.offer.to != them:
                    print(" already have an offer, not to them tho...")
                    self.reject_proposal(addr,self.max_cost, self.stage)
            mycost = self.max_cost
            theircost = 0
            costs: dict[bytes, float] = dict()
            max_l = int.from_bytes(data[i:i+4], byteorder="big")
            i+=4
            for _ in range(max_l):
                pr = data[i:i+32]
                i+=32
                theircost = struct.unpack(">f", data[i:i+4])[0]
                costs[pr] = theircost
                i+=4
            their_max_same = 0
            their_max_diff = 0
            
            
            if self.per_stage.get(self.stage + 1) == None:
                self.per_stage[self.stage + 1] = []
            if self.per_stage.get(self.stage - 1) == None:
                self.per_stage[self.stage - 1] = []
            # print(costs, max_l)
            mysame = self.per_stage.get(self.stage) if self.per_stage.get(self.stage) != None else []
            
            mypeers = self.per_stage[self.stage + 1] + self.per_stage[self.stage - 1]
            if self.peers[them] in mypeers:
                mypeers.remove(self.peers[them])
            for p in mypeers:
                if costs.get(p.p.id_node) == None:
                    # their_max_diff = 0
                    print("diff: ooops they dont know ", p.p.pub_key)
                    break
                their_max_diff = max(their_max_diff,costs.get(p.p.id_node))
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
                print("they dont know enough peers", their_max_diff == 0 and len(mypeers) > 0, their_max_same == 0 and len(mysame) > 0)
                self.reject_proposal(addr, self.max_cost, self.stage)
                return
            # for ik in range(min(len(costs_tmp), len(self.curr_costs))):
            #     if (costs_tmp[ik])**self.alpha > self.T * (self.curr_costs[ik])**self.alpha:
            #         print("would increase one of the maxes")
            #         self.reject_proposal(addr, self.max_cost, self.stage)
            #         return

            max_l = int.from_bytes(data[i:i+4], byteorder="big")
            i+=4
            my_same_max = 0
            costs_tmp = []
            for _ in range(max_l):
                pr = data[i:i+32]
                i+=32
                if self.peers.get(pr) == None and self.peer.id_node != pr:
                    my_same_max = -float("inf")
                    loop = asyncio.get_event_loop()
                    loop.create_task(self.find_peer(pr))
                    print("maxl ooops... i dont know", pr)

                    continue

                cost = 100*self.costmap(self.peer.pub_key, self.peers[pr].p.pub_key)
                costs_tmp.append(cost)
                my_same_max += cost
            costs_tmp.sort()
            costs_tmp = costs_tmp[:5]
            # for ik in range(min(len(costs_tmp), len(self.curr_costs))):
            #     if (costs_tmp[ik])**self.alpha > self.T * (self.curr_costs[ik])**self.alpha:
            #         print("i might increase their max")
            #         self.reject_proposal(addr, self.max_cost, self.stage)
            #         return
            max_l_diff = int.from_bytes(data[i:i+4], byteorder="big")
            i+=4
            my_diff_max = 0
            for _ in range(max_l_diff):
                pr = data[i:i+32]
                i+=32
                if self.peers.get(pr) == None and self.peer.id_node != pr:
                    
                    print("maxldiff ooops... i dont know", pr)
                    loop = asyncio.get_event_loop()
                    loop.create_task(self.find_peer(pr))
                    continue

                cost = self.costmap(self.peer.pub_key, self.peers[pr].p.pub_key)
                my_diff_max = max(my_diff_max, cost)
            their_max_cost_reported = struct.unpack(">f",data[i:i+4])[0]
            if (my_same_max < 0 and max_l > 0):
                print("i dont know enough peers :/")
                self.reject_proposal(addr, self.max_cost, self.stage)
                return
            
            # if self.T * (mycost)**self.alpha > their_max_same**self.alpha and self.T * (their_max_cost_reported)**self.alpha > my_same_max**self.alpha:
            if mycost > their_max_same and their_max_cost_reported > my_same_max:
                print("perform switch", self.T * mycost, their_max_same, self.T * their_max_cost_reported, my_same_max, self.T, len(mysame),self.stage)
                print("going from ", self.stage," to ", data[i+4])
                #perform switch 2.9763498325156017 0.8402053564786911 3.3682570280230477 0.037882558746736295
                # perform switch 1.726714622962025 0 4.15973953745985 0.014725477178423239 1.9405979999999998
# proposal received
# wrong stage
                self.accept_proposal(addr, my_same_max, data[i+4])
                self.T = 0.95*self.T
                self.alpha = max(1, self.alpha * 0.9)
                
                self.max_cost = -1
                self.per_stage[self.peers[them].stage].remove(self.peers[them])
                self.stage_peers[them] = self.stage
                self.peers[them].stage = self.stage
                if self.per_stage.get(self.stage) == None:
                    self.per_stage[self.stage] = []
                self.per_stage[self.stage].append(self.peers[them])

                self.stage = data[i+4]
                self.broadcast_introduction()

                
            else:
                r = random.uniform(0,1)
                if exp((their_max_cost_reported - their_max_same)/self.T) > r and exp((mycost - my_same_max)/self.T) > r:
                    print("WRONG! perform switch", self.T * mycost, their_max_same, self.T * their_max_cost_reported, my_same_max, self.T, len(mysame),self.stage)
                    print("going from ", self.stage," to ", data[i+4])
                    print(exp((mycost + their_max_cost_reported - my_same_max - their_max_same)/self.T), r)
                    #perform switch 2.9763498325156017 0.8402053564786911 3.3682570280230477 0.037882558746736295
                    # perform switch 1.726714622962025 0 4.15973953745985 0.014725477178423239 1.9405979999999998
    # proposal received
    # wrong stage
                    self.accept_proposal(addr, my_same_max, data[i+4])
                    self.T = 0.95 * self.T
                    self.alpha = max(1, self.alpha * 0.9)
                    
                    self.max_cost = -1
                    self.per_stage[self.peers[them].stage].remove(self.peers[them])
                    self.stage_peers[them] = self.stage
                    self.peers[them].stage = self.stage
                    if self.per_stage.get(self.stage) == None:
                        self.per_stage[self.stage] = []
                    self.per_stage[self.stage].append(self.peers[them])

                    self.stage = data[i+4]
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
                if data[2] == self.stage:
                    print("with correct stage")
                    self.T = 0.95*self.T
                    self.alpha = max(1, self.alpha * 0.9)
                    self.stage = self.peers[self.offer.to].stage
                    self.broadcast_introduction()
                
                self.per_stage[self.peers[self.offer.to].stage].remove(self.peers[self.offer.to])
                self.stage_peers[self.offer.to] = data[2]
                self.peers[self.offer.to].stage = data[2]
                self.per_stage[data[2]].append(self.peers[self.offer.to])
                self.offer = None
                return
                
            elif data[1] == 1:
                
                self.per_stage[self.peers[self.offer.to].stage].remove(self.peers[self.offer.to])
                self.stage_peers[self.offer.to] = data[2]
                self.peers[self.offer.to].stage = data[2]
                self.per_stage[data[2]].append(self.peers[self.offer.to])
                self.peers[self.offer.to].max_cost = struct.unpack(">f",data[3:7])[0]
                self.peers[self.offer.to].asked_before = 2
                self.offer = None
                i = 7
                loop = asyncio.get_event_loop()
                while i < len(data):
                    loop.create_task(self.find_peer(data[i:i+32]))
                    i+=32
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
        msg += int(0).to_bytes(1, byteorder="big")
        msg += their_stage.to_bytes(1, byteorder="big")
        msg+= struct.pack(">f", my_cost)
        loop = asyncio.get_event_loop()
        loop.create_task(self._lower_sendto(msg, to))
        return 
    def reject_proposal(self, to: tuple[str,int], my_cost: float, my_stage: int):
        msg = bytearray([Arpegio.ANSWER_CHANGE])
        msg += int(1).to_bytes(1, byteorder="big")
        msg += my_stage.to_bytes(1, byteorder="big")
        msg+= struct.pack(">f", my_cost)
        if self.per_stage.get(self.stage) == None:
            self.per_stage[self.stage] = []
        for p in self.per_stage[self.stage]:
            msg += p.p.id_node
        loop = asyncio.get_event_loop()
        loop.create_task(self._lower_sendto(msg, to))
        return 
    def send_proposal(self, to, proof: list[tuple[StagePeer, float]]):
        self.offer = ChangeOffer(to, self.stage_peers[to])
        addr = self.get_peer(to).addr
        msg = bytearray([Arpegio.PROPOSE_CHANGE])
        msg += self.peer.id_node
        msg += self.offer.theirstage.to_bytes(1, byteorder="big")
        # print(proof)
        msg += len(proof).to_bytes(4, byteorder="big")
        for p in proof:
            msg += p[0].p.id_node
            msg += struct.pack(">f",p[1])
        
        if self.per_stage.get(self.stage) == None:
            self.per_stage[self.stage] = []
        if self.per_stage.get(self.stage - 1) == None:
            self.per_stage[self.stage - 1] = []
        if self.per_stage.get(self.stage + 1) == None:
            self.per_stage[self.stage + 1] = []
        sm = self.per_stage[self.stage]
        diff_stage = self.per_stage[self.stage + 1] + self.per_stage[self.stage - 1]
        if self.peers[to] in diff_stage:
            diff_stage.remove(self.peers[to])
        msg += len(sm).to_bytes(4, byteorder="big")
        for p in sm:
            msg += p.p.id_node
        msg += len(diff_stage).to_bytes(4, byteorder="big")
        for p in diff_stage:
            
            msg += p.p.id_node
        msg += struct.pack(">f", self.max_cost)
        msg += self.stage.to_bytes(1, byteorder = "big")
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
                if vl.stage == self.stage:
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
            print(self.iterations)
        if len(self.iterations) > 120:
            exit()
        minb = self.peer.id_node
        count = 1
        diff_stages: list[bytes] = []
        curr_costs_sames = []
        curr_cost_same = 0
        curr_cost_diff = 0
        if self.offer != None:
            loop = asyncio.get_event_loop()
            self.refresh_loop = loop.call_later(2, self._periodic)
            return
        for k,v in self.stage_peers.items():
            if v == self.stage:
                count += 1
                curr_cost_same += 100*self.costmap(self.peer.pub_key, self.get_peer(k).pub_key)
                curr_costs_sames.append(100*self.costmap(self.peer.pub_key, self.get_peer(k).pub_key))
                minb = minb if minb < k else k
            else:
                diff_stages.append(k)
            if v == self.stage - 1 or v == self.stage + 1:
                curr_cost_diff = max(10*self.costmap(self.peer.pub_key, self.get_peer(k).pub_key),curr_cost_diff)
        self.max_cost = curr_cost_same
        self.max_cost = float("inf") if self.max_cost == 0 else self.max_cost
        curr_costs_sames.sort()
        self.curr_costs = curr_costs_sames[:5]
        rn = random.random() < 0.5
        # if (count > 1 and minb == self.peer.id_node) or len(diff_stages) == 0 or self.offer != None:
        if rn or self.offer!=None:
            print("count",count, len(diff_stages))
            self.can_switch = False

            loop = asyncio.get_event_loop()
            self.refresh_loop = loop.call_later(2, self._periodic)
            return
        self.can_switch = True
        diff_stages = random.sample(diff_stages,min(10, len(diff_stages)))
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
            tmp_cost_diff = 0
            tmp_proof = []
            tmp_sames = []
            for p in prvpprs + nxtprs:
                tmp_cost_diff = max(10*self.costmap(self.peer.pub_key, self.get_peer(p.p.id_node).pub_key), tmp_cost_diff)
                tmp_proof.append((p,10*self.costmap(self.peer.pub_key, self.get_peer(p.p.id_node).pub_key)))
           
            for p in smpr:
                tmp_cost_same += 100*self.costmap(self.peer.pub_key, self.get_peer(p.p.id_node).pub_key)
                tmp_proof.append((p,100*self.costmap(self.peer.pub_key, self.get_peer(p.p.id_node).pub_key)))
                tmp_sames.append(100*self.costmap(self.peer.pub_key, self.get_peer(p.p.id_node).pub_key))
            tmp_sames.sort()
            tmp_sames = tmp_sames[:5]
            if self.max_cost - tmp_cost_same > cost_minimisation or (cost_minimisation<=0 and exp((self.max_cost - tmp_cost_same)/self.T) > random.uniform(0,1)):
                cost_minimisation = self.max_cost - tmp_cost_same
                chs = pt
                proof = tmp_proof
                print("minimisation of ", tmp_cost_same, self.T * pr.max_cost, pr.max_cost)
        if chs != None:
            print("sending proposal to",self.get_peer(chs).pub_key)
            self.send_proposal(chs, proof)
        else:
            print("No proposal")
        loop = asyncio.get_event_loop()
        self.refresh_loop = loop.call_later(2, self._periodic)



        
    async def start(self, p : Peer):
        await super().start(p)
        self.peers[p.id_node] = StagePeer(p,self.stage)
        self._periodic()


    
    @bindfrom("connected_callback")
    def add_peer(self, addr: tuple[str,int], p: Peer):
        loop = asyncio.get_event_loop()
        msg = bytearray([Arpegio.INTRODUCTION])
        msg += self.peer.id_node
        msg += self.stage.to_bytes(1, byteorder = "big")
        print("introducing")
        loop.create_task(self._lower_sendto(msg, p.addr))
        self.peer_connected(addr, p)
# TODO: Send your current costs
# TODO: remember other peer's costs when selecting them
# TODO: 