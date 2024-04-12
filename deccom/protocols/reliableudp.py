import asyncio
from typing import Callable
from deccom.protocols.abstractprotocol import AbstractProtocol

class Connection():
    
    def __init__(self, connection, data = None, max_size = 3084, max_packets = 2, send_datagram = lambda msg, addr: ..., addr = None) -> None:
        self.data = data if data != None else asyncio.Queue()
        self.connection = connection
        self.head = 0
        self.max_ack = -1
        self.max_size = max_size
        self.missing = []
        self.done = False
        self.acks = 0
        self.max_packets = max_packets
        self.ln = 0
        self.chunk_size = 0
        self.their_head = 0
        self.attempts = 3
        loop = asyncio.get_event_loop()
        self.refresh_loop: asyncio.TimerHandle = loop.call_later(5,self.resend_last_batch)
        if data != None:
            self.ln = len(data)
        self.addr = addr
        self.send_datagram = send_datagram
        self.complete = False
        self.desired = -1
    def stop(self, clear_queue = True):
        if self.refresh_loop != None:
            self.refresh_loop.cancel()
        if clear_queue and isinstance(self.data, asyncio.Queue):
            while not self.data.empty():
                self.data.get_nowait()
        self.missing.clear()

    
    def send(self, head: int):
        if head * self.max_size >= self.ln:
            self.done = True
            #print("wont send")
            return False
        if (head + 1) * self.max_size >= self.ln:
            self.done = True

            header = ReliableUDP.COMPLETE.to_bytes(1,byteorder="big")
        else:
            header = ReliableUDP.MSG.to_bytes(1,byteorder="big")
        mn = head * self.max_size
        mx = mn + self.max_size
        loop = asyncio.get_event_loop()
        loop.create_task(self.send_datagram(self.connection + header + head.to_bytes(2,byteorder="big") + self.data[mn:mx], self.addr))
        return True

    def start(self):
        self.refresh_loop.cancel()
        for _ in range(self.max_packets):
            
            
            if not self.send(self.head):
                break
            self.head+=1
        loop = asyncio.get_event_loop()
        self.refresh_loop: asyncio.TimerHandle = loop.call_later(3,self.resend_last_batch)
    def _helper(self):
        
        self.attempts -= 1
        loop = asyncio.get_event_loop()
        if self.attempts == 0:
            return
        if isinstance(self.data, bytes):
            self.reset()
            # print("resend",self.done,self.their_head, self.head)
            if self.done and self.their_head == self.head:
                return
            for _ in range(self.max_packets):
                self.send_next()
            self.refresh_loop: asyncio.TimerHandle = loop.call_later(3,self.resend_last_batch)
            return
        else:
            # print("resend",self.complete)
            if self.done:
                return
            
            msg = self.connection + ReliableUDP.ACK.to_bytes(1,byteorder="big") + self.gen_ack()
             
            loop.create_task(self.send_datagram(msg,self.addr))
            self.refresh_loop: asyncio.TimerHandle = loop.call_later(0.5,self.resend_last_batch)
            
        
        
    def resend_last_batch(self):
        loop = asyncio.get_event_loop()
        loop.call_soon_threadsafe(self._helper)
        
    def send_next(self):
        #print(self.their_head, self.head, self.done)
        if self.their_head < 0:
            
            msn_head = self.missing[len(self.missing) + self.their_head]
            
            self.send(msn_head)
            self.their_head+=1
            if self.their_head == 0:
                self.their_head = self.max_ack
        elif self.their_head < self.head:
            
            self.send(self.their_head)
            self.their_head+=1
        elif self.their_head == self.head:
            if self.done:
                self.refresh_loop.cancel()
                return
            self.send(self.head)
            self.head += 1
            self.their_head += 1
            
    # 2**16
    def ack_recv(self, msg):
        self.refresh_loop.cancel()
        i = 0
        self.attempts = 3
        max_ack = msg[i:i+2]
        max_ack = int.from_bytes(max_ack,byteorder="big")
        if max_ack < self.max_ack:
            loop = asyncio.get_event_loop()
            self.refresh_loop: asyncio.TimerHandle = loop.call_later(3,self.resend_last_batch)
            return
        # print("received ack", max_ack)
        # print(msg[i+2:])
        self.max_ack = max(max_ack,self.max_ack)
        i+=2
        strt = max_ack
        self.missing = []
        
        while i < len(msg):
            # print(i)
            cntrl = msg[i]
            rd = cntrl % 128
            cntrl = cntrl // 128
            rd += 1
            i+=1
            
            if cntrl == 1:
                for k in range(strt-rd, strt):
                    
                    self.missing.insert(0,k)
            
            strt -= rd
            
        # print("resetting",self.missing)
        self.reset()
        # print(self.their_head, self.head)
        if self.done and self.their_head == self.head:
            return
        for _ in range(self.max_packets):
            self.send_next()
        loop = asyncio.get_event_loop()
        self.refresh_loop: asyncio.TimerHandle = loop.call_later(3,self.resend_last_batch)
    def reset(self):
        self.acks = 0
        if len(self.missing) == 0:
            self.their_head = self.max_ack + 1
        else:
            self.their_head = -len(self.missing)
    def receive(self,msg):
        if self.complete:
            self.acks += 1
            return        
        self.refresh_loop.cancel()
        i = 0
        self.attempts = 5
        rcvd = msg[i:i+2]
        rcvd = int.from_bytes(rcvd,byteorder="big")
        #print(rcvd)
        if self.complete:
            self.acks += 1
            return        
        if rcvd > self.max_ack:
            
            if rcvd - self.max_ack > 1:
                self.missing.append((self.max_ack + 1, rcvd - 1))
                
            self.max_ack = rcvd
            self.acks += 1
            self.ln += (len(msg) - 2)
            self.chunk_size = max(self.chunk_size,len(msg) - 2)
            self.data.put_nowait((rcvd,msg))
        else:
            k = 0 
            while k < len(self.missing):
                if self.missing[k][0]<= rcvd and self.missing[k][1]>=rcvd:
                    self.acks += 1
                    self.ln += (len(msg) - 2)
                    self.chunk_size = max(self.chunk_size,len(msg) - 2)
                    self.data.put_nowait((rcvd,msg))
                    mn,mx = self.missing[k]
                    if mx == mn:
                        del self.missing[k]
                        break
                    if rcvd == mn:
                        
                        self.missing[k] = (mn + 1, mx)
                    elif rcvd == mx:
                        self.missing[k] = (mn, mx - 1)
                    else:
                        self.missing[k] = (mn, rcvd - 1)
                        self.missing.insert(k+1, (rcvd+1,mx))
                    break
                k += 1
        # print(self.missing)
        loop = asyncio.get_event_loop()
        self.refresh_loop: asyncio.TimerHandle = loop.call_later(0.5,self.resend_last_batch)
    def gen_ack(self) -> bytes:
        
        # print("gen_ack",self.missing)
        msg = bytearray()
        self.desired = len(self.missing)
        msg += self.max_ack.to_bytes(2,byteorder="big")
        curr_ack = self.max_ack - 1
        k = len(self.missing) - 1
        # print(k)
        while k >= 0:
            mn,mx = self.missing[k]
            if mx - mn < 127:
                to_add: int = 0
                to_add = curr_ack - mx
                if to_add > 0:
                    to_add -= 1
                    msg += to_add.to_bytes(1, byteorder="big")
                to_add: int = 0
                to_add += (mx - mn)
                to_add += 128
                curr_ack = mn - 1
                msg += to_add.to_bytes(1, byteorder="big")
            else:
                print("error")
            k-=1
        
        return bytes(msg)
    def assemble_message(self) -> bytes:
        
        self.refresh_loop.cancel()
        self.complete = True
        ret = bytearray(self.ln)
        while not self.data.empty():
            idx, msg = self.data.get_nowait()
            
            ret[idx*self.chunk_size:idx*self.chunk_size+len(msg)-2] = msg[2:]
        return ret


