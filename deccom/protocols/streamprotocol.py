import asyncio
from datetime import datetime
import random
from deccom.cryptofuncs.hash import SHA256
from deccom.utils.common import ternary_comparison
from asyncio import exceptions
from typing import Any, Callable, List, Union
from deccom.peers.peer import Peer
from deccom.protocols.abstractprotocol import AbstractProtocol
from deccom.protocols.wrappers import *
import socket
class DictItem:
    def __init__(self,reader: asyncio.StreamReader,writer: asyncio.StreamWriter,fut: asyncio.Future, opened_by_me: int) -> None:
        self.reader = reader
        self.writer = writer
        self.fut = fut
        self.opened_by_me = opened_by_me
        self.using = 0
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
    required_lower = AbstractProtocol.required_lower + ["get_peer", "set_connected_callback", "set_disconnected_callback"]
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
        
        
        # self.lock = asyncio.Lock()
        
    
    async def handle_connection(self, reader: asyncio.StreamReader,writer: asyncio.StreamWriter, node_id: Any = None, addr: Any = None):
        print("CONNECTION FROM PEER",  writer.get_extra_info('peername'))
        addr = writer.get_extra_info('peername')
        try:
            data = await  asyncio.wait_for(reader.readline(), timeout=10)
            
        except exceptions.TimeoutError:
            print('PEER DID NOT INTRODUCE THEMSELVES')
            writer.close()
            return
        if len(data)<5 or data[0:4] != b'\xe4\xe5\xf3\xc6':
            print("wrong introduction")
            writer.close()
            return
        node_id = data[4:-1]
        if self.locks.get(node_id) == None:
            self.locks[node_id] = asyncio.Lock()
        # print("connection from",node_id)
        if self.connections.get(node_id) != None:
            print("duplicate connection RECEIVED")
            #rint(self.connections.get(node_id).opened_by_me,ternary_comparison(self.peer.id_node, node_id))
            if self.connections.get(node_id).opened_by_me * ternary_comparison(self.peer.id_node, node_id) == -1:
                print("closing previous, keeping new")
                self.remove_from_dict(node_id)
            else:
                print("keeping old one")
                writer.close()
                return
        self.connections[node_id] = DictItem(reader,writer,None, -1)
        self.connections[node_id].fut = asyncio.ensure_future(self.listen_for_data(reader,node_id,addr))
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
    
    async def open_connection(self, remote_ip, remote_port, node_id: bytes, s =  None):
        # print("connection to",remote_port, node_id)
        if node_id==self.peer:
            print("OPENING TO SELF???")
            return False
        
        if remote_port == None:
            print("empty remote port")
            return False
        if self.connections.get(node_id) == None and self.await_connections.get(node_id) != None and not self.await_connections[node_id].done():
            await self.await_connections[node_id]
        
        if self.connections.get(node_id) != None:
            print("duplicate connection OPENED")
            self.connections.get(node_id).using += 1
            return True
        
        if s == None:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) 
            s.bind((self.peer.addr[0], self.peer.tcp))
        self.await_connections[node_id] = asyncio.Future()
        try:
            print(remote_ip, remote_port)
            s.connect((remote_ip,remote_port))
            reader, writer = await asyncio.wait_for(asyncio.open_connection(sock = s), timeout=4)
            if self.locks.get(node_id) == None:
                self.locks[node_id] = asyncio.Lock()
        except ConnectionRefusedError as e:
            with open(f"log{self.peer.pub_key}.txt", "a") as log:
                log.write("connection refused\n")
            self.await_connections[node_id].set_result(False)
            print("BROKEN SOMETHING", e)
            return False
        self.connections[node_id] = DictItem(reader,writer,None,1)
        self.connections[node_id].fut = asyncio.ensure_future(self.listen_for_data(reader,node_id,(remote_ip,remote_port)))
        print("introducing myself :)")
        async with self.locks[node_id]:
            writer.write(b'\xe4\xe5\xf3\xc6')
            writer.write(self.peer.id_node)
            writer.write(b'\n')
            
            await writer.drain()
        self.await_connections[node_id].set_result(True)
        print(self.connections)
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
    async def listen_for_data(self, reader: asyncio.StreamReader, node_id = None, addr = None):
        
        # seqrand = random.randint(1,40000)
        print("listening for data")
        try:
            data = await reader.read(32)
        except (ConnectionResetError, BrokenPipeError) as e:
            with open(f"log{self.peer.pub_key}.txt", "a") as log:
                log.write(datetime.now().strftime("%d/%m/%Y, %H:%M:%S"))
                log.write(f" closed because reset from {node_id}\n")
                log.write(e)
                log.write("\n")
            async with self.locks[node_id]:
                if node_id !=None and self.connections.get(node_id) != None:
                    self.connections[node_id].fut = None
                print("closing because reset", addr,node_id)
                self.remove_from_dict(node_id)
                self.closed_stream(node_id, addr)
                return

        
        if data == b'':
            async with self.locks[node_id]:
                if node_id !=None and self.connections.get(node_id) != None:
                    self.connections[node_id].fut = None
                print("closing because received empty bytes", addr,node_id)
                self.remove_from_dict(node_id)
                self.closed_stream(node_id, addr)
                return
        buffer = bytearray()
        i = int.from_bytes(data,byteorder="big")
        with open(f"log{self.peer.pub_key}.txt", "a") as log:
            log.write(datetime.now().strftime("%d/%m/%Y, %H:%M:%S"))
            log.write(f" will from {self.get_peer(node_id).pub_key} {i} {len(data)}\n")
        
        while i > 0:
            data = await reader.read(min(i, 9048))
            if data == b'':
                async with self.locks[node_id]:
                    if node_id !=None and self.connections.get(node_id) != None:
                        self.connections[node_id].fut = None
                    print("closing because received empty bytes", addr,node_id)
                    self.remove_from_dict(node_id)
                    self.closed_stream(node_id, addr)
                    return
            i -= len(data)
            buffer+=data
        with open(f"log{self.peer.pub_key}.txt", "a") as log:
            log.write(datetime.now().strftime("%d/%m/%Y, %H:%M:%S"))
            log.write(f" receive from {self.get_peer(node_id).pub_key} {len(buffer)}\n")
        # print(seqrand,"read",len(buffer), "from",self.get_peer(node_id).pub_key)
        loop = asyncio.get_event_loop()
        asyncio.run_coroutine_threadsafe(self._caller(buffer,node_id,addr), loop)
        
        self.connections[node_id].fut = asyncio.ensure_future(self.listen_for_data(reader,node_id,addr))
    async def send_stream(self, node_id, data):
        print(self.connections)
        if self.connections.get(node_id) == None: 
            print("CANT FIND???")
            return
        async with self.locks[node_id]:
            with open(f"log{self.peer.pub_key}.txt", "a") as log:
                log.write(datetime.now().strftime("%d/%m/%Y, %H:%M:%S"))
                log.write(f" sending to {self.get_peer(node_id).pub_key} {len(data)}\n")

            self.connections[node_id].writer.write(len(data).to_bytes(32,byteorder="big"))
            await self.connections[node_id].writer.drain()
            self.connections[node_id].writer.write(data)
            await self.connections[node_id].writer.drain()
        # print("done srream")
    def set_stream_close_callback(self, callback):
        self.stream_close_callback = callback    
    async def _caller(self,data,node_id,addr):
        self.stream_callback(data,node_id,addr)
    @bindfrom("stream_callback")
    def process_data(self,data,node_id,addr):
        
        self.stream_callback(data,node_id,addr)
    def remove_from_dict(self,nodeid):
        if self.connections.get(nodeid) == None:
            return
        # print("removing...")
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
    