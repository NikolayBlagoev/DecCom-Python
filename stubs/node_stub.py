import asyncio
from asyncio import exceptions
from typing import Callable
from deccom.cryptofuncs.hash import SHA256
from random import randint
from deccom.peers.peer import Peer
from deccom.protocols.abstractprotocol import AbstractProtocol  
        

class NodeStub(object):
    def __init__(self, peer: Peer, protocol: AbstractProtocol, ip_addr = "0.0.0.0", port = None, call_back: Callable[[tuple[str,int], bytes], None] = lambda addr, data: print(addr,data)) -> None:
        if port == None:
            port = randint(0,10000)
        self.port = port
        self.ip_addr = ip_addr
        self.call_back = call_back
        self.peers: dict[bytes,tuple[str,int]] = dict()
        print(f"Node listening on {ip_addr}:{port}")
        self.protocol_type = protocol
        protocol.callback = call_back
        self.peer = peer
        self.peer.addr = (self.ip_addr, self.port)
        pass
    def set_listen(self, state):
        self.protocol_type.get_lowest().set_listen(state)
    async def listen(self):
        
        self.protocol_type.get_lowest().initialise((self.ip_addr, self.port))
        
        await self.protocol_type.start(self.peer)
    async def sendto(self, msg, addr): 
        await self.protocol_type.sendto(msg, addr=addr)
    async def ping(self, addr, success, error, dt):
        await self.protocol_type.send_ping(addr, success, error, dt)
    
    async def find_node(self, id, timeout = 50):
        if not isinstance(id, bytes):
            id = SHA256(id)
            print("looking for",id)
        try:
            peer = await  asyncio.wait_for(self.protocol_type.find_peer(id), timeout=timeout)
            print("FOUND PEER")
            return peer
        except asyncio.exceptions.TimeoutError:
            print('PEER NOT FOUND')
            return None



        
    