class ReliableUDP(AbstractProtocol):
    ACK = int.from_bytes(b'\x00', byteorder="big")
    MSG = int.from_bytes(b'\x01', byteorder="big")
    COMPLETE = int.from_bytes(b'\x02', byteorder="big")
    def __init__(self, max_size = 3084, max_packets = 10, max_connections = 20, submodule=None, callback: Callable[[tuple[str, int], bytes], None] = ...):
        super().__init__(submodule, callback)
        self.max_size = max_size
        self.max_packets = max_packets
        self.max_connections = max_connections
        self.receives: dict[tuple[tuple[str,int], bytes], Connection] = dict()
        self.sends: dict[tuple[tuple[str,int], bytes], Connection] = dict()
        self.connections = 0
    async def stop(self):
        for _,v in self.receives.items():
            v.stop()
        self.receives.clear()
        for _,v in self.sends.items():
            v.stop()
        self.sends.clear()
        return await super().stop()
    def process_datagram(self, addr, data):
        
        connection = data[0:4]
        if data[4] == ReliableUDP.ACK:
            if self.sends.get((addr,connection)) == None:
                return
            self.sends[(addr,connection)].ack_recv(data[5:])
            return
        elif data[4] == ReliableUDP.MSG:
            if self.sends.get((addr,connection)) == None:
                self.sends[(addr,connection)] = Connection(connection, addr = addr, send_datagram=self.send_datagram)
            self.sends[(addr,connection)].receive(data[5:])
            loop = asyncio.get_event_loop()
            if self.sends[(addr,connection)].acks >= self.max_packets:
                msg = connection + ReliableUDP.ACK.to_bytes(1,byteorder="big") + self.sends[(addr,connection)].gen_ack()
                self.sends[(addr,connection)].reset()
                loop.create_task(self.send_datagram(msg,addr))
            
            if self.sends[(addr,connection)].done and len(self.sends[(addr,connection)].missing) == 0 and not self.sends[(addr,connection)].complete:
                self.sends[(addr,connection)].refresh_loop.cancel()
                self.callback(addr, self.sends[(addr,connection)].assemble_message())
                
                
            
            return
        elif data[4] == ReliableUDP.COMPLETE:
            if self.sends.get((addr,connection)) == None:
                self.sends[(addr,connection)] = Connection(connection, addr = addr, send_datagram=self.send_datagram)
            self.sends[(addr,connection)].receive(data[5:])
            self.sends[(addr,connection)].done = True
            loop = asyncio.get_event_loop()
            msg = connection + ReliableUDP.ACK.to_bytes(1,byteorder="big") + self.sends[(addr,connection)].gen_ack()
            self.sends[(addr,connection)].reset()
            loop.create_task(self.send_datagram(msg,addr))
            if self.sends[(addr,connection)].done and len(self.sends[(addr,connection)].missing) == 0 and not self.sends[(addr,connection)].complete:
                self.sends[(addr,connection)].refresh_loop.cancel()
                self.callback(addr, self.sends[(addr,connection)].assemble_message())
                
            
            
            return
            
    async def send_datagram(self, msg: bytes, addr: tuple[str, int]):

        return await super().send_datagram(msg, addr)
        
    async def sendto(self, msg, addr):
        self.connections += 1
        uniqueid = self.connections.to_bytes(4, byteorder="big")
        self.sends[(addr,uniqueid)] = Connection(uniqueid, msg,max_size=self.max_size, send_datagram=self.send_datagram, addr=addr, max_packets=self.max_packets)
        self.sends[(addr,uniqueid)].start()