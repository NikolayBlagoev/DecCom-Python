import os
import pickle
from typing import Callable
from deccom.cryptofuncs.hash import SHA256
from deccom.peers.peer import Peer
from deccom.protocols.abstractprotocol import AbstractProtocol
from deccom.protocols.streamprotocol import StreamProtocol
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from torch import tensor, mean, stack, cat, split
import pickle
import asyncio
class TrainingProtocol(AbstractProtocol):
    offers = dict(AbstractProtocol.offers, **{})
    bindings = dict(AbstractProtocol.bindings, **{
        "process_data": "set_stream_callback",
        "_lower_find_peer": "find_peer",
        "_lower_open_connection": "open_connection",
        "_lower_send_stream": "send_stream",
        "_lower_get_peer": "get_peer"
    })
    required_lower = AbstractProtocol.required_lower + \
        ["find_peer", "set_stream_callback",
            "open_connection", "send_stream", "get_peer"]

    def __init__(self, world_size, pipeline_size, rank, net, optimizer, dataloader=None, submodule=None, callback: Callable[[tuple[str, int], bytes], None] = ...):
        assert world_size % pipeline_size == 0
        super().__init__(submodule, callback)
        self.world_size = world_size
        self.pipeline_size = pipeline_size
        self.rank = rank
        self.dp_group = []

        self.pipeline = rank // pipeline_size
        self.pipeline_rank = rank % pipeline_size
        
        if self.pipeline_rank == 0:
            assert dataloader != None
            self.dataloader = enumerate(dataloader)
            self.next = SHA256(str(self.rank + 1))
            self.prev = SHA256(str(self.rank + self.pipeline_size - 1))
        elif self.pipeline_rank == self.pipeline_size - 1:
            self.next = SHA256(str(self.rank - self.pipeline_size + 1))
            self.prev = SHA256(str(self.rank-1))
        else:
            self.prev = SHA256(str(self.rank - 1))
            self.next = SHA256(str(self.rank + 1))

        dp_member = self.rank
        self.dp_group.append(SHA256(str(dp_member)))
        dp_member = (dp_member + pipeline_size) % world_size
        while dp_member != self.rank:
            self.dp_group.append(SHA256(str(dp_member)))
            dp_member = (dp_member + pipeline_size) % world_size
            
        self._lower_find_peer = lambda: ...
        self._lower_open_connection = lambda: ...
        self._lower_send_stream = lambda: ...
        self._lower_get_peer = lambda: ...
        self.net: nn.Module = net
        self.sizes = []
        self.len_sizes = []
        for param in self.net.parameters():
            self.sizes.append(param.shape)
        self.optimizer = optimizer
        self.buffer_in = dict()
        self.buffer_out = dict()
        self.aggregation = []
        self.prev_grad = None
        self.iter = 0
        print(self.pipeline_rank, self.rank,self.dp_group)
    async def start(self):
        await super().start()
        if self.pipeline_rank == 0: 
            try:
                    batch_idx, (data, target) = next(self.dataloader)
            except StopIteration :
                    print("TRAINING COMPLETE")
                    return
                
            new_seq_id = os.urandom(8)
            while self.buffer_out.get(new_seq_id) != None:
                    new_seq_id = os.urandom(8)
            self.buffer_in[new_seq_id] = target
            ret = TrainingProtocol.train(self.net,self.optimizer, data, rank = 0, stage=1)
            ret.retain_grad()
            print("sending to next")
            self.buffer_out[new_seq_id] = ret
            loop = asyncio.get_running_loop()
            loop.create_task(self.send_stream(self.next,pickle.dumps(ret),seqdata=new_seq_id))
    def _apply_grad(self):
        # print("applyinb back")
        self.iter += 1
        tmp = []
        for p in self.aggregation:
                        
            tmp.append(split(p, self.len_sizes))
                    
                    
        tmp = TrainingProtocol.custom_avg(tmp)
        for i, param in enumerate(self.net.parameters()):
            param.data = param.data - 0.01*tmp[i].view(self.sizes[i])
        self.aggregation = []

    def process_data(self, data:bytes, nodeid, addr):
        seq_id = bytes(data[0:8])
        # print("\n\n\n",seq_id,"\n\n\n")
        data=pickle.loads(data[8:])
        peer: Peer = self._lower_get_peer(nodeid)
        if nodeid == self.prev:
            if self.pipeline_rank == 0:
                loss = F.cross_entropy(data, self.buffer_in.get(seq_id))
                loss.backward()
                if self.iter % 100 == 0:
                    print(loss.item())
                loop = asyncio.get_running_loop()
                loop.create_task(self.send_stream(self.prev,pickle.dumps(data.grad),seqdata=seq_id))
                
            else:
                self.buffer_in[seq_id] = data
                
                ret = TrainingProtocol.train(self.net,self.optimizer, inp_batch=data, rank = self.pipeline_rank, stage = 1)
                ret.retain_grad()
                self.buffer_out[seq_id] = ret
                loop = asyncio.get_running_loop()
                loop.create_task(self.send_stream(self.next,pickle.dumps(ret),seqdata=seq_id))
                
                
                
        elif nodeid == self.next:
            if self.pipeline_rank == 0:
                TrainingProtocol.train(self.net,self.optimizer, inp_batch=self.buffer_out.get(seq_id),output=data, rank = 0, stage = -1)
                tmp = []
                self.len_sizes = []
                for param in self.net.parameters():
                    tmp.append(param.grad.view(-1))
                    self.len_sizes.append(len(tmp[-1]))
                loop = asyncio.get_running_loop()
                self.prev_grad = cat(tmp)
                for peer in self.dp_group:
                    if peer == Peer.me.id_node:
                        continue
                    loop.create_task(self.send_stream(peer,pickle.dumps(self.prev_grad),seqdata=seq_id))
                    
                self.aggregation.append(self.prev_grad)
                # print("calculating\n\n\n\n",len(self.dp_group))
                if len(self.aggregation) == len(self.dp_group):
                    self._apply_grad()
                    # print("\n\n\n\ncalculated")
                    try:
                        batch_idx, (data, target) = next(self.dataloader)
                    except StopIteration :
                        print("TRAINING COMPLETE")
                        return
                    del self.buffer_in[seq_id]
                    del self.buffer_out[seq_id]
                    new_seq_id = os.urandom(8)
                    while self.buffer_out.get(new_seq_id) != None:
                        new_seq_id = os.urandom(8)
                    self.buffer_in[new_seq_id] = target
                    ret = TrainingProtocol.train(self.net,self.optimizer, data, rank = 0, stage=1)
                    ret.retain_grad()
                    self.buffer_out[new_seq_id] = ret
                    loop = asyncio.get_running_loop()
                    loop.create_task(self.send_stream(self.next,pickle.dumps(ret),seqdata=new_seq_id))
            else:
                ret = TrainingProtocol.train(self.net, self.optimizer, inp_batch=self.buffer_out.get(seq_id), output=data, rank = self.pipeline_rank, stage = -1)
                # print(ret)
                loop = asyncio.get_running_loop()
                loop.create_task(self.send_stream(self.prev,pickle.dumps(self.buffer_in.get(seq_id).grad),seqdata=seq_id))
                tmp = []
                self.len_sizes = []
                for param in self.net.parameters():
                    tmp.append(param.grad.view(-1))
                    self.len_sizes.append(len(tmp[-1]))
                loop = asyncio.get_running_loop()
                self.prev_grad = cat(tmp)
                for peer in self.dp_group:
                    if peer == Peer.me.id_node:
                        continue
                    loop.create_task(self.send_stream(peer,pickle.dumps(self.prev_grad),seqdata=seq_id))
                    
                self.aggregation.append(self.prev_grad)
                # print("calculating\n\n\n\n",len(self.dp_group))
                if len(self.aggregation) == len(self.dp_group):
                    self._apply_grad()
                del self.buffer_in[seq_id]
                del self.buffer_out[seq_id]
        elif nodeid in self.dp_group:
            self.aggregation.append(data)
            # pprint("collecting...")
            if len(self.aggregation) == len(self.dp_group):
                self._apply_grad()
                if self.pipeline_rank == 0:
                    try:
                        batch_idx, (data, target) = next(self.dataloader)
                    except StopIteration :
                        print("TRAINING COMPLETE")
                        return
                    new_seq_id = os.urandom(8)
                    while self.buffer_out.get(new_seq_id) != None:
                        new_seq_id = os.urandom(8)
                    self.buffer_in[new_seq_id] = target
                    ret = TrainingProtocol.train(self.net,self.optimizer, data, rank = 0, stage=1)
                    ret.retain_grad()
                    self.buffer_out[new_seq_id] = ret
                    loop = asyncio.get_running_loop()
                    loop.create_task(self.send_stream(self.next,pickle.dumps(ret),seqdata=new_seq_id))
 

        return

    async def send_stream(self, node_id, data, seqdata=b''):
        # print("SENDING TO")
        p: Peer = await self._lower_find_peer(node_id)
        # print("FOUND PEER SENDING")
        await self._lower_open_connection(p.addr[0], p.tcp, p.id_node)
        to_send = bytearray(seqdata)
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
                