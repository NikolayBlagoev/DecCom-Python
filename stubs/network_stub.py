import asyncio
from typing import Any, Callable
import os

class TransportStub():
    def __init__(self, addr) -> None:
        self.addr = addr
        return
    def sendto(self, data, addr):
        sending = NetworkStub.connections.get(addr)
        if sending == None:
            return
        
        asyncio.get_running_loop().create_task(sending(data,self.addr))
class NetworkStub():
    PING_b = b'\xd4'
    PONG_b = b'\xd5'
    PING = int.from_bytes(PING_b, byteorder="big")
    PONG = int.from_bytes(PONG_b, byteorder="big")
    connections = {}
    def __init__(self, callback: Callable[[tuple[str,int], bytes], None] = lambda addr, data: ...):
        self.transport = None
        self.callback = callback
        self.pings = dict()
        self._taken = dict()
        self.listen = True
        self.addr = None
    def set_listen(self, state):
        self.listen = state
    def initialise(self,addr):
        NetworkStub.connections[addr] = self.processor
        self.transport = TransportStub(addr)
        self.addr = addr
    async def processor(self, data, addr):
        if not self.listen:
            # print(self.addr[1], "resting")
            return
        # print("received")
        self.datagram_received(bytes(data),addr)
    def set_callback(self, callback):
        # print("setting callback to", callback)
        self.callback = callback
    
    def datagram_received(self, data, addr):
        
        # print("from:", addr, "data", data)
        loop = asyncio.get_event_loop()
        if len(data) < 2:
            print("invalid msg received")
            return
        if data[0] == NetworkStub.PING:
            loop.create_task(self.handle_ping(addr, data[1:]))
        elif data[0] == NetworkStub.PONG:
            loop.create_task(self.handle_pong(addr,data[1:]))
        else:
            loop.create_task(self.call_callback(addr,data[1:]))
    async def call_callback(self, addr,data):
        self.callback(addr,data)

    async def start(self, *args):
        return
    def timeout(self, addr, error, msg_id):
        print("timed out")
        if self.pings.get(msg_id) is None:
            return
        del self.pings[msg_id]
        error(addr)
    async def send_ping(self, addr, success, error, dt = 10):
        loop = asyncio.get_running_loop()
        bts = os.urandom(4)
        msg_id = int.from_bytes(bts, "big")
        while self.pings.get(msg_id) != None:
            bts = os.urandom(4)
            msg_id = int.from_bytes(bts, "big")
        print("sending ping",addr,dt)
        timeout = loop.call_later(dt,
                                      self.timeout, addr,error,msg_id)
        self.pings[msg_id] = (success, timeout)
        trmp = bytearray([NetworkStub.PING])
        trmp = trmp + bts
        self.transport.sendto(trmp, addr=addr)
        
        return

    async def handle_ping(self, addr, data):
        trmp = bytearray([NetworkStub.PONG])
        trmp = trmp + data
        self.transport.sendto(trmp, addr=addr)
        # print("sent pong",addr)
        return

    async def handle_pong(self, addr, data):
        msg_id = int.from_bytes(data, "big")
        # print("received pong",addr )
        if self.pings.get(msg_id) is None:
            return
        success, timeout = self.pings[msg_id]
        timeout.cancel()
        del self.pings[msg_id]
        success(addr)
        return
    def get_lowest(self):
        return self
    def connection_lost(self, exc: Exception) -> None:
        print("lost connection",exc)
        return super().connection_lost(exc)
    
    async def sendto(self,msg,addr):
        # print("sending to",addr)
        trmp = bytearray(b'\x01')
        trmp = trmp + msg
        self.transport.sendto(trmp, addr=addr)
        # print("sent")
