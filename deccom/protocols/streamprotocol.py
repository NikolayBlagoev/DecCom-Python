import asyncio
from os import urandom
from datetime import datetime
from deccom.utils.common import ternary_comparison
from asyncio import exceptions, IncompleteReadError
from typing import Any, Callable, List, Union
from deccom.peers.peer import Peer
from deccom.protocols.abstractprotocol import AbstractProtocol
from deccom.protocols.wrappers import *
import socket
import traceback
class DictItem:
    def __init__(self,reader: asyncio.StreamReader,writer: asyncio.StreamWriter,fut: asyncio.Future, opened_by_me: int) -> None:
        self.reader = reader
        self.writer = writer
        self.fut = fut
        self.opened_by_me = opened_by_me
        self.using = 0
        self.unique_id = None
        self.in_use = True
        self.confirmed = False
        pass
    
    
    

class StreamProtocol(AbstractProtocol):
    offers = dict(AbstractProtocol.offers,**{  
                
                "disconnected_callback": "set_disconnected_callback",
                "get_peer": "get_peer",
                "connected_callback": "set_connected_callback",
                "stream_callback": "set_stream_callback",
                "stream_close_callback": "set_stream_close_callback",
                "open_connection": "open_connection",
                "send_stream": "send_stream",
                "process_data": "process_data",
                "send_ping": "send_ping",
                "set_peer_connected_callback": "set_connected_callback"
                })
    bindings = dict(AbstractProtocol.bindings, **{
                    "remove_peer":"set_disconnected_callback",
                    "peer_connected": "set_connected_callback",
                    "process_data": "set_stream_callback",
                    "_lower_get_peer": "get_peer",
                    
                })
    required_lower = AbstractProtocol.required_lower + ["get_peer"]
    def __init__(self, always_connect: bool, submodule=None, callback: Callable[[tuple[str, int], bytes], None] = lambda addr, data: print(addr, data),disconnected_callback = lambda addr,nodeid: print(nodeid, "disconnected"), 
                connected_callback = lambda addr, peer: ..., stream_callback = lambda data, node_id, addr: ..., stream_close_callback = lambda node_id,addr: ...):
        super().__init__(submodule, callback)
        self.stream_callback = stream_callback
        self.connected_callback = connected_callback
        self.disconnected_callback = disconnected_callback
        self.stream_close_callback = stream_close_callback
        self.connections: dict[bytes, DictItem]= dict()
        self.locks: dict[bytes, asyncio.Lock] = dict()
        self.always_connect = always_connect
        self.await_connections = dict()
        
    async def stop(self):
        for k,v in self.connections.items():
            async with self.locks[k]:
                v.writer.close()
                if v.fut != None:
                    v.fut.cancel()
        self.connections.clear()
        self.locks.clear()
        self.await_connections.clear()
        return await super().stop()
    
    async def handle_connection(self, reader: asyncio.StreamReader,writer: asyncio.StreamWriter, node_id: Any = None, addr: Any = None):
        #print("CONNECTION FROM PEER",  writer.get_extra_info('peername'))
        with open(f"log{self.peer.pub_key}.txt", "a") as log:
            log.write(f"connection from {writer.get_extra_info('peername')}\n")
        addr = writer.get_extra_info('peername')
        try:
            data = await  asyncio.wait_for(reader.readexactly(36), timeout=10)
            
        except exceptions.TimeoutError:
            with open(f"log{self.peer.pub_key}.txt", "a") as log:
                log.write(f"peer {addr} did not introduce themselves\n")
            writer.close()
            return
        if len(data)<5 or data[0:4] != b'\xe4\xe5\xf3\xc6':
            with open(f"log{self.peer.pub_key}.txt", "a") as log:
                log.write(f"wrong introduction \n")
            writer.close()
            return
        node_id = data[4:]
        with open(f"log{self.peer.pub_key}.txt", "a") as log:
            log.write(f"connection is from {addr} {self.get_peer(node_id).pub_key}\n")
        if self.locks.get(node_id) == None:
            self.locks[node_id] = asyncio.Lock()
        # print("connection from",node_id)
        if self.connections.get(node_id) != None:
            
            with open(f"log{self.peer.pub_key}.txt", "a") as log:
                log.write(f"duplicate connection from {addr} {self.get_peer(node_id).pub_key}\n")
            
            if self.connections.get(node_id).opened_by_me * ternary_comparison(self.peer.id_node, node_id) == -1:
                with open(f"log{self.peer.pub_key}.txt", "a") as log:
                    log.write(f"closing previous with {addr} {self.get_peer(node_id).pub_key}\n")
                self.remove_from_dict(node_id)
            else:
                with open(f"log{self.peer.pub_key}.txt", "a") as log:
                    log.write(f"keeping old one with {addr} {self.get_peer(node_id).pub_key}\n")
                writer.close()
                return
        writer.write(int(0).to_bytes(32,byteorder="big"))
        await writer.drain()
        with open(f"log{self.peer.pub_key}.txt", "a") as log:
            log.write(f"listening from {addr} {self.get_peer(node_id).pub_key}\n")
        self.connections[node_id] = DictItem(reader,writer,None, -1)
        self.connections[node_id].unique_id = urandom(4)
        self.connections[node_id].confirmed = True
        self.connections[node_id].fut = asyncio.ensure_future(self.listen_for_data(reader,node_id,addr,self.connections[node_id].unique_id))
        return
    
    @bindto("get_peer")
    def get_peer(self, id) -> Union[Peer,None]:
        return None
    
    @bindfrom("connected_callback")
    def peer_connected(self,addr,peer: Peer):
        # print("here", nodeid)
        
        # print(peer.tcp)
        if self.always_connect and peer != None and peer.tcp != None:
            if self.connections.get(peer.id_node) == None:
                loop = asyncio.get_event_loop()
                loop.create_task(self.open_connection(peer.addr[0], peer.tcp, peer.id_node))
                
        self.connected_callback(addr,peer)
        return
    
    async def open_connection(self, remote_ip, remote_port, node_id: bytes, port_listen =  None):
        # print("connection to",remote_port, node_id)
        if node_id==self.peer:
            print("OPENING TO SELF???")
            return False
        
        if remote_port == None:
            
            return False
        
        if self.connections.get(node_id) == None and self.await_connections.get(node_id) != None:
            
            return await self.await_connections[node_id]
        
        
        if self.connections.get(node_id) != None:
            # print("duplicate connection OPENED")
            self.connections.get(node_id).using += 1
            return True
        loop = asyncio.get_event_loop()
        
        self.await_connections[node_id] = loop.create_future()
        
        
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        
        if hasattr(socket, 'SO_REUSEPORT'):
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1) 
        else:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) 

        
        
        s.bind((self.peer.addr[0], self.peer.tcp if port_listen == None else port_listen))
        
        try:
            
            s.connect((remote_ip,remote_port))
            reader, writer = await asyncio.wait_for(asyncio.open_connection(sock = s), timeout=10)
            
            if self.locks.get(node_id) == None:
                self.locks[node_id] = asyncio.Lock()
        except ConnectionRefusedError as e:
            with open(f"log{self.peer.pub_key}.txt", "a") as log:
                log.write("connection refused\n")
            self.await_connections[node_id].set_result(False)
            
            s.close()
            
            print("BROKEN SOMETHING ?")
            return False
        except asyncio.TimeoutError as e:
            print("timed out...")
            print(e.with_traceback())
            
            s.close()
            
            return False
        self.connections[node_id] = DictItem(reader,writer,None,1)
        self.connections[node_id].unique_id = urandom(4)
        self.connections[node_id].fut = asyncio.ensure_future(self.listen_for_data(reader,node_id,(remote_ip,remote_port),self.connections[node_id].unique_id ))
        #print("introducing myself :)")
        async with self.locks[node_id]:
            writer.write(b'\xe4\xe5\xf3\xc6')
            writer.write(self.peer.id_node)
            
            with open(f"log{self.peer.pub_key}.txt", "a") as log:
                log.write(f"introducing with {len(self.peer.id_node)} \n ")
            
            await writer.drain()
            await self.await_connections[node_id]
        
        
        #del self.await_connections[node_id]
        self.connections.get(node_id).using += 1
        return True
    def set_connected_callback(self, callback):
        self.connected_callback = callback


    async def close_stream(self, node_id: bytes, user = False) -> bool:
        if self.connections.get(node_id) == None:
            return False
        if user:
            self.connections.get(node_id).using -= 1
        
        if self.connections.get(node_id).using > 0:
            return False
        async with self.locks[node_id]:
            
            if self.connections.get(node_id) != None:
                self.connections[node_id].fut = None
            print("closing")
            self.remove_from_dict(node_id)
            
            return True
    async def listen_for_data(self, reader: asyncio.StreamReader, node_id = None, addr = None, uniq_id = None):
        
        if self.connections.get(node_id) == None or self.connections[node_id].unique_id != uniq_id:
            return
        # seqrand = random.randint(1,40000)
        #print("listening for data")
        # with open(f"log{self.peer.pub_key}.txt", "a") as log:
        #     log.write(f"listening for data {node_id} \n")
            
        try:
            data = await reader.readexactly(32)
        except (ConnectionResetError, BrokenPipeError,IncompleteReadError) as e:
            with open(f"log{self.peer.pub_key}.txt", "a") as log:
                log.write(datetime.now().strftime("%d/%m/%Y, %H:%M:%S"))
                log.write(f" closed because reset from {node_id}\n")
                # log.write(e)
                log.write("\n")
            async with self.locks[node_id]:
                if self.connections[node_id].unique_id != uniq_id:
                    return
                if node_id !=None and self.connections.get(node_id) != None:
                    self.connections[node_id].fut = None
                print("closing because reset", addr,node_id)
                self.remove_from_dict(node_id)
                self.closed_stream(node_id, addr)
                return
        
        
        if data == b'':
            async with self.locks[node_id]:
                if self.connections[node_id].unique_id != uniq_id:
                    return
                if node_id !=None and self.connections.get(node_id) != None:
                    self.connections[node_id].fut = None
                print("closing because received empty bytes", addr,node_id)
                self.remove_from_dict(node_id)
                self.closed_stream(node_id, addr)
                return
        buffer = bytearray()
        i = int.from_bytes(data,byteorder="big")
        if i != 0:
            with open(f"log{self.peer.pub_key}.txt", "a") as log:
                # log.write(datetime.now().strftime("%d/%m/%Y, %H:%M:%S"))
                log.write(f" will from {self.get_peer(node_id).pub_key} {i} {len(data)}\n")
            
            while i > 0:
                data = await reader.read(min(i, 9048))
                if data == b'':
                    async with self.locks[node_id]:
                        if self.connections[node_id].unique_id != uniq_id:
                            return
                        if node_id !=None and self.connections.get(node_id) != None:
                            self.connections[node_id].fut = None
                        # print("closing because received empty bytes", addr,node_id)
                        self.remove_from_dict(node_id)
                        self.closed_stream(node_id, addr)
                        return
                i -= len(data)
                buffer+=data
            # with open(f"log{self.peer.pub_key}.txt", "a") as log:
            #     log.write(datetime.now().strftime("%d/%m/%Y, %H:%M:%S"))
            #     log.write(f" receive from {self.get_peer(node_id).pub_key} {len(buffer)}\n")
            # print(seqrand,"read",len(buffer), "from",self.get_peer(node_id).pub_key)
            loop = asyncio.get_event_loop()
            asyncio.run_coroutine_threadsafe(self._caller(buffer,node_id,addr), loop)
        else:
            self.connections[node_id].confirmed = True
            self.await_connections[node_id].set_result(True)
        loop = asyncio.get_event_loop()
        self.connections[node_id].fut = asyncio.ensure_future(self.listen_for_data(reader,node_id,addr,uniq_id))
    async def send_stream(self, node_id, data, lvl = 0):
        
        if self.connections.get(node_id) == None or lvl >= 3: 
            
            return False
        try:
            async with self.locks[node_id]:
                with open(f"log{self.peer.pub_key}.txt", "a") as log:
                    # log.write(datetime.now().strftime("%d/%m/%Y, %H:%M:%S"))
                    log.write(f" sending to {self.get_peer(node_id).pub_key} {len(data)}\n")

                self.connections[node_id].writer.write(len(data).to_bytes(32,byteorder="big"))
                await self.connections[node_id].writer.drain()
                self.connections[node_id].writer.write(data)
                await self.connections[node_id].writer.drain()
        except ConnectionResetError:
            with open(f"log{self.peer.pub_key}.txt", "a") as log:
                # log.write(datetime.now().strftime("%d/%m/%Y, %H:%M:%S"))
                log.write(f" cannot send to {self.get_peer(node_id).pub_key} {len(data)}\n")
            await asyncio.sleep(3)
            p: Peer = self.get_peer(node_id)
            if p == None:
                return False
            ret = await self.open_connection(p.addr[0],p.tcp, p.id_node, port_listen = 0)
            if ret == False:
                return False
            with open(f"log{self.peer.pub_key}.txt", "a") as log:
                # log.write(datetime.now().strftime("%d/%m/%Y, %H:%M:%S"))
                log.write(f"Resetting sending to {node_id}\n")
            return await self.send_stream(node_id,data, lvl=lvl+1)
        with open(f"log{self.peer.pub_key}.txt", "a") as log:
                # log.write(datetime.now().strftime("%d/%m/%Y, %H:%M:%S"))
                log.write(f" finished sending to {self.get_peer(node_id).pub_key} {len(data)}\n")
        # print("done srream")
        return True
    def set_stream_close_callback(self, callback):
        self.stream_close_callback = callback    
    async def _caller(self,data,node_id,addr):
        # print("received data... ", len(data))
        try:
            self.stream_callback(data,node_id,addr)
        except Exception:
                traceback.print_exc(file=log)
    @bindfrom("stream_callback")
    def process_data(self,data,node_id,addr):
        
        self.stream_callback(data,node_id,addr)
    def remove_from_dict(self,nodeid):
        if self.connections.get(nodeid) == None:
            return
        # print("removing...")
        if not self.connections[nodeid].confirmed:
            self.await_connections[nodeid].set_result(False)
        if self.connections[nodeid].fut != None:
            # print("cancelling task...")
            self.connections[nodeid].fut.cancel()
        if self.connections[nodeid].writer != None:
            self.connections[nodeid].writer.close()
        del self.connections[nodeid]
        
        return
    def set_stream_callback(self, callback):
        self.stream_callback = callback
    def closed_stream(self, node_id, addr):
        self.stream_close_callback(node_id,addr)
    @bindfrom("disconnected_callback")
    def remove_peer(self, addr, nodeid):
        self.remove_from_dict(nodeid)
        self.disconnected_callback(addr,nodeid) 
    def set_disconnected_callback(self, callback):
        self.disconnected_callback = callback
    def get_lowest_stream(self):
        submodule = self.submodule
        while submodule != None and not hasattr(submodule, "get_lowest_stream") and hasattr(submodule, "submodule") :
            submodule = submodule.submodule
        if submodule != None and hasattr(submodule, "get_lowest_stream"):
            ret = submodule.get_lowest_stream()
            if ret == None:
                return self
            else:
                return ret
        else:
            
            return self


    def has_connection(self, node_id):
        return self.connections.get(node_id) != None
    