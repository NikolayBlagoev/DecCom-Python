import os
import pickle
from typing import Callable
from deccom.cryptofuncs.hash import SHA256
from deccom.peers.peer import Peer
from deccom.protocols.abstractprotocol import AbstractProtocol
from deccom.protocols.streamprotocol import StreamProtocol
import torch.nn as nn
import torch.nn.functional as F
from torch import tensor, mean, stack, cat, split, zeros_like
import pickle
from datetime import datetime

import asyncio
class PeerClassification:
    def __init__(self, peerid: bytes, delay: float) -> None:
        self.peerid: bytes = peerid
        self.delay = delay
        pass
    
    
class SwarmProtocol(AbstractProtocol):
    offers = dict(AbstractProtocol.offers, **{})
    bindings = dict(AbstractProtocol.bindings, **{
        "process_data": "set_stream_callback",
        "_lower_find_peer": "find_peer",
        "_lower_open_connection": "open_connection",
        "_lower_send_stream": "send_stream",
        "_lower_get_peer": "get_peer",
        "peer_connected": "set_connected_callback",
        "_lower_get_peers": "get_peers"
    })
    required_lower = AbstractProtocol.required_lower + \
        ["find_peer", "set_stream_callback",
            "open_connection", "send_stream", "get_peer", "get_peers", "set_connected_callback"]
    INTRODUCTION = int.from_bytes(b'\xd1', byteorder="big")
    COMPLETE = int.from_bytes(b'\xd8', byteorder="big")
    

    def __init__(self, rank, net, optimizer, dataloader=None, submodule=None, callback: Callable[[tuple[str, int], bytes], None] = ...):
        
        super().__init__(submodule, callback)
        
        self.rank = rank
        self.dataloader = dataloader
        self._lower_find_peer = lambda: ...
        self._lower_open_connection = lambda: ...
        self._lower_send_stream = lambda: ...
        self._lower_get_peer = lambda: ...
        self._lower_get_peers = lambda: ...
        self.net: nn.Module = net
        self.sizes = []
        
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
        self.next_stage: dict[bytes,PeerClassification] = dict()
        self.sent: dict[bytes, dict[bytes,datetime]] = dict()
        self.same_stage = []
        self.outstanding: dict[bytes,asyncio.TimerHandle] = dict()
    def peer_connected(self, nodeid):
        # print("NEW PEER")
        loop = asyncio.get_running_loop()
        
        peer: Peer = self._lower_get_peer(nodeid)
        msg = bytearray([SwarmProtocol.INTRODUCTION])
        msg = msg + int(self.rank).to_bytes(4,byteorder="big") + Peer.me.id_node
        loop.create_task(self.sendto(msg, peer.addr))
        return
    def choose_next(self,):
        choice = PeerClassification(None, 10000000000)
        if len(self.next_stage.items()) == 0:
            # print("ooops... NO NEXT???")
            return None
        for idx,pr in self.next_stage.items():
            if pr.delay < choice.delay:
                choice = pr
        # print(choice.delay,len(self.next_stage.items()),choice.peerid)
        return choice
    async def send_forward(self,seq_id, inp, outp, prev_peer = None):
        choice = self.choose_next()
        while choice == None:
            # print("eeeping....")
            await asyncio.sleep(3)
            choice = self.choose_next()
        self.buffer_in[seq_id] = (inp, prev_peer)
        self.buffer_out[seq_id] = (outp,choice.peerid)
        if self.sent.get(choice.peerid) == None:
            self.sent[choice.peerid] = dict()
        self.sent[choice.peerid][seq_id] = datetime.now()
        loop = asyncio.get_running_loop()
        loop.create_task(self.send_stream(choice.peerid,pickle.dumps(outp),seqdata=seq_id))
        timeout = loop.call_later(20,
                                      self.timeout, seq_id)
        self.outstanding[seq_id] = timeout
    def send_back(self, seq_id, data):
        ret = SwarmProtocol.train(self.net, self.optimizer, inp_batch=self.buffer_out.get(seq_id)[0], output=data, rank = self.rank, stage = -1)
        loop = asyncio.get_running_loop()
        loop.create_task(self.send_stream(self.buffer_in.get(seq_id)[1],pickle.dumps(self.buffer_in.get(seq_id)[0].grad),seqdata=seq_id))
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
            if peer == Peer.me.id_node:
                continue
            loop.create_task(self.send_stream(peer,pickle.dumps(self.prev_grad),seqdata=seq_id)) 
        if len(self.aggregation) >= len(self.same_stage):
                    self._apply_grad()  
        del self.buffer_in[seq_id]
        del self.buffer_out[seq_id]     
        return
    async def start(self):
        await super().start()
        peers = self._lower_get_peers()
        for _,p in peers.items():
            # print("introducing to ",p.addr)
            msg = bytearray([SwarmProtocol.INTRODUCTION])
            msg = msg  + int(self.rank).to_bytes(4,byteorder="big") + Peer.me.id_node
            await self._lower_sendto(msg, p.addr)
        if self.rank == 0: 
            try:
                    if self.iter > 10:
                        print("finished training")
                        return
                    batch_idx, ret = next(self.dataloader)
                    data = ret['text']
                    target = ret['text']
            except StopIteration :
                    print("TRAINING COMPLETE")
                    return
            
            new_seq_id = os.urandom(8)
            while self.buffer_out.get(new_seq_id) != None:
                    new_seq_id = os.urandom(8)
            ret = SwarmProtocol.train(self.net,self.optimizer, data, rank = 0, stage=1)
            ret.retain_grad()
            await self.send_forward(new_seq_id,target, ret)
        
    def _apply_grad(self):
        # print("applyinb back")
        self.iter += 1
        tmp = []
        for p in self.aggregation:
                        
            tmp.append(split(p, self.len_sizes))
                    
                    
        tmp = SwarmProtocol.custom_avg(tmp)
        for i, param in enumerate(self.net.parameters()):
            param.data = param.data - 0.01*tmp[i].view(self.sizes[i])
        self.aggregation = []
    def timeout(self,seq_id):
        print("oops timed out",seq_id)
        nodeid = self.buffer_out[seq_id][1]
        # del self.next_stage[nodeid]
        self.next_stage[nodeid].delay = 8000000
        loop = asyncio.get_running_loop()
        loop.create_task(
            self.send_forward(seq_id,self.buffer_in[seq_id][0], self.buffer_out[seq_id][0], self.buffer_in[seq_id][1]))
        return
    def process_data(self, data:bytes, nodeid, addr):
        seq_id = bytes(data[0:8])
        stage = int.from_bytes(data[8:12],byteorder="big")
        # print("\n\n\n",seq_id,"\n\n\n")
        data=pickle.loads(data[12:])
        peer: Peer = self._lower_get_peer(nodeid)
        if stage == (self.rank + 1)%3:
            # print("BACKWARDS")
            if self.buffer_in.get(seq_id) == None:
                print("NOT RECOGNISED BACKWARDS")
                return
            if self.rank == 0:
                SwarmProtocol.train(self.net,self.optimizer, inp_batch=self.buffer_out.get(seq_id)[0],output=data, rank = 0, stage = -1)
                tmp = []
                self.len_sizes = []
                for param in self.net.parameters():
                    tmp.append(param.grad.view(-1))
                    self.len_sizes.append(len(tmp[-1]))
                loop = asyncio.get_running_loop()
                self.prev_grad = cat(tmp)
                for peer in self.same_stage:
                    if peer == Peer.me.id_node:
                        continue
                    loop.create_task(self.send_stream(peer,pickle.dumps(self.prev_grad),seqdata=seq_id))
                    
                self.aggregation.append(self.prev_grad)
                
                if len(self.aggregation) >= len(self.same_stage):
                    self._apply_grad()
                    # print("\n\n\n\ncalculated")
                    # if self.iter > 3:
                    #     print("TRAINING COMPLETE")
                    #     return
                    try:
                        if self.iter > 10:
                            print("finished training")
                            return
                        batch_idx, ret = next(self.dataloader)
                        data = ret['text']
                        target = ret['text']
                    except StopIteration :
                        print("TRAINING COMPLETE")
                        return
                    del self.buffer_in[seq_id]
                    del self.buffer_out[seq_id]
                    new_seq_id = os.urandom(8)
                    while self.buffer_out.get(new_seq_id) != None:
                        new_seq_id = os.urandom(8)
                    
                    ret = SwarmProtocol.train(self.net,self.optimizer, data, rank = 0, stage=1)
                    ret.retain_grad()
                    loop = asyncio.get_running_loop()
                    loop.create_task(
                                self.send_forward(new_seq_id,target, ret))
            else:
                
                self.send_back(seq_id,data)
        elif self.rank == stage:
            self.aggregation.append(data)
            print("collecting...\n\n\n\n")
            if len(self.aggregation) >= len(self.same_stage):
                self._apply_grad()
                if self.rank == 0:
                    try:
                        if self.iter > 10:
                            print("finished training")
                            return
                        batch_idx, ret = next(self.dataloader)
                        data = ret['text']
                        target = ret['text']
                    except StopIteration :
                        print("TRAINING COMPLETE")
                        return
                    new_seq_id = os.urandom(8)
                    while self.buffer_out.get(new_seq_id) != None:
                        new_seq_id = os.urandom(8)
                    
                    ret = SwarmProtocol.train(self.net,self.optimizer, data, rank = 0, stage=1)
                    ret.retain_grad()
                    loop = asyncio.get_running_loop()
                    loop.create_task(
                            self.send_forward(new_seq_id,target, ret))
        else:
            if len(self.same_stage) >= 1 and Peer.get_current().pub_key == "1":
                print("ME")
                exit()
            if Peer.get_current().pub_key == "4":
                print("FORWARDS")
            try:
                if self.rank == 0:
                    loss = self.net.task_layer(data,self.buffer_in.get(seq_id)[0])
                    loss.backward()
                    if self.iter % 10 == 0:
                        print(loss.item())
                    loop = asyncio.get_running_loop()
                    loop.create_task(self.send_stream(nodeid,pickle.dumps(data.grad),seqdata=seq_id))
                    
                else:
                    
                    
                    ret = SwarmProtocol.train(self.net,self.optimizer, inp_batch=data, rank = self.rank, stage = 1)
                    ret.retain_grad()
                    loop = asyncio.get_running_loop()
                    loop.create_task(
                            self.send_forward(seq_id,data,ret,nodeid))
            except Exception as e:
                print("ERROR IN TRAINING?!",e.with_traceback())
                exit()
            self.send_complete(seq_id,nodeid)
            # loop.create_task(self.se)  
        return
    def send_complete(self, seq_id, nodeid):
        loop = asyncio.get_running_loop()
        
        peer: Peer = self._lower_get_peer(nodeid)
        msg = bytearray([SwarmProtocol.COMPLETE])
        msg = msg +  seq_id
        loop.create_task(self.sendto(msg, peer.addr))
    async def sendto(self, msg, addr):
        await self._lower_sendto(msg,addr)
    def process_datagram(self, addr: tuple[str, int], data: bytes):
        if data[0] == SwarmProtocol.INTRODUCTION:
            
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
            elif stage == (self.rank + 1) % 3:
                if self.next_stage.get(nodeid) == None:
                    self.next_stage[nodeid] = PeerClassification(nodeid, 15000.0)
            return
        elif data[0] == SwarmProtocol.COMPLETE:
            # print("COMPLETE")
            self.outstanding[data[1:]].cancel()
            del self.outstanding[data[1:]]
            self.next_stage[self.buffer_out[data[1:]][1]].delay = 0.6 * self.next_stage[self.buffer_out[data[1:]][1]].delay + 0.4 * (datetime.now() - self.sent[self.buffer_out[data[1:]][1]][data[1:]]).seconds * 1000
            return
        else:
            super().process_datagram(addr, data)
        
    async def send_stream(self, node_id, data, seqdata=b'', stage = None):
        if stage == None:
            stage = self.rank
        stage = int(stage).to_bytes(4,byteorder="big")
        # print("SENDING TO")
        p: Peer = await self._lower_find_peer(node_id)
        # print("FOUND PEER SENDING")
        if seqdata == b'':
            print("if seqdata", seqdata)
        await self._lower_open_connection(p.addr[0], p.tcp, p.id_node)
        to_send = bytearray(seqdata)
        to_send += stage + data
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
                inp_batch.backward(output)
                
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
            
                