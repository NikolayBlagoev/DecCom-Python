import os
import pickle
from typing import Callable
from deccom.cryptofuncs.hash import SHA256
from deccom.peers.peer import Peer
from deccom.protocols.abstractprotocol import AbstractProtocol
from deccom.protocols.streamprotocol import StreamProtocol
from deccom.protocols.wrappers import *
import torch.nn as nn
from torch import zeros_like
import torch.nn.functional as F
import torch.optim as optim
from torch import tensor, mean, stack, cat, split
from datetime import datetime
import pickle
import asyncio

class PeerClassification:
    def __init__(self, peerid: bytes, delay: float) -> None:
        self.peerid: bytes = peerid
        self.delay = delay
        pass
    
class SwarmProtocol(AbstractProtocol):
    offers = dict(AbstractProtocol.offers, **{})
    bindings = dict(AbstractProtocol.bindings, **{
        
    })
    required_lower = AbstractProtocol.required_lower + \
        ["find_peer", "set_stream_callback",
            "open_connection", "send_stream", "get_peer", "get_peers", "connected_callback","disconnected_callback"]
    INTRODUCTION = int.from_bytes(b'\xd1', byteorder="big")
    COMPLETE = int.from_bytes(b'\xd8', byteorder="big")
    
    def __init__(self, pipeline_size, stage, net, optimizer, max_iterations = -1, microbatches = 1, loss_fn = None, get_data=None, submodule=None, callback: Callable[[tuple[str, int], bytes], None] = lambda : ...):
        
        super().__init__(submodule, callback)
        self.pipeline_size = pipeline_size
        self.stage = stage
        self.time_start = None
        self.microbatches = microbatches
        
        self.max_iterations = max_iterations
        if self.stage == 0:
            assert get_data != None
            assert loss_fn != None
            self.loss_fn = loss_fn
            self.get_data = get_data
        
        
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
        self.time_start = datetime.now()
        self.next_stage: dict[bytes,PeerClassification] = dict()
        self.sent: dict[bytes, dict[bytes,datetime]] = dict()
        self.outstanding: dict[bytes,asyncio.TimerHandle] = dict()
        self.same_stage = []
    @bindto("open_connection")
    async def _lower_open_connection(self, remote_ip, remote_port, node_id: bytes):
        return
    @bindto("send_stream")
    async def _lower_send_stream(self, node_id, data):
        return
    @bindto("get_peer")
    def _lower_get_peer(self, node_id)->Peer:
        return None
    
    @bindto("find_peer")
    async def _lower_find_peer(self, id: bytes) -> Peer:
        return None
    
    async def start(self, p: Peer):
        await super().start(p)
        if self.stage == 0: 
            loop = asyncio.get_event_loop()      
            loop.create_task(self.start_iteration())
    
    @bindfrom("connected_callback")
    def peer_connected(self, nodeid, peer: Peer):
        # print("NEW PEER")
        loop = asyncio.get_running_loop()

        msg = bytearray([SwarmProtocol.INTRODUCTION])
        msg = msg + int(self.stage).to_bytes(4,byteorder="big") + self.peer.id_node
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
        
        return choice
    async def send_forward(self,seq_id, inp, outp, prev_peer = None):
        if self.stage % self.pipeline_size == self.pipeline_size - 1:
            
            choice = PeerClassification(seq_id[0:32],0)
        else:
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
        ret = SwarmProtocol.train(self.net, self.optimizer, inp_batch=self.buffer_out.get(seq_id)[0], output=data, rank = self.stage, stage = -1)
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
            if peer == self.peer.id_node:
                continue
            loop.create_task(self.send_stream(peer,pickle.dumps(self.prev_grad),seqdata=seq_id)) 
        self.check_for_back()
        del self.buffer_in[seq_id]
        del self.buffer_out[seq_id]     
        return


    async def start_iteration(self):

        assert self.stage == 0
        ttl = (datetime.now() - self.time_start).total_seconds()
        print(ttl)
        self.time_start = datetime.now()
        for _ in range(self.microbatches):
            try:
                if self.iter == self.max_iterations:
                    print("TRAINING COMPLETE")
                    return
                self.time_start = datetime.now()
                data, target = self.get_data()
                    
                    
            except StopIteration :
                print("TRAINING COMPLETE")
                return
            
            new_seq_id = self.peer.id_node + os.urandom(4)
            while self.buffer_out.get(new_seq_id) != None:
                new_seq_id = self.peer.id_node + os.urandom(4)
            
            ret = SwarmProtocol.train(self.net,self.optimizer, data, rank = 0, stage=1)
            ret.retain_grad()
            #print("sending to next")
            self.buffer_out[new_seq_id] = ret
            await self.send_forward(new_seq_id, target, ret)
            
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
                    
                    
        tmp = SwarmProtocol.custom_avg(tmp)
        for i, param in enumerate(self.net.parameters()):
            param.data = param.data - 0.01*tmp[i].view(self.sizes[i])
        self.aggregation = []
    def timeout(self,seq_id):
        print("oops timed out",seq_id)
        nodeid = self.buffer_out[seq_id][1]
        # del self.next_stage[nodeid]
        if self.next_stage.get(nodeid) != None:
            self.next_stage[nodeid].delay = 8000000
        loop = asyncio.get_running_loop()
        loop.create_task(
            self.send_forward(seq_id,self.buffer_in[seq_id][0], self.buffer_out[seq_id][0], self.buffer_in[seq_id][1]))
        return
    def check_for_back(self):
        if len(self.aggregation) > self.microbatches * len(self.same_stage):
                print("CAN DO BACK", len(self.aggregation), len(self.same_stage))
                self._apply_grad()
                if self.stage == 0:
                    loop = asyncio.get_running_loop()
                    loop.create_task(self.start_iteration())
        
    @bindfrom("stream_callback")
    def process_data(self, data:bytes, nodeid, addr):
        
        seq_id = bytes(data[0:36])
        stage = int.from_bytes(data[36:40],byteorder="big")
        data = pickle.loads(data[40:])
        peer: Peer = self._lower_get_peer(nodeid)
        if stage == (self.stage + 1) % self.pipeline_size:
            # print("BACKWARDS")
            if self.buffer_in.get(seq_id) == None:
                print("NOT RECOGNISED BACKWARDS")
                return
            if self.stage == 0:
                SwarmProtocol.train(self.net,self.optimizer, inp_batch=self.buffer_out.get(seq_id)[0],output=data, rank = 0, stage = -1)
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
                
                self.send_back(seq_id,data)
        elif self.stage == stage:
            self.aggregation.append(data)
            print("collecting...\n\n\n\n")
            self.check_for_back()
            
        else:
            # if len(self.same_stage) >= 1 and self.peer.pub_key == "1":
            #     print("ME")
            #     exit()
            # if self.peer.pub_key == "4":
            #     print("FORWARDS")
            
            if self.stage == 0:
                loss = self.loss_fn(data,self.buffer_in.get(seq_id)[0])
                loss.backward()
                if self.iter % 10 == 0:
                    print(loss.item())
                loop = asyncio.get_running_loop()
                loop.create_task(self.send_stream(nodeid,pickle.dumps(data.grad),seqdata=seq_id))
                    
            else:
                
                    
                ret = SwarmProtocol.train(self.net,self.optimizer, inp_batch=data, rank = self.stage, stage = 1)
                ret.retain_grad()
                loop = asyncio.get_running_loop()
                loop.create_task(
                            self.send_forward(seq_id,data,ret,nodeid))
           
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
            if stage == self.stage:
                if nodeid not in self.same_stage:
                    self.same_stage.append(nodeid)
                    print("ADDING TO SAME STAGE")
            elif stage == (self.stage + 1) % self.pipeline_size:
                if self.next_stage.get(nodeid) == None:
                    self.next_stage[nodeid] = PeerClassification(nodeid, 0.5)
            return
        elif data[0] == SwarmProtocol.COMPLETE:
            # print("COMPLETE")
            if self.outstanding.get(data[1:]) == None:
                return
            self.outstanding[data[1:]].cancel()
            del self.outstanding[data[1:]]
            self.next_stage[self.buffer_out[data[1:]][1]].delay = 0.6 * self.next_stage[self.buffer_out[data[1:]][1]].delay + 0.4 * (datetime.now() - self.sent[self.buffer_out[data[1:]][1]][data[1:]]).seconds * 1000
            return
        else:
            super().process_datagram(addr, data[1:])
    async def send_stream(self, node_id, data, seqdata=b'', stage = None):
        # print("SENDING TO")
        if stage == None:
            stage = self.stage
        stage = int(stage).to_bytes(4,byteorder="big")
        p: Peer = await self._lower_find_peer(node_id)
        # print("FOUND PEER SENDING")
        
        
        
        
        
        ret = await self._lower_open_connection(p.addr[0], p.tcp, p.id_node)
        if not ret:
            return self.timeout(seqdata)
        to_send = seqdata + stage + data
        return await self._lower_send_stream(node_id, to_send)
        
        
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
                