import asyncio
from collections import OrderedDict
import os
from typing import Callable, Union
from deccom.cryptofuncs.hash import SHA256
from deccom.peers.peer import Peer
from deccom.protocols.peerdiscovery.abstractpeerdiscovery import AbstractPeerDiscovery
from ._kademlia_routing import BucketManager
from deccom.protocols.wrappers import *
from ._finder import Finder
class KademliaDiscovery(AbstractPeerDiscovery):
    INTRODUCTION = int.from_bytes(b'\xe1', byteorder="big") # english opening king's variation
    RESPOND_FIND = int.from_bytes(b'\xc4', byteorder="big")
    # TODO: Fix finding
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
        self.finders: dict[bytes, Finder] = dict()
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
        print("refreshing")
        loop = asyncio.get_running_loop()
        if len(self.bucket_manager.buckets) == 1 and len(self.bucket_manager.buckets[0].peers) == 0:
            print("i dont know anyone still")
            for p in self.bootstrap_peers:
                await self.introduce_to_peer(p)
                msg = bytearray([KademliaDiscovery.ASK_FOR_ID])
                await self._lower_sendto(msg,p.addr)
            self.refresh_loop = loop.call_later(2, self.refresh_table)
            return
        rand_ids = []
        other = self.bucket_manager.get_smallest_bucket().to_bytes(32, byteorder = "big")
        rand_ids.append(other)
        unique_id = os.urandom(8)
        while self.searches.get(unique_id) != None:
            unique_id = os.urandom(8)
        if self.warmup == 0:
            
            print("looking for myself", self.peer.id_node)
            self.finders[unique_id] = Finder(self.peer.id_node, self.bucket_manager.get_closest(self.peer.id_node,3), 3)
            l = self.finders[unique_id].find_peer()
            self.warmup+=1
            for p in l:
                msg = bytearray([KademliaDiscovery.FIND ^ 1])
                msg += unique_id
                msg += self.peer.id_node
                await self._lower_sendto(msg,p.addr)
            self.refresh_loop = loop.call_later(self.interval, self.refresh_table)
            return

        ret = self.bucket_manager.get_buckets_not_updated(self.interval)
        for r in ret:
            rand_ids.append(r.to_bytes(32, byteorder="big"))
        for ids in rand_ids:
            l = self.bucket_manager.get_closest(ids,3)
            if len(l) == 0:
                continue
            for p in l:
                msg = bytearray([KademliaDiscovery.FIND ^ 1])
                msg += unique_id
                msg += ids
                await self._lower_sendto(msg,p.addr)

        
        self.refresh_loop = loop.call_later(self.interval, self.refresh_table)
    
    def remove_peer(self, addr: tuple[str, int], node_id: bytes):
        if  self.bucket_manager.get_peer(node_id) == None:
            return
        del self.peers[node_id]
        print(self.peer.pub_key, "removing peer.", self.bucket_manager.get_peer(node_id).pub_key)
        self.bucket_manager.remove_peer(node_id)
        return super().remove_peer(addr, node_id)
    
    async def introduce_to_peer(self, peer: Peer):
        print("introducing to", peer.id_node)
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
            print(self.peer.pub_key,": introduction form", other.pub_key)
            other.addr = addr
            
                
                
            if self.bucket_manager.get_peer(other.id_node) != None:

                self.bucket_manager.update_peer(other.id_node, other)
            else:
                self.connection_approval(addr,other,self.add_peer,self.ban_peer)

        
        elif data[0] == KademliaDiscovery.FIND or data[0] ^ KademliaDiscovery.FIND == 1:
            # print("peer looking")

            
            i = 1
            unique_id = data[i:i+8]
            id = data[i+8:]
            if self.get_peer(id) != None:

                print(self.get_peer(id).pub_key, " is looking for ",id)
            self.sent_finds[data] = i
            if id == self.peer.id_node:
                # print("THATS ME")
                loop = asyncio.get_running_loop()
                msg = bytearray([KademliaDiscovery.INTRODUCTION])
                msg = msg + bytes(self.peer)
                loop = asyncio.get_running_loop()
                loop.create_task(self._lower_sendto(msg, addr))
            elif self.get_peer(id) != None and data[0] == KademliaDiscovery.FIND:
                # print(self.peer.pub_key,"I KNOW THAT GUY!",self.get_peer(id).pub_key)
                self.send_find_response(addr,[self.get_peer(id)],unique_id)
            else:
                
                closest_peers = self.bucket_manager.get_closest(id)
                if len(closest_peers) == 0:
                    # print("oops dont know anyone :/")
                    return
                
                self.send_find_response(addr,closest_peers,unique_id)
        
        elif data[0] == KademliaDiscovery.RESPOND_FIND:
            # print(self.peer.pub_key,"got a response",addr)
            i = 1
            unique_id = data[i:i+8]
            i+=8
            if self.searches.get(unique_id) == None and self.warmup >= 60:
                # print(self.peer.pub_key,"NOT A VALID SEARCH")
                return
            else:
                self.warmup += 1
            peers: list[Peer] = []
            while i < len(data):
                peer_new, offs = Peer.from_bytes(data[i:])
                i+=offs
                if peer_new.id_node == self.peer.id_node:
                    continue
                peers.append(peer_new)
            # print("got ",len(peers), "to look up",self.searches.get(unique_id))
            
            if self.searches.get(unique_id) != None:
                for p in peers:
                    if p.id_node == self.searches.get(unique_id) and p.id_node != self.peer.id_node:
                        # print("oh he in here!")
                        
                        loop = asyncio.get_running_loop()
                        loop.create_task(self.introduce_to_peer(p))
                        msg = bytearray([KademliaDiscovery.FIND])
                        msg += unique_id
                        msg += self.finders[unique_id].look_for
                        del self.finders[unique_id]
                        loop.create_task(self._lower_sendto(msg, p.addr))
                        
                        
                        return
                    
                
            for p in peers:
                self._lower_heard_from(addr, p.addr)
                if self.bucket_manager.get_peer(p.id_node) == None and p.id_node != self.peer.id_node:
                    loop = asyncio.get_running_loop()
                    loop.create_task(self.introduce_to_peer(p))
                    msg = bytearray([KademliaDiscovery.ASK_FOR_ID])
                    loop.create_task(self._lower_sendto(msg,p.addr))
            if self.finders.get(unique_id) != None:
                self.finders[unique_id].add_peer(peers)
                msg = bytearray([KademliaDiscovery.FIND if self.finders[unique_id].look_for != self.peer.id_node else KademliaDiscovery.FIND ^ 1])
                msg += unique_id
                msg += self.finders[unique_id].look_for
                l = self.finders[unique_id].find_peer()
                loop = asyncio.get_running_loop()
                for p in l:
                    print("sending to ", p.pub_key)
                    loop.create_task(self._lower_sendto(msg, p.addr))

                    
        
            
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
    async def send_find(self, unique_id, p: Peer, bypass = False, for_peer: bytes = None):
        if self.searches.get(unique_id) == None:
            if bypass:
                # print("bypassing")
                msg = bytearray([KademliaDiscovery.FIND ^ 1])
                msg += unique_id
                msg += self.peer.id_node if for_peer == None else for_peer
                await self._lower_sendto(msg,p.addr)
            elif self.warmup < 60:
                msg = bytearray([KademliaDiscovery.FIND])
                msg += unique_id
                msg += self.peer.id_node if for_peer == None else for_peer
                await self._lower_sendto(msg,p.addr)
            return
        msg = bytearray([KademliaDiscovery.FIND])
        msg += unique_id
        msg += self.searches[unique_id]
        await self._lower_sendto(msg,p.addr)
    def successful_add(self, addr: tuple[str,int], p: Peer):
        
        print(self.peer.pub_key," : adding peer", p.pub_key)
        if self.peer_crawls.get(p.id_node) != None:
                self.peer_crawls[p.id_node][0].set_result("success")
                del self.searches[self.peer_crawls[p.id_node][1]]
                del self.peer_crawls[p.id_node]
        self.bucket_manager.update_peer(p.id_node,p)
        self.peers[p.id_node] = p
        super().add_peer(addr, p)
    async def _async_add(self,addr,p):
        return self.successful_add(addr,p)
    def _add(self, dist, p: Peer):
        loop = asyncio.get_event_loop()
        loop.create_task(self._async_add(p.addr,p))
        
        
    def update_peer(self, p: Peer):
        # print(self.peer.pub_key, "peer responded", p.pub_key)
        self.bucket_manager.update_peer(p.id_node, p)
    
    def add_peer(self, addr: tuple[str,int], p: Peer):
        # print(p)
        
        ret = self.bucket_manager.add_peer(p.id_node,p)
        if ret != None:
            # print(self.peer.pub_key,"oops, kinda big for", p.pub_key)
            loop = asyncio.get_event_loop()
            loop.create_task(self._lower_ping(ret[1].addr, lambda addr, peer=ret[1], self=self: self.update_peer(peer), lambda addr, oldp=ret[1], self=self: self.remove_peer(addr, oldp.id_node), 8))
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
        
        
        self.finders[unique_id] = Finder(id, self.bucket_manager.get_closest(id,5), 5)
        l = self.finders[unique_id].find_peer()
        for p in l:
            print("sending to ", p.pub_key)
            await self._lower_sendto(msg, p.addr)


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