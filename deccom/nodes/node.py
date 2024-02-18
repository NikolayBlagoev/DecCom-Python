import asyncio
from asyncio import exceptions
from typing import Callable
from deccom.cryptofuncs.hash import SHA256
from deccom.utils.common import find_open_port
from deccom.protocols.abstractprotocol import AbstractProtocol


class Introduction:
    x: int
    y: int
# class GridNode(object):
#     GREET_b = b'\xe5'
#     MEET_b = b'\xe4'
#     FRWRD_b = b'\xd4'
#     GREET = int.from_bytes(GREET_b, byteorder="big")
#     MEET = int.from_bytes(MEET_b, byteorder="big")
#     FRWRD = int.from_bytes(FRWRD_b, byteorder="big")
#     def __init__(self, ip_addr = "0.0.0.0", port = None, grid = (0,0), sz = (3,3)) -> None:
#         if port == None:
#             port = find_open_port()
#         self.tcp_port = find_open_port()
#         self.ip_addr = ip_addr
        
#         self.udp_port = port
#         self.grid = grid
#         self.sz = sz
#         self.tmp_grid = (0,0)
#         self.l = None
#         self.r = None
#         self.u = None
#         self.d = None
#         self.waiting_up = []
#         self.waiting_down = []
#         self.waiting_left = []
#         self.waiting_right = []
#         self.bootstrap = ("127.0.0.1", 10015)
#         pass
#     async def listen(self):
#         loop = asyncio.get_running_loop()
#         listen = loop.create_datagram_endpoint(lambda: BaseProtocol(call_back=self.handle_request), local_addr=(self.ip_addr, self.udp_port))
#         self.transport, self.protocol = await listen
#         if self.grid[0] != 0 or self.grid[1]!=0:
#             dt = bytearray(GridNode.MEET_b)
#             dt = dt + self.grid[0].to_bytes(1,byteorder = "big") + self.grid[1].to_bytes(1,byteorder = "big") + int(1).to_bytes(1,byteorder = "big") + self.tcp_port.to_bytes(4,byteorder = "big")
#             self.protocol.sendto(dt,self.bootstrap)
#             dt = bytearray(GridNode.MEET_b)
#             dt = dt  + self.grid[0].to_bytes(1,byteorder = "big") + self.grid[1].to_bytes(1,byteorder = "big") + int(2).to_bytes(1,byteorder = "big") + self.tcp_port.to_bytes(4,byteorder = "big")
#             self.protocol.sendto(dt,self.bootstrap)
#         print("listening ")
#         self.server = asyncio.start_server(self.handle_request, self.ip_addr,self.tcp_port)

#     def perform2(self, diff_y, diff_x, data,x,y,addr, dir):
#         if (self.grid[0] + 1) % self.sz[0] == y and self.grid[1] == x:
#             self.u = addr
#             dt = bytearray(GridNode.GREET_b)
#             dt = dt + int(1).to_bytes(1,byteorder = "big") + self.tcp_port.to_bytes(4,byteorder = "big")
#             self.protocol.sendto(dt,addr=addr)
#         elif (self.grid[0] - 1) % self.sz[0] == y and self.grid[1] == x:
#             self.d = addr
#             dt = bytearray(GridNode.GREET_b)
#             dt = dt + int(3).to_bytes(1,byteorder = "big") + self.tcp_port.to_bytes(4,byteorder = "big")
#             self.protocol.sendto(dt,addr=addr)
#             dt = bytearray(GridNode.FRWRD_b)
#             dt = dt + addr[1].to_bytes(4,byteorder = "big") + addr[0].encode("utf-8")
#             for a in self.waiting_down:
#                 self.protocol.sendto(dt,addr=a)
#         elif (self.grid[1] + 1) % self.sz[1] == x and self.grid[0] == y:
#             self.r = addr
#             dt = bytearray(GridNode.GREET_b)
#             dt = dt + int(4).to_bytes(1,byteorder = "big") + self.tcp_port.to_bytes(4,byteorder = "big")
#             self.protocol.sendto(dt,addr=addr)
#             dt = bytearray(GridNode.FRWRD_b)
#             dt = dt + addr[1].to_bytes(4,byteorder = "big") + addr[0].encode("utf-8")
#             for a in self.waiting_right:
#                 self.protocol.sendto(dt,addr=a)
#         elif (self.grid[1] - 1) % self.sz[1] == x and self.grid[0] == y:
#             dt = bytearray(GridNode.GREET_b)
#             dt = dt + int(2).to_bytes(1,byteorder = "big") + self.tcp_port.to_bytes(4,byteorder = "big")
#             self.protocol.sendto(dt,addr=addr)
#             self.l = addr
#         if not ((self.grid[0] + 1) % self.sz[0] == y and self.grid[1] == x) and not ((self.grid[1] + 1) % self.sz[1] == x and self.grid[0] == y):
#             if dir == 1:
#                 if self.r == None:
#                     self.waiting_right.append(addr)
#                 else:
                    
