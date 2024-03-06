import asyncio
from collections import OrderedDict
import os
from typing import Callable, Union
from deccom.cryptofuncs.hash import SHA256
from deccom.peers.peer import Peer
from deccom.protocols.peerdiscovery.abstractpeerdiscovery import AbstractPeerDiscovery
from ._kademlia_routing import BucketManager
from deccom.protocols.wrappers import *
class KademliaDiscovery(AbstractPeerDiscovery):
    INTRODUCTION = int.from_bytes(b'\xe1', byteorder="big") # english opening king's variation
    RESPOND_FIND = int.from_bytes(b'\xc4', byteorder="big")
    
    FIND = int.from_bytes(b'\xf6', byteorder="big")
    ASK_FOR_ID = int.from_bytes(b'\xf3',byteorder="big")
    offers = dict(AbstractPeerDiscovery.offers, **{
        "send_ping": "send_ping"
    })
    bindings = dict(AbstractPeerDiscovery.bindings, **{
                    "_lower_ping": "send_ping"
                    })
    required_lower = AbstractPeerDiscovery.required_lower + ["send_ping"]
    def __init__(self, bootstrap_peers: list[Peer] = [], interval: int = 60, k: int = 20, submodule=None, callback: Callable[[tuple[str, int], bytes], None] = None, disconnected_callback=lambda *args:..., connected_callback: Callable[[Peer], None] =lambda *args:...):
        super().__init__(bootstrap_peers, interval, submodule, callback, disconnected_callback, connected_callback)
        self.k = k
        self.peer_crawls = dict()
        self.sent_finds = dict()
        self.warmup = 0
        self.searches: dict[bytes,bytes] = dict()
    async def start(self, p: Peer):
        await super().start(p)
        self.bucket_manager = BucketManager(self.peer.id_node,self.k,self._add)
        for p in self.bootstrap_peers:
            await self.introduce_to_peer(p)
            msg = bytearray([KademliaDiscovery.ASK_FOR_ID])
            await self._lower_sendto(msg,p.addr)
        loop = asyncio.get_event_loop()
        loop.call_later(2, self.refresh_table)
    
    def refresh_table(self):
        
        loop = asyncio.get_event_loop()

        loop.create_task(self._refresh_table())

    async def _refresh_table(self):
        # print("refreshing")
        loop = asyncio.get_running_loop()
        if len(self.bucket_manager.buckets) == 1 and len(self.bucket_manager.buckets[0].peers) == 0:
            # print("i dont know anyone still")
            for p in self.bootstrap_peers:
                await self.introduce_to_peer(p)
                msg = bytearray([KademliaDiscovery.ASK_FOR_ID])
                await self._lower_sendto(msg,p.addr)
            self.refresh_loop = loop.call_later(2, self.refresh_table)
            return
        rand_ids = [self.peer.id_node]
        unique_id = os.urandom(8)
        while self.searches.get(unique_id) != None:
            unique_id = os.urandom(8)
        for _ in range(2):
            r1 = os.urandom(32)
            while r1 in rand_ids:
                r1 = os.urandom(32)
            rand_ids.append(r1)
        if self.warmup < 7:
            rand_ids = rand_ids[:1]
            # self.warmup += 1
        for ids in rand_ids:
            l = self.bucket_manager.get_closest(ids,1)
            if len(l) == 0:
                print("noone close to me?")
                break
            msg = bytearray([KademliaDiscovery.FIND ^ 1])
            msg += unique_id
            msg += ids
            await self._lower_sendto(msg,l[0].addr)

        
        self.refresh_loop = loop.call_later(self.interval+2, self.refresh_table)
    
    def remove_peer(self, addr: tuple[str, int], node_id: bytes):
        print("removing peer.")
        self.bucket_manager.remove_peer(node_id)
        return super().remove_peer(addr, node_id)
    
    async def introduce_to_peer(self, peer: Peer):
        # print("introducing to", peer.id_node)
        msg = bytearray([KademliaDiscovery.INTRODUCTION])
        msg = msg + bytes(self.peer)
        await self._lower_sendto(msg, peer.addr)

    async def sendto(self, msg, addr):
        tmp = bytearray([1])
        tmp = tmp + msg
        return await self._lower_sendto(tmp, addr)
      
    def process_datagram(self, addr: tuple[str, int], data: bytes):
        
        if data[0] == KademliaDiscovery.INTRODUCTION:

            other, i = Peer.from_bytes(data[1:])
            # print(self.peer.pub_key,": introduction form", other.pub_key)
            other.addr = addr
            
                
                
            if self.bucket_manager.get_peer(other.id_node) != None:

                self.bucket_manager.update_peer( other.id_node, other)
            else:
                self.connection_approval(addr,other,self.add_peer,self.ban_peer)

        
        elif data[0] == KademliaDiscovery.FIND or data[0] ^ KademliaDiscovery.FIND == 1:
            # print("peer looking")
            if self.sent_finds.get(data) != None:
                # print("duplicate")
                return

            
            i = 1
            unique_id = data[i:i+8]
            id = data[i+8:]
            # print(" is looking for ",id)
            self.sent_finds[data] = i
            if id == self.peer.id_node:
                # print("THATS ME")
                loop = asyncio.get_running_loop()
                msg = bytearray([KademliaDiscovery.INTRODUCTION])
                msg = msg + bytes(self.peer)
                loop = asyncio.get_running_loop()
                loop.create_task(self._lower_sendto(msg, addr))
            elif self.get_peer(id) != None and data[0] == KademliaDiscovery.FIND:
                self.send_find_response(addr,[self.get_peer(id)],unique_id)
            else:
                
                closest_peers = self.bucket_manager.get_closest(id,alpha=3)
                if len(closest_peers) == 0:
                    # print("oops dont know anyone :/")
                    return
                
                # print(self.peer.pub_key,": i know someone close", len(closest_peers))
                self.send_find_response(addr,closest_peers,unique_id)
        
        elif data[0] == KademliaDiscovery.RESPOND_FIND:
            # print(self.peer.pub_key,"got a response",addr)
            i = 1
            unique_id = data[i:i+8]
            i+=8
            if self.searches.get(unique_id) == None and self.warmup >= 7:
                return
            else:
                self.warmup += 1
            peers: list[Peer] = []
            while i < len(data):
                peer_new, offs = Peer.from_bytes(data[i:])
                i+=offs
                if peer_new == self.peer:
                    continue
                peers.append(peer_new)
            # print("got ",len(peers), "to look up",self.searches.get(unique_id))
            
            if self.searches.get(unique_id) != None:
                for p in peers:
                    if p.id_node == self.searches.get(unique_id):
                        # print("oh he in here!")
                        loop = asyncio.get_running_loop()
                        loop.create_task(self.send_find(unique_id,p))
                        self.connection_approval(p.addr,p,self.add_peer,self.ban_peer)
                        return
                    
                
            for p in peers:
                if self.bucket_manager.get_peer(p.id_node) == None and p.id_node != self.peer.id_node:
                    loop = asyncio.get_running_loop()
                    loop.create_task(self.introduce_to_peer(p))
                    self.connection_approval(p.addr,p,self.add_peer,self.ban_peer)
                    loop.create_task(self.send_find(unique_id,p))
                    
            if self.warmup < 7:
                        loop = asyncio.get_running_loop()
                        loop.create_task(self.send_find(unique_id,self.bucket_manager.get_closest(self.peer.id_node, 1)[0], True))
            
        elif data[0] == KademliaDiscovery.ASK_FOR_ID:
            # print("ASKING FOR ID")
            msg = bytearray([KademliaDiscovery.INTRODUCTION])
            # print("PUBKEY", self.peer)
            
            # pprint(vars(self.peer))

            msg = msg + bytes(self.peer)
            loop = asyncio.get_running_loop()
            loop.create_task(self._lower_sendto(msg, addr))
            
        else:
            return self.callback(addr, data[1:])
        
    
    def send_find_response(self, addr, best_guess: list[Peer], uniq_id):
        
        msg = bytearray([KademliaDiscovery.RESPOND_FIND])
        msg += uniq_id
        for p in best_guess:
            msg += bytes(p)
        loop = asyncio.get_running_loop()
        loop.create_task(self._lower_sendto(msg, addr))
    async def send_ping(self, addr, success, fail, timeout):
        await self._lower_ping(addr, success, fail, timeout)
    async def send_find(self, unique_id, p: Peer, bypass = False):
        if self.searches.get(unique_id) == None:
            if bypass:
                # print("bypassing")
                msg = bytearray([KademliaDiscovery.FIND ^ 1])
                msg += unique_id
                msg += self.peer.id_node
                await self._lower_sendto(msg,p.addr)
            
            return
        msg = bytearray([KademliaDiscovery.FIND])
        msg += unique_id
        msg += self.searches[unique_id]
        await self._lower_sendto(msg,p.addr)
    def successful_add(self, addr: tuple[str,int], p: Peer):
        if self.peer_crawls.get(p.id_node) != None:
                self.peer_crawls[p.id_node][0].set_result("success")
                del self.searches[self.peer_crawls[p.id_node][1]]
                del self.peer_crawls[p.id_node]
        self.bucket_manager.update_peer(p.id_node,p)
        super().add_peer(addr, p)
    async def _async_add(self,addr,p):
        return self.successful_add(addr,p)
    def _add(self, dist, p: Peer):
        loop = asyncio.get_event_loop()
        loop.create_task(self._async_add(p.addr,p))
        
        
    def update_peer(self, p: Peer):
        print(self.peer.pub_key, "peer responded", p.pub_key)
        self.bucket_manager.update_peer(p.id_node, p)
    
    def add_peer(self, addr: tuple[str,int], p: Peer):
        # print(p)
        # if self.peer.pub_key != "0":
        #     print(self.peer.pub_key," : adding peer", p.pub_key)
        ret = self.bucket_manager.add_peer(p.id_node,p)
        if ret != None:
            print(self.peer.pub_key,"oops, kinda big for", p.pub_key)
            loop = asyncio.get_event_loop()
            loop.create_task(self._lower_ping(ret[1].addr, lambda addr, peer=ret[1], self=self: self.update_peer(peer), lambda addr, oldp=ret[1], self=self: self.remove_peer(addr, oldp.id_node), 5))
        else:
            self.successful_add(addr,p)

    
    async def _find_peer(self, fut, id):
        unique_id = os.urandom(8)
        while self.searches.get(unique_id) != None:
            unique_id = os.urandom(8)

        
        self.peer_crawls[id] = (fut, unique_id)
        msg = bytearray([KademliaDiscovery.FIND])

        self.searches[unique_id] = id
        msg += unique_id
        if not isinstance(id, bytes):
            id = SHA256(id)
        msg += id
        l = self.bucket_manager.get_closest(id,10)
        # print(self.peer.pub_key,"we found a list of", len(l))
        for p in l:
            await self._lower_sendto(msg, p.addr)

        return

    async def find_peer(self, id) -> Peer:
        if self.get_peer(id) == None:
            if self.peer_crawls.get(id) == None:
                loop = asyncio.get_running_loop()
                fut = loop.create_future()
                await self._find_peer(fut, id)
                await fut
            else:
                await self.peer_crawls.get(id)[0]
        return self.get_peer(id)
    def get_peer(self, id) -> Union[Peer,None]:
        return self.bucket_manager.get_peer(id)
    
    @bindto("send_ping")
    async def _lower_ping(self, addr, success, failure, timeout):
        return