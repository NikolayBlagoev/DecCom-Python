import asyncio
import traceback
from typing import Any, Callable
import os
from deccom.cryptofuncs.hash import SHA256

from deccom.peers.peer import Peer
from deccom.utils.common import get_executor

class DefaultProtocol(asyncio.DatagramProtocol):
    PING_b = b'\xd4'
    PONG_b = b'\xd5'
    PING = int.from_bytes(PING_b, byteorder="big")
    PONG = int.from_bytes(PONG_b, byteorder="big")
    def __init__(self, callback: Callable[[tuple[str,int], bytes], None] = lambda addr, data: ...):
        self.transport = None
        self.started = False
        self.callback = callback
        self.pings = dict()
        self._taken = dict()
        self.executor = get_executor()
        self.loop = asyncio.get_event_loop()
        self.uniqueid = SHA256(self.__class__.__name__)[-8:]
        
        
    def get_loop(self):
        return self.loop
    def connection_made(self, transport):
        self.transport = transport
        
    def set_callback(self, callback):
        # print("setting callback to", callback)
        self.callback = callback

    async def send_datagram(self, msg: bytes, addr: tuple[str,int]):
        await self.sendto(self.uniqueid + msg, addr)
        

    
    def process_datagram(self, addr, data):
        
        loop = asyncio.get_event_loop()
        
        if len(data) < 2:
            print("invalid msg received")
            return
        if data[0] == DefaultProtocol.PING:
            
            loop.create_task(self.handle_ping(addr, data[1:]))
        elif data[0] == DefaultProtocol.PONG:
            loop.create_task(self.handle_pong(addr,data[1:]))
    def datagram_received(self, data, addr):
        if not self.started:
            return
        # print("from:", addr, "data", data)
        
        if data[:8] == self.uniqueid:
            return self.process_datagram(addr, data[8:])
        else:
            loop = asyncio.get_event_loop()
            asyncio.run_coroutine_threadsafe(self.call_callback(addr,data), loop)
    async def call_callback(self, addr,data):
        with open(f"log{self.p.pub_key}.txt", "a") as log:

            try:
                #
                self.callback(addr,data)
            except Exception:
                traceback.print_exc(file=log)
                
       
    async def stop(self):
        self.started = False

        return
    async def start(self, p: Peer, *args):
        self.p = p
        self.started = True
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
        # with open(f"log{self.p.pub_key}.txt","a") as log:
        #     log.write(f"SENDING PING TO {addr} {bts}\n")
        timeout = loop.call_later(dt+2,
                                      self.timeout, addr,error,msg_id)
        self.pings[msg_id] = (success, timeout)
        trmp = bytearray([DefaultProtocol.PING])
        trmp = trmp + bts
        await self.send_datagram(trmp, addr=addr)
        
        return

    async def handle_ping(self, addr, data):
        trmp = bytearray([DefaultProtocol.PONG])
        trmp = trmp + data
        # with open(f"log{self.p.pub_key}.txt","a") as log:
        #     log.write(f"RESPONDING PING TO {addr} {data}\n")
        await self.send_datagram(trmp, addr=addr)
        
        return

    async def handle_pong(self, addr, data):
        msg_id = int.from_bytes(data, "big")
        # with open(f"log{self.p.pub_key}.txt","a") as log:
        #     log.write(f"rECEIVED PONG FROM {addr} {data}\n")
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
        # print("sending to",addr,msg)
        if addr[0] == self.transport.get_extra_info("sockname")[0] and addr[1] == self.transport.get_extra_info("sockname")[1]:
            return
        self.transport.sendto(msg, addr)
        # print("sent")