#                     dt = bytearray(GridNode.FRWRD_b)
#                     dt = dt + self.r[1].to_bytes(4,byteorder = "big") + self.r[0].encode("utf-8")
#                     self.protocol.sendto(dt,addr=addr)
#             else:
#                 print("wait on down")
#                 if self.d == None:
#                     self.waiting_down.append(addr)
#                 else:
                    
#                     dt = bytearray(GridNode.FRWRD_b)
#                     dt = dt + self.d[1].to_bytes(4,byteorder = "big") + self.d[0].encode("utf-8")
#                     self.protocol.sendto(dt,addr=addr)

#     def handle_request(self,addr,data):
#         print(data)
#         if data[0] == GridNode.MEET:
            
#             y = data[1]
#             x = data[2]
#             dir = data[3]
#             print("met from ",y,x,dir,addr)
#             diff_y = min(abs(self.grid[0] - y),abs(self.grid[0]-self.sz[0] - y),abs(self.grid[0]+self.sz[0] - y))
#             diff_x = min(abs(self.grid[1] - x),abs(self.grid[1]-self.sz[1] - x),abs(self.grid[1]+self.sz[1] - x))
#             self.perform2(diff_y,diff_x,data,x,y,addr,dir)
                
            
#         elif data[0] == GridNode.FRWRD:
#             tmpp = int.from_bytes(data[1:5], byteorder="big")
#             tmpi = data[5:].decode("utf-8")
#             print("forwarded to ",tmpi,tmpp)
#             dt = bytearray(GridNode.MEET_b)
#             dt = dt + self.grid[0].to_bytes(1,byteorder = "big") + self.grid[1].to_bytes(1,byteorder = "big") + self.udp_port.to_bytes(4,byteorder = "big")
#             self.protocol.sendto(dt,(tmpi,tmpp))
#         elif data[0] == GridNode.GREET:
#             print("greet", data[1])
#             dir = data[1]
#             if dir == 1:
#                 self.d = addr
#                 dt = bytearray(GridNode.FRWRD_b)
#                 dt = dt + addr[1].to_bytes(4,byteorder = "big") + addr[0].encode("utf-8")
#                 for a in self.waiting_down:
#                     self.protocol.sendto(dt,addr=a)
#             elif dir == 2:
#                 self.r = addr
#                 dt = bytearray(GridNode.FRWRD_b)
#                 dt = dt + addr[1].to_bytes(4,byteorder = "big") + addr[0].encode("utf-8")
#                 for a in self.waiting_right:
#                     self.protocol.sendto(dt,addr=a)
#             elif dir == 3:
#                 self.u = addr
#             elif dir == 4:
#                 self.l = addr
#         print(self.u,self.r,self.l,self.d)
            
        

class Node(object):
    def __init__(self,  protocol: AbstractProtocol, ip_addr = "0.0.0.0", port = None, call_back: Callable[[tuple[str,int], bytes], None] = lambda addr, data: print(addr,data)) -> None:
        if port == None:
            port = find_open_port()
        self.port = port
        self.ip_addr = ip_addr
        self.call_back = call_back
        self.peers: dict[bytes,tuple[str,int]] = dict()
        print(f"Node listening on {ip_addr}:{port}")
        self.protocol_type = protocol
        pass

    async def listen(self):
        loop = asyncio.get_running_loop()
        listen = loop.create_datagram_endpoint(self.protocol_type.get_lowest, local_addr=(self.ip_addr, self.port))
        self.transport, self.protocol = await listen
        await self.protocol_type.start()
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



        
    

