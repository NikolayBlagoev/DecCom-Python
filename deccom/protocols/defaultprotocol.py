import asyncio
from typing import Any, Callable
import os


class DefaultProtocol(asyncio.DatagramProtocol):
    PING_b = b'\xd4'
    PONG_b = b'\xd5'
    PING = int.from_bytes(PING_b, byteorder="big")
    PONG = int.from_bytes(PONG_b, byteorder="big")
    _taken = dict()
    def __init__(self, callback: Callable[[tuple[str,int], bytes], None] = lambda addr, data: ...):
        self.transport = None
        self.callback = callback
        self.pings = dict()
        

    def connection_made(self, transport):
        self.transport = transport
        
    def set_callback(self, callback):
        # print("setting callback to", callback)
        self.callback = callback
    
    def datagram_received(self, data, addr):
        
        # print("from:", addr, "data", data)
        if len(data) < 2:
            print("invalid msg received")
            return
        if data[0] == DefaultProtocol.PING:
            self.handle_ping(addr, data[1:])
        elif data[0] == DefaultProtocol.PONG:
            self.handle_pong(addr,data[1:])
        else:
            self.callback(addr,data[1:])
    async def start(self):
        return
    def timeout(self, addr, error, msg_id):
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
        # print("sending ping",addr)
        timeout = loop.call_later(dt+2,
                                      self.timeout, addr,error,msg_id)
        self.pings[msg_id] = (success, timeout)
        trmp = bytearray([DefaultProtocol.PING])
        trmp = trmp + bts
        self.transport.sendto(trmp, addr=addr)
        
        return

    def handle_ping(self, addr, data):
        trmp = bytearray([DefaultProtocol.PONG])
        trmp = trmp + data
        self.transport.sendto(trmp, addr=addr)
        # print("sent pong",addr)
        return

    def handle_pong(self, addr, data):
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
        print("sending to",addr)
        trmp = bytearray(b'\x01')
        trmp = trmp + msg
        self.transport.sendto(trmp, addr=addr)
        # print("sent")
