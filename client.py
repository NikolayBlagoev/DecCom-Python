import asyncio
from typing import Callable
from utils.common import find_open_port
from protcols.protocols import BaseProtocol, BatchedTimeoutProtocol

class Node(object):
    def __init__(self, ip_addr = "0.0.0.0", port = None) -> None:
        if port == None:
            port = find_open_port()
        self.port = port
        self.ip_addr = ip_addr
        print("port for node",port)
        pass

    async def listen(self):
        self.server = asyncio.start_server(print, self.ip_addr,self.port)
        await self.server.serve_forever()



class UDPNode(object):
    def __init__(self, ip_addr = "0.0.0.0", port = None, call_back: Callable[[tuple[str,int], bytes], None] = lambda addr, data: print(addr,data)) -> None:
        if port == None:
            port = find_open_port()
        self.port = port
        self.ip_addr = ip_addr
        self.call_back = call_back
        self.peers: dict[bytes,tuple[str,int]] = dict()
        print(f"Node listening on {ip_addr}:{port}")
        pass

    async def listen(self, loop: asyncio.AbstractEventLoop):
        
        listen = loop.create_datagram_endpoint(lambda: BaseProtocol(call_back=self.call_back), local_addr=(self.ip_addr, self.port))
        self.transport, self.protocol = await listen
    async def ping(self, addr, callback = print):
        self.transport.sendto(b'\xe2\xe4', addr=addr)
    async def sendto(self, msg, addr): 
        self.transport.sendto(msg, addr=addr)


class BatchedNode(object):
    def __init__(self, ip_addr = "0.0.0.0", port = None, call_back: Callable[[tuple[str,int], bytes], None] = lambda addr, data: print(addr,data)) -> None:
        if port == None:
            port = find_open_port()
        self.port = port
        self.ip_addr = ip_addr
        self.call_back = call_back
        self.peers: dict[bytes,tuple[str,int]] = dict()
        print(f"Node listening on {ip_addr}:{port}")
        pass

    async def listen(self, loop: asyncio.AbstractEventLoop):
        
        listen = loop.create_datagram_endpoint(lambda: BatchedTimeoutProtocol(call_back=self.call_back), local_addr=(self.ip_addr, self.port))
        self.transport, self.protocol = await listen
    # async def ping(self, addr, callback = print):
    #     self.transport.sendto(b'\xe2\xe4', addr=addr)
    def sendto(self, msg, addr): 
        self.protocol.start_send(addr,msg,1)  


n = BatchedNode(ip_addr='127.0.0.1')
loop = asyncio.new_event_loop()
# loop.create_task()
loop.run_until_complete(n.listen(loop))
n.sendto(b'hi',addr=('127.0.0.1',10041))
loop.run_forever()