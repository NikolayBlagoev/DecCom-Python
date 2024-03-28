import os
import pickle
from typing import Callable
from deccom.cryptofuncs.hash import SHA256
from deccom.peers.peer import Peer
from deccom.protocols.abstractprotocol import AbstractProtocol

import torch.nn as nn
import torch.nn.functional as F
from torch import tensor, mean, stack, cat, split, zeros_like
import pickle
from deccom.protocols.wrappers import *
from datetime import datetime

import asyncio
class PeerClassification:
    def __init__(self, peerid: bytes, delay: float) -> None:
        self.peerid: bytes = peerid
        self.delay = delay
        pass
    
    
class FaultProtocol(AbstractProtocol):
    offers = dict(AbstractProtocol.offers, **{})
    bindings = dict(AbstractProtocol.bindings, **{
        "process_data": "set_stream_callback",
        "_lower_find_peer": "find_peer",
        "_lower_open_connection": "open_connection",
        "_lower_send_stream": "send_stream",
        "_lower_get_peer": "get_peer",
        "peer_connected": "connected_callback",
        "_lower_get_peers": "get_peers",
        "peer_disconnected": "disconnected_callback"
    })
    required_lower = AbstractProtocol.required_lower + \
        ["find_peer", "set_stream_callback",
            "open_connection", "send_stream", "get_peer", "get_peers", "connected_callback","disconnected_callback"]
    INTRODUCTION = int.from_bytes(b'\xd1', byteorder="big")
    COMPLETE = int.from_bytes(b'\xd8', byteorder="big")
    BACK_COMPLETE = int.from_bytes(b'\xd7', byteorder="big")
    ALERT = int.from_bytes(b'\xd6', byteorder="big")
    PING = int.from_bytes(b'\xd5', byteorder="big")

    def __init__(self, rank, net, optimizer, dataloader=None, submodule=None, callback: Callable[[tuple[str, int], bytes], None] = ...):
        
        super().__init__(submodule, callback)
        
        self.rank = rank
        self.dataloader = dataloader
        
        self.paths = dict()
        self.net: nn.Module = net
        self.sizes = []
        if self.rank == 0:
            assert dataloader != None
            self.dataloader = enumerate(dataloader)
        self.len_sizes = []
        for param in self.net.parameters():
            self.sizes.append(param.shape)
            self.len_sizes.append(len(param.view(-1)))
        self.optimizer = optimizer
        self.buffer_in = dict()
        self.buffer_out = dict()
        self.aggregation = []
        self.prev_grad = None
        self.iter = 0
        self.outstanding_batches = dict()
        self.next_stage: dict[bytes,PeerClassification] = dict()
        self.sent: dict[bytes, dict[bytes,datetime]] = dict()
        self.same_stage = []
        self.outstanding: dict[bytes,asyncio.TimerHandle] = dict()
        self.forward_start = None
    @bindto("find_peer")
    async def _lower_find_peer(self, p: Peer):
        return None
    @bindto("open_connection")
    async def _lower_open_connection(self):
        return
    
    @bindto("get_peer")
    def _lower_get_peer(self, p: Peer):
        return None
    
    @bindfrom("connected_callback")
    def peer_connected(self, nodeid, peer: Peer):
        # print("NEW PEER")
        loop = asyncio.get_running_loop()
        
        
        msg = bytearray([FaultProtocol.INTRODUCTION])
        msg = msg + int(self.rank).to_bytes(4,byteorder="big") + self.peer.id_node
        loop.create_task(self.sendto(msg, peer.addr))
        return
    def choose_next(self,):
        choice = PeerClassification(None, 10000000000)
        if len(self.next_stage.items()) == 0:
            print("ooops... NO NEXT???")
            return None
        for idx,pr in self.next_stage.items():
            if pr.delay < choice.delay:
                choice = pr
        # print(choice.delay,len(self.next_stage.items()),choice.peerid)
        return choice
    async def send_forward(self,seq_id, inp, outp, prev_peer = None, resend = False, path: list = []):
        if len(path) < 6:
            path.append(bytes(self.peer.id_node))
        else:
            path[self.rank] = bytes(self.peer.id_node)
            nxtinline = path[(self.rank + 1) % 6]
            self.paths[seq_id] = path
            if int.from_bytes(nxtinline, byteorder="big") != 0:
                p: Peer = await self._lower_find_peer(nxtinline)
                print("next in line is ", p.pub_key)
                choice = self.next_stage.get(p.id_node)
                while choice == None:
                    await asyncio.sleep(2)
                    choice = self.next_stage.get(p.id_node)
                self.buffer_in[seq_id] = (inp, prev_peer)
                self.buffer_out[seq_id] = (outp,choice.peerid)
                if self.sent.get(choice.peerid) == None:
                    self.sent[choice.peerid] = dict()
                self.sent[choice.peerid][seq_id] = datetime.now()
                loop = asyncio.get_running_loop()
                loop.create_task(self.send_stream(choice.peerid,pickle.dumps(outp),seqdata=seq_id, path = path))
                timeout = loop.call_later(20,
                                            self.timeout, seq_id)
                
                self.outstanding[seq_id] = timeout
                return
        self.paths[seq_id] = path
        if self.rank % 6 == 5:
            print("looking for", seq_id[0])
            choice = PeerClassification(SHA256(str(seq_id[0])),0)
        else:
            
            choice = self.choose_next()
            if resend:
                outp,choice = self.buffer_out.get(seq_id)
                choice = self.next_stage.get(choice)
            else:
                while choice == None:
                    print("eeeping....")
                    await asyncio.sleep(3)
                    choice = self.choose_next()
        print("sending to",self._lower_get_peer(choice.peerid).pub_key)
        self.buffer_in[seq_id] = (inp, prev_peer)
        self.buffer_out[seq_id] = (outp,choice.peerid)
        if self.sent.get(choice.peerid) == None:
            self.sent[choice.peerid] = dict()
        self.sent[choice.peerid][seq_id] = datetime.now()
        loop = asyncio.get_running_loop()
        loop.create_task(self.send_stream(choice.peerid,pickle.dumps(outp),seqdata=seq_id, path=path))
        timeout = loop.call_later(20,
                                      self.timeout, seq_id)
        self.outstanding[seq_id] = timeout
    def send_back(self, seq_id, data, path):
        ret = FaultProtocol.train(self.net, self.optimizer, inp_batch=self.buffer_out.get(seq_id)[0], output=data, rank = self.rank, stage = -1)
        self._helper_back(seq_id, path)
        # loop = asyncio.get_running_loop()
        # loop.create_task(self.send_stream(self.buffer_in.get(seq_id)[1],pickle.dumps(self.buffer_in.get(seq_id)[0].grad),seqdata=seq_id))
        tmp = []
        
        for param in self.net.parameters():
            if param.grad == None:
                tmp.append(zeros_like(param.data).view(-1))
                
                continue
            tmp.append(param.grad.view(-1))
            
        loop = asyncio.get_running_loop()
        self.prev_grad = cat(tmp)
        self.aggregation.append(self.prev_grad)
        for peer in self.same_stage:
            if peer == self.peer.id_node:
                continue
            loop.create_task(self.send_stream(peer,pickle.dumps(self.prev_grad),seqdata=seq_id)) 
        if len(self.aggregation) > len(self.same_stage):
                    print("CAN DO BACK", len(self.aggregation), len(self.same_stage))
                    self._apply_grad()  
             
        return
    @bindto("get_peers")
    def get_peers(self):
        return None
    async def start(self, p: Peer):
        await super().start(p)
        
        for _,p in self.get_peers():
            # print("introducing to ",p.addr)
            msg = bytearray([FaultProtocol.INTRODUCTION])
            msg = msg  + int(self.rank).to_bytes(4,byteorder="big") + self.peer.id_node
            await self._lower_sendto(msg, p.addr)
        if self.rank == 0: 
            self.forward_start = datetime.now()
            try:
                    if self.iter > 25:
                        print("finished training")
                        return
                    batch_idx, ret = next(self.dataloader)
                    data = ret['text']
                    target = ret['text']
            except StopIteration :
                    print("TRAINING COMPLETE")
                    return
            
            new_seq_id = bytearray()
            new_seq_id = int(self.peer.pub_key).to_bytes(1, byteorder="big") + os.urandom(7)
            new_seq_id = bytes(new_seq_id)
            while self.buffer_out.get(new_seq_id) != None:
                    new_seq_id = bytearray()
                    new_seq_id = int(self.peer.pub_key).to_bytes(1, byteorder="big") + os.urandom(7)
                    new_seq_id = bytes(new_seq_id)
            ret = FaultProtocol.train(self.net,self.optimizer, data, rank = 0, stage=1)
            ret.retain_grad()
            await self.send_forward(new_seq_id,target, ret)
    @bindfrom("disconnected_callback")
    def peer_disconnected(self,addr, node_id):
        if node_id in self.same_stage:
            self.same_stage.remove(node_id)
            self.check_for_back()
        if self.next_stage.get(node_id) != None:
            del self.next_stage[node_id]
    def _apply_grad(self):
        # print("applyinb back")
        self.iter += 1
        tmp = []
        for p in self.aggregation:
                        
            tmp.append(split(p, self.len_sizes))
                    
                    
        tmp = FaultProtocol.custom_avg(tmp)
        for i, param in enumerate(self.net.parameters()):
            param.data = param.data - 0.01*tmp[i].view(self.sizes[i])
        self.aggregation = []
    def timeout(self,seq_id):
        print("oops timed out",seq_id)
        nodeid = self.buffer_out[seq_id][1]
        rt = nodeid
        if rt != None:
            rt = self._lower_get_peer(nodeid)
        if rt == None:
            print("I DO NOT KNOW THIS MAN")
        else:
            print(self.peer.pub_key,rt.pub_key, "timed out /")
        if len(self.paths[seq_id]) >= 6:
            self.paths[seq_id][(self.rank + 1)%6] = int(0).to_bytes(32, byteorder="big")
        if self.next_stage.get(nodeid) != None:
            self.next_stage[nodeid].delay = float("inf")
            del self.next_stage[nodeid]
        loop = asyncio.get_running_loop()
        loop.create_task(
            self.send_forward(seq_id,self.buffer_in[seq_id][0], self.buffer_out[seq_id][0], self.buffer_in[seq_id][1], path=self.paths[seq_id]))
        return
    
    def dataholder_timeout(self,seq_id):
        print("oops missing batch out",seq_id)
        
        # nodeid = self.buffer_out[seq_id][1]
        # del self.next_stage[nodeid]
        # if self.next_stage.get(nodeid) != None:
        #     self.next_stage[nodeid].delay = 8000000
        loop = asyncio.get_running_loop()
        loop.create_task(
            self.send_forward(seq_id,self.buffer_in[seq_id][0], self.buffer_out[seq_id][0], self.buffer_in[seq_id][1], True))
        return
    def check_for_back(self):
        if len(self.aggregation) > len(self.same_stage):
                print("CAN DO BACK", len(self.aggregation), len(self.same_stage))
                self._apply_grad()
                if self.rank == 0:
                    if self.forward_start!= None:
                        print("TIME IT TOOK", (datetime.now() - self.forward_start).seconds)
                    self.forward_start = datetime.now()
                    try:
                        if self.iter > 25:
                            print("finished training")
                            return
                        batch_idx, ret = next(self.dataloader)
                        data = ret['text']
                        target = ret['text']
                    except StopIteration :
                        print("TRAINING COMPLETE")
                        return
                    new_seq_id = bytearray()
                    new_seq_id = int(self.peer.pub_key).to_bytes(1, byteorder="big") + os.urandom(7)
                    new_seq_id = bytes(new_seq_id)
                    while self.buffer_out.get(new_seq_id) != None:
                        new_seq_id = bytearray()
                        new_seq_id = int(self.peer.pub_key).to_bytes(1, byteorder="big") + os.urandom(7)
                        new_seq_id = bytes(new_seq_id)
                    self.paths[new_seq_id] = []
                    ret = FaultProtocol.train(self.net,self.optimizer, data, rank = 0, stage=1)
                    ret.retain_grad()
                    loop = asyncio.get_running_loop()
                    loop.create_task(
                            self.send_forward(new_seq_id,target, ret, path=[]))
    
    def alert_dataholder(self, seq_id):
        msg = bytearray([FaultProtocol.ALERT])
        msg += seq_id
        loop = asyncio.get_event_loop()
        loop.create_task(self._alert(msg, seq_id))
    async def _alert(self, msg, seq_id):
        print("looking for",str(seq_id[0]))
        p: Peer = await self._lower_find_peer(SHA256(str(seq_id[0])))
        await self._lower_sendto(msg, p.addr)

    def _helper_back(self, seq_id, path):
        loop = asyncio.get_running_loop()

        loop.create_task(self.send_stream(bytes(path[self.rank-1]),pickle.dumps(self.buffer_in.get(seq_id)[0].grad),seqdata=seq_id,path=path))
        timeout = loop.call_later(20,
                                      self.back_timeout, seq_id)
        self.outstanding[seq_id] = timeout
        print("setting timeout for ", seq_id)
    def back_timeout(self,seq_id):
        print("oops timed out backwards",seq_id)
        nodeid = self.buffer_in[seq_id][1]
        # del self.next_stage[nodeid]
        if self.next_stage.get(nodeid) != None:
            self.next_stage[nodeid].delay = 8000000
        
        self.alert_dataholder(seq_id)
    @bindfrom("stream_callback")
    def process_data(self, data:bytes, nodeid, addr):
        seq_id = bytes(data[0:8])
        stage = int.from_bytes(data[8:12],byteorder="big")
        pth_l = data[12]
        path = []
        i = 13
        for _ in range(pth_l):
            path.append(data[i: i+32])
            i += 32
        print(seq_id, len(path))
        # print("\n\n\n",seq_id,"\n\n\n")
        data=pickle.loads(data[i:])
        peer: Peer = self._lower_get_peer(nodeid)
        if stage == (self.rank + 1)% 6:
            if len(self.same_stage) >= 1 and self.peer.pub_key == "4" and self.iter > 5:
                print("ME")
                exit()
            # print("BACKWARDS")
            if self.buffer_in.get(seq_id) == None:
                print("NOT RECOGNISED BACKWARDS")
                return
            if self.rank == 0:
                
                self.send_complete_back(seq_id, nodeid)
                self.paths[seq_id] = path
                FaultProtocol.train(self.net,self.optimizer, inp_batch=self.buffer_out.get(seq_id)[0],output=data, rank = 0, stage = -1)
                tmp = []
                
                for param in self.net.parameters():
                    if param.grad == None:
                        tmp.append(zeros_like(param.data).view(-1))
                        
                        continue
                    tmp.append(param.grad.view(-1))
                loop = asyncio.get_running_loop()
                self.prev_grad = cat(tmp)
                for peer in self.same_stage:
                    if peer == self.peer.id_node:
                        continue
                    loop.create_task(self.send_stream(peer,pickle.dumps(self.prev_grad),seqdata=seq_id))
                    
                self.aggregation.append(self.prev_grad)
                
                self.check_for_back()
            else:
                
                self.send_back(seq_id,data, path)
                self.send_complete_back(seq_id, nodeid)
        elif self.rank == stage:
            self.aggregation.append(data)
            # print("collecting...\n\n\n\n")
            self.check_for_back()
            
        else:
            
            if self.peer.pub_key == "4":
                print("FORWARDS")
            
            if self.rank == 0:
                self.paths[seq_id] = path
                loss = self.net.task_layer(data,self.buffer_in.get(seq_id)[0])
                loss.backward()
                if self.iter % 10 == 0:
                    print(loss.item())
                loop = asyncio.get_running_loop()
                loop.create_task(self.send_stream(nodeid,pickle.dumps(data.grad),seqdata=seq_id, path = path))
                    
            else:
                if self.buffer_in.get(seq_id) != None:
                    # need to resend
                    self.send_complete(seq_id,nodeid)
                    self._helper_back(seq_id,path)
                    return
                if self.forward_start!= None:
                    print("TIME IT TOOK", (datetime.now() - self.forward_start).seconds)
                self.forward_start = datetime.now()
                    
                ret = FaultProtocol.train(self.net,self.optimizer, inp_batch=data, rank = self.rank, stage = 1)
                ret.retain_grad()
                loop = asyncio.get_running_loop()
                loop.create_task(
                            self.send_forward(seq_id,data,ret,nodeid, path = path))
           
            self.send_complete(seq_id,nodeid)
            # loop.create_task(self.se)  
        return
    def send_complete_back(self, seq_id, nodeid):
        loop = asyncio.get_running_loop()
        
        peer: Peer = self._lower_get_peer(nodeid)
        msg = bytearray([FaultProtocol.BACK_COMPLETE])
        msg = msg +  seq_id
        loop.create_task(self.sendto(msg, peer.addr))
    def send_complete(self, seq_id, nodeid):
        loop = asyncio.get_running_loop()
        
        peer: Peer = self._lower_get_peer(nodeid)
        msg = bytearray([FaultProtocol.COMPLETE])
        msg = msg +  seq_id
        loop.create_task(self.sendto(msg, peer.addr))
    async def sendto(self, msg, addr):
        await self._lower_sendto(msg,addr)
    def process_datagram(self, addr: tuple[str, int], data: bytes):
        if data[0] == FaultProtocol.INTRODUCTION:
            
            stage = int.from_bytes(data[1:5], byteorder="big")
            nodeid = data[5:]
            # if self._lower_get_peer(nodeid)!= None:
            #     print("INTRODUCTION FROM",self._lower_get_peer(nodeid).pub_key)
            # else:
            #     print("FAST INTRODUCTION")
            if stage == self.rank:
                if nodeid not in self.same_stage:
                    self.same_stage.append(nodeid)
                    print("ADDING TO SAME STAGE")
            elif stage == (self.rank + 1) % 6:
                if self.next_stage.get(nodeid) == None:
                    self.next_stage[nodeid] = PeerClassification(nodeid, 15000.0)
            return
        elif data[0] == FaultProtocol.COMPLETE:
            # print("COMPLETE")
            self.outstanding[data[1:]].cancel()
            del self.outstanding[data[1:]]
            print(self.buffer_out.get(data[1:]) == None)
            try:
                self.next_stage[self.buffer_out[data[1:]][1]].delay = 0.6 * self.next_stage[self.buffer_out[data[1:]][1]].delay + 0.4 * (datetime.now() - self.sent[self.buffer_out[data[1:]][1]][data[1:]]).seconds * 1000
            except:
                print("ignored")
            # if self.rank == 0:
            #     print("setting timeout for lost batch")
            #     loop = asyncio.get_event_loop()
            #     self.outstanding_batches[data[1:]] = loop.call_later(90, self.dataholder_timeout, data[1:])
            return
        elif data[0] == FaultProtocol.BACK_COMPLETE:
            print("successful back")
            if self.outstanding.get(data[1:])== None:
                return
            self.outstanding[data[1:]].cancel()
            del self.outstanding[data[1:]]
            del self.buffer_in[data[1:]]
            del self.buffer_out[data[1:]]
            return
        elif data[0] == FaultProtocol.PING:
            seq_id = data[1:9]
            i = 9
            pth = []
            while i < len(data):
                pth.append(data[i:i+32])
                i+=32
            self.paths[seq_id] = pth
            self.send_complete(seq_id, self.buffer_in[seq_id][1])
            print("received ping path ", len(pth))
            self.send_ping(seq_id, pth)
        elif data[0] == FaultProtocol.ALERT:
            print("RECEIVED ALERT")
            if self.rank != 0:
                return
            pth = self.paths.get(data[1:])
            if pth == None:
                return
            self.send_ping(data[1:], pth)
        else:
            super().process_datagram(addr, data)
    def send_ping(self, seq_id, pth):
        nxt = self.buffer_out[seq_id]
        loop = asyncio.get_event_loop()
        msg = bytearray([FaultProtocol.PING])
        msg += seq_id
        for p in pth:
            msg += p
        loop.create_task(self._lower_sendto(msg, self._lower_get_peer(self.buffer_out[seq_id][1]).addr))
        timeout = loop.call_later(20,
                                      self.timeout, seq_id)
        self.outstanding[seq_id] = timeout    
    @bindto("send_stream")
    async def _lower_send_stream(self, node_id, data):
        return
    async def send_stream(self, node_id, data, seqdata=b'', stage = None, path = []):
        if stage == None:
            stage = self.rank
        stage = int(stage).to_bytes(4,byteorder="big")
        pth_len  = int(len(path)).to_bytes(1, byteorder="big")

        # print("SENDING TO")
        p: Peer = await self._lower_find_peer(node_id)
        print("FOUND PEER SENDING TO",p.pub_key)
        if seqdata == b'':
            print("if seqdata", seqdata)
            return
        ret = await self._lower_open_connection(p.addr[0], p.tcp, p.id_node)
        if not ret:
            if self.next_stage.get(node_id) != None:
                self.next_stage[node_id].delay = float("inf")
            print("couldn't open connection for some reason to",p.pub_key)
            return
        to_send = bytearray(seqdata)
        to_send += stage + pth_len
        for p in path:
            to_send += p
        to_send += data
        await self._lower_send_stream(node_id, to_send)
        return
    def get_lowest_stream(self):
        submodule = self.submodule
        while submodule != None and not hasattr(submodule, "get_lowest_stream") and hasattr(submodule, "submodule") :
            submodule = submodule.submodule
        if submodule != None and hasattr(submodule, "get_lowest_stream"):
            ret = submodule.get_lowest_stream()
            if ret == None:
                return self
            else:
                return ret
        else:
            
            return self

    def custom_avg(list_of_tensors):
        new_gradients = []
        for i in range(len(list_of_tensors[0])):
            tmp = []
            for p in range(len(list_of_tensors)):
                tmp.append(list_of_tensors[p][i])
            tmp = stack(tmp)
            new_gradients.append(mean(tmp,dim=0))
        return new_gradients
    def train(net, optimizer, inp_batch, stage, rank, output = None):
        if rank != 0:
            if stage == 1:

                return net(inp_batch)
            else:
                optimizer.zero_grad()
                try:
                    
                    inp_batch.backward(output)
                except:
                    print(inp_batch)
                    exit()
                
                # optimizer.step()
                if rank !=0:
                    return inp_batch.grad
        else:
            if stage == 1:

                return net(inp_batch)
            else:
                optimizer.zero_grad()
                inp_batch.backward(output)
                # loc_count+=1
                # optimizer.step()
            
                