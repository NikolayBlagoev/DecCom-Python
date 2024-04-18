import asyncio
from typing import Callable
from deccom.cryptofuncs.hash import SHA256
from deccom.peers.peer import Peer
from deccom.utils.common import find_open_port
from deccom.protocols.abstractprotocol import AbstractProtocol

class Node(object):
    def __init__(self, p: Peer, protocol: AbstractProtocol, ip_addr = "0.0.0.0", port = None, call_back: Callable[[tuple[str,int], bytes], None] = lambda addr, data: print(addr,data)) -> None:
        if port == None:
            port = find_open_port()
        self.port = port
        self.ip_addr = ip_addr
        self.call_back = call_back
        self.peers: dict[bytes,tuple[str,int]] = dict()
        print(f"Node listening on {ip_addr}:{port}")
        self.protocol_type = protocol
        self.peer = p
        protocol.callback = call_back
        self.peer.addr = (self.ip_addr, self.port)
        pass

    async def listen(self):
        loop = asyncio.get_running_loop()
        self.udp = loop.create_datagram_endpoint(self.protocol_type.get_lowest, local_addr=(self.ip_addr, self.port))
        self.transport, self.protocol = await self.udp
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



        
    

