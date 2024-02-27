import asyncio
import random
from deccom.utils.common import ternary_comparison
from asyncio import exceptions
from typing import Any, Callable, List
from deccom.peers.peer import Peer
from deccom.protocols.abstractprotocol import AbstractProtocol
class DictItem:
    def __init__(self,reader: asyncio.StreamReader,writer: asyncio.StreamWriter,fut: asyncio.Future, opened_by_me: int) -> None:
        self.reader = reader
        self.writer = writer
        self.fut = fut
        self.opened_by_me = opened_by_me
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
                    "_lower_ping": "send_ping",
                    "peer_connected": "set_connected_callback",
                    "process_data": "set_stream_callback",
                    "_lower_get_peer": "get_peer",
                    
                })
    required_lower = AbstractProtocol.required_lower + ["send_ping","get_peer", "set_connected_callback", "set_disconnected_callback"]
    def __init__(self, always_connect: bool, submodule=None, callback: Callable[[tuple[str, int], bytes], None] = lambda addr, data: print(addr, data),disconnected_callback = lambda addr,nodeid: print(nodeid, "disconnected"), 
                peer_connected_callback = lambda addr, peer: ..., stream_callback = lambda data, node_id, addr: ..., stream_close_callback = lambda node_id,addr: ...):
        super().__init__(submodule, callback)
        self.stream_callback = stream_callback
        self.peer_connected_callback = peer_connected_callback
        self.disconnected_callback = disconnected_callback
        self.stream_close_callback = stream_close_callback
        self.connections: dict[bytes, DictItem]= dict()
        self._lower_ping = lambda : ...
        self._lower_get_peer = lambda : ...
        self.always_connect = always_connect
        
    
    async def handle_connection(self, reader: asyncio.StreamReader,writer: asyncio.StreamWriter, node_id: Any = None, addr: Any = None):
        print("CONNECTION FROM PEER")
        try:
            data = await  asyncio.wait_for(reader.readline(), timeout=10)
            
        except exceptions.TimeoutError:
            print('PEER DID NOT INTRODUCE THEMSELVES')
            writer.close()
            return
        if len(data)<5 or data[0:4] != b'\xe4\xe5\xf3\xc6':
            
            writer.close()
            return
        node_id = data[4:-1]
        # print("connection from",node_id)
        if self.connections.get(node_id) != None:
            print("duplicate connection RECEIVED")
            print(self.connections.get(node_id).opened_by_me,ternary_comparison(Peer.me.id_node, node_id))
            if self.connections.get(node_id).opened_by_me * ternary_comparison(Peer.me.id_node, node_id) == -1:
                print("closing previous, keeping new")
                self.remove_from_dict(node_id)
            else:
                print("keeping old one")
                writer.close()
                return
        self.connections[node_id] = DictItem(reader,writer,None, -1)
        self.connections[node_id].fut = asyncio.ensure_future(self.listen_for_data(reader,node_id,addr))
        return
    
    def peer_connected(self,addr,peer: Peer):
        # print("here", nodeid)
        
        # print(peer.tcp)
        if self.always_connect and peer != None and peer.tcp != None:
            if self.connections.get(peer.id_node) == None:
                
                asyncio.ensure_future(self.open_connection(peer.addr[0], peer.tcp, peer.id_node))
        self.peer_connected_callback(peer)
        return
    async def send_ping(self, addr, success, fail, timeout):
        await self._lower_ping(addr, success, fail, timeout)
    async def open_connection(self, remote_ip, remote_port, node_id: bytes, duplicate = False):
        # print("connection to",remote_port, node_id)
        if node_id==Peer.get_current():
            print("OPENING TO SELF???")
            return
        if remote_port == None:
        	return None
        if self.connections.get(node_id) != None:
            # print("duplicate connection OPENED")
            
            if self.connections.get(node_id).opened_by_me * ternary_comparison(Peer.me.id_node, node_id) == -1:
                # print("closing previous, keeping new")
                self.remove_from_dict(node_id)
            else:
                # print("keeping old one")
                return
        try:
            reader, writer = await asyncio.open_connection(
                        remote_ip, remote_port)
        except ConnectionRefusedError:
            print("BROKEN")
            return
        self.connections[node_id] = DictItem(reader,writer,None,1)
        self.connections[node_id].fut = asyncio.ensure_future(self.listen_for_data(reader,node_id,(remote_ip,remote_port)))
        # print("introducing myself :)")
        writer.write(b'\xe4\xe5\xf3\xc6')
        writer.write(Peer.me.id_node)
        writer.write(b'\n')
        await writer.drain()
    def set_connected_callback(self, callback):
        self.peer_connected_callback = callback
    async def listen_for_data(self, reader: asyncio.StreamReader, node_id = None, addr = None):
        
        # seqrand = random.randint(1,40000)
        # print("listening ", seqrand)
        data = await reader.read(32)
        
        
        if data == b'':
            if node_id !=None and self.connections.get(node_id) != None:
                self.connections[node_id].fut = None
            print("closing", addr,node_id)
            self.remove_from_dict(node_id)
            self.closed_stream(node_id, addr)
            return
        buffer = bytearray()
        i = int.from_bytes(data,byteorder="big")
        while i > 0:
            data = await reader.read(9048)
            i -= len(data)
            buffer+=data
        # print(seqrand,"read",len(buffer), "from",self.get_peer(node_id).pub_key)
        asyncio.ensure_future(self.process_data(buffer,node_id,addr))
        self.connections[node_id].fut = asyncio.ensure_future(self.listen_for_data(reader,node_id,addr))
    async def send_stream(self, node_id, data):
        if self.connections.get(node_id) == None: 
            print("CANT FIND???")
            return
        print("writing",len(data))
        self.connections[node_id].writer.write(len(data).to_bytes(32,byteorder="big"))
        await self.connections[node_id].writer.drain()
        self.connections[node_id].writer.write(data)
        await self.connections[node_id].writer.drain()
        # print("done srream")
    def set_stream_close_callback(self, callback):
        self.stream_close_callback = callback    
    async def process_data(self,data,node_id,addr):
        # print("RECEIVED FROM",node_id)
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
    