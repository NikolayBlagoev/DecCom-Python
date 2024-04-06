import asyncio
import random
from typing import Any, Callable
import os

class TransportStub():
    def __init__(self, addr, nat) -> None:
        self.addr = addr
        self.nat: NAT = nat
        return
    def sendto(self, data, addr, ntstb):
        receiving: NAT = ntstb.connections.get(addr[0])
        if receiving == None:
            return
        
        trnsprt = self.nat.send(self.addr, addr)
        receiving = receiving.receive(trnsprt, addr, data)
        if receiving == None:
            return
        # print("approved",addr[0], self.addr[0])
        asyncio.get_running_loop().create_task(receiving(data,trnsprt))
class NAT():
    def __init__(self, active) -> None:
        self.connections = dict()
        self.outbound = dict()
        self.reverse = dict()
        self.active = active
        self.processors = dict()
    def register(self, addr1, mthd):
        self.processors[addr1] = mthd
    def retranslate(self,addr1,addr2):
        if not self.active:
            return addr1
        if self.connections.get(addr1) == None:
            if self.connections.get(addr2) != None:
                return addr1
            self.connections[addr1] = (addr1[0], addr1[1]*2)
            self.reverse[self.connections[addr1]] = addr1
        return self.connections[addr1]
    
    def send(self,addr1,addr2):
        if not self.active:
            return addr1
        _addr1 = self.retranslate(addr1,addr2)
        if _addr1 != addr1:
            if self.outbound.get(addr1) == None:
                self.outbound[addr1] = []
            if addr2 not in self.outbound[addr1]:
                self.outbound[addr1].append(addr2)
                # print("adding exception",addr1,addr2)
        return _addr1
    
    def receive(self, frm, to, msg):
        if not self.active:
            return self.processors.get(to)
        if self.reverse.get(to) == None:
            if self.connections.get(frm) != None and self.connections.get(to) != None:
                return self.processors[to]
            # print("1 denied", frm[0], to[0])
            return None
        if self.outbound.get(self.reverse[to]) == None or frm not in self.outbound[self.reverse[to]]:
            # print("2 denied", frm[0],to[0],self.outbound.get(self.reverse[to]) == None)
            return None
        return self.processors[self.reverse[to]]
                


class NatStub():
    PING_b = b'\xd4'
    PONG_b = b'\xd5'
    PING = int.from_bytes(PING_b, byteorder="big")
    PONG = int.from_bytes(PONG_b, byteorder="big")
    
    def __init__(self, connections, callback: Callable[[tuple[str,int], bytes], None] = lambda addr, data: ...):
        self.transport = None
        self.callback = callback
        self.pings = dict()
        self.connections = connections
        self._taken = dict()
        self.listen = True
        self.addr = None
    def set_listen(self, state):
        self.listen = state
    def initialise(self,addr):
        print(addr)
        if self.connections.get(addr[0]) == None:
            self.connections[addr[0]] = NAT(addr[0] != "0.0.0.0")
            
        self.connections[addr[0]].register(addr,self.processor)
        self.transport = TransportStub(addr,self.connections[addr[0]])
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
        loop = asyncio.get_running_loop()
        if len(data) < 2:
            print("invalid msg received")
            return
        if data[0] == NatStub.PING:
            loop.create_task(self.handle_ping(addr, data[1:]))
        elif data[0] == NatStub.PONG:
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
        trmp = bytearray([NatStub.PING])
        trmp = trmp + bts
        self.transport.sendto(trmp, addr,self)
        
        return

    async def handle_ping(self, addr, data):
        trmp = bytearray([NatStub.PONG])
        trmp = trmp + data
        self.transport.sendto(trmp, addr,self)
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
        self.transport.sendto(trmp, addr,self)
        # print("sent")
