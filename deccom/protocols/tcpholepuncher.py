import asyncio
from typing import Callable
from deccom.peers.peer import Peer
from deccom.protocols.streamprotocol import StreamProtocol
from deccom.protocols.wrappers import bindto
from deccom.utils.common import *

class TCPHolePuncher(StreamProtocol):
    REQUEST_TCP = int.from_bytes(b'\x11', byteorder="big")
    ANSWER_TCP = int.from_bytes(b'\x12', byteorder="big")
    REQUEST_CONNECTION = int.from_bytes(b'\x13', byteorder="big")
    ANSWER_CONNECTION = int.from_bytes(b'\x14', byteorder="big")
    def __init__(self, known_peers: list[Peer] =[], always_connect: bool = False, submodule=None, callback: Callable[[tuple[str, int], bytes], None] = lambda addr, data: print(addr, data),disconnected_callback = lambda addr,nodeid: print(nodeid, "disconnected"), 
                connected_callback = lambda addr, peer: ..., stream_callback = lambda data, node_id, addr: print, stream_close_callback = lambda node_id,addr: ...):
        self.known_peers = known_peers
        self.addresses_known: list[tuple[str,int]] = []
        self.futures: dict[bytes,asyncio.Future] = dict()
        self.known_tcp_pairs: list[tuple[bytes,str,int]] = []
        super().__init__(False, submodule, callback, disconnected_callback, connected_callback, stream_callback, stream_close_callback)
    
    async def start(self, p: Peer):
        await super().start(p)
        
        for p in self.known_peers:
            
            msg = bytearray([TCPHolePuncher.REQUEST_TCP])
            await self.send_datagram(msg,p.addr)

    async def stop(self):
        for _,v in self.futures.items():
            v.cancel()
        self.addresses_known.clear()
        self.futures.clear()
        self.known_tcp_pairs.clear()
        return await super().stop()
    def get_addr(self, writer):
        for addr in self.addresses_known:
            writer.write_ip(addr[0])
            writer.write_int(2, addr[1])
        writer.write_ip(self.peer.addr[0])
        writer.write_int(2, self.peer.tcp)

    def process_datagram(self, addr: tuple[str, int], data: bytes):
        print("from ",addr,data)
        if data[0] == TCPHolePuncher.REQUEST_TCP:
            writer = byte_writer(header=TCPHolePuncher.ANSWER_TCP)
            writer.write_raw(self.peer.id_node)
            self.get_addr(writer)
            loop = asyncio.get_event_loop()
            return loop.create_task(self.send_datagram(writer.bytes(),addr))
        elif data[0] == TCPHolePuncher.ANSWER_TCP:
            reader = byte_reader(data[1:])
            node_id = reader.read_next(32)
            addresses = []
            while not reader.is_done():
                addresses.append((reader.read_ip(), reader.read_next_int(2)))
                self.known_tcp_pairs.append((node_id, addresses[-1][0], addresses[-1][1]))
            loop = asyncio.get_event_loop()
            return loop.create_task(self.get_my_tcp(node_id,addresses))
        elif data[0] == TCPHolePuncher.REQUEST_CONNECTION:
            print("connection requested..")
            reader = byte_reader(data[1:])
            node_id = reader.read_next(32)
            addresses = []
            loop = asyncio.get_event_loop()
            while not reader.is_done():
                addresses.append((reader.read_ip(), reader.read_next_int(2)))
            loop.create_task(self.attempt_connection(node_id, addresses))

            writer = byte_writer(header=TCPHolePuncher.ANSWER_CONNECTION)
            writer.write_raw(self.peer.id_node)
            self.get_addr(writer)
            loop = asyncio.get_event_loop()
            print("will send them my addr")
            return loop.create_task(self.send_datagram(writer.bytes(),addr))
        elif data[0] == TCPHolePuncher.ANSWER_CONNECTION:
            print("answer to my connection")
            reader = byte_reader(data[1:])
            node_id = reader.read_next(32)
            if self.futures.get(node_id) != None:
                return
            addresses = []
            while not reader.is_done():
                addresses.append((reader.read_ip(), reader.read_next_int(2)))    
            loop = asyncio.get_event_loop()
            loop.create_task(self.attempt_connection(node_id, addresses))
        else:
            super().process_datagram(addr, data[1:])

    async def attempt_connection(self, node_id, addresses):
        for _ in range(3):
            print("attempting connection")
            for addr in addresses:
                ret = await self._lower_open_connection(addr[0], addr[1], node_id)
                print(ret)
                if ret:
                    print("connection was success...")
                    if self.futures.get(node_id) != None:
                        self.futures[node_id].set_result(True)
                    return
            print("sleeping...")
            await asyncio.sleep(2)
        if self.futures.get(node_id) != None:
            self.futures[node_id].set_result(False)
    
    async def get_my_tcp(self, node_id, addresses):
        for addr in addresses:
            print("getting my tcp")
            ret = await self._lower_open_connection(addr[0], addr[1], node_id)
            if ret:
                print("opening was successful")
                await self._lower_send_stream(node_id=node_id, data=bytearray([TCPHolePuncher.REQUEST_TCP]))
                return
            else:
                self.known_tcp_pairs.remove((node_id,addr[0],addr[1]))
    async def close_after(self, node_id, wait = 2, user = False):
        await asyncio.sleep(wait)
        if self.futures.get(node_id) == None:
            await self._lower_close_stream(node_id, user)

    
    def process_data(self, data, node_id, addr):
        print("got data",data)
        if data[0] == TCPHolePuncher.REQUEST_TCP:
            print("requested tcp",addr)
            msg = byte_writer(TCPHolePuncher.ANSWER_TCP)
            msg.write_ip(addr[0])
            msg.write_int(2, addr[1])
            loop = asyncio.get_event_loop()
            print("sending them their information...")
            loop.create_task(self._lower_send_stream(node_id, msg.bytes()))
            #loop.create_task(self.close_after(node_id))
        elif data[0] == TCPHolePuncher.ANSWER_TCP:
            print("got my tcp")
            reader = byte_reader(data[1:])
            myip = reader.read_ip()
            mytcp = reader.read_next_int(2)
            print(myip, mytcp)
            if (myip, mytcp) not in self.addresses_known:
                self.addresses_known.append((myip, mytcp))
            loop = asyncio.get_event_loop()
            return loop.create_task(self._lower_close_stream(node_id, True))
        else: 
            super().process_data(data[1:], node_id, addr)
    @bindto("open_connection")
    async def _lower_open_connection(self, remote_ip, remote_port, node_id: bytes):
        return

    async def open_connection(self, remote_ip, remote_port, node_id: bytes, keep_after: bool = False):
        if self._lower_has_connection(node_id):
            print("does have connection")
            return await self._lower_open_connection(remote_ip, remote_port, node_id)
        else:
            if self.futures.get(node_id) != None:
                return await self.futures.get(node_id)
            else:
                loop = asyncio.get_event_loop()
                fut = loop.create_future()
                ret = self.get_peer(node_id)
                if ret == None:
                    return False
                writer = byte_writer(header=TCPHolePuncher.REQUEST_CONNECTION)
                writer.write_raw(self.peer.id_node)
                self.get_addr(writer)
                loop.create_task(self.send_datagram(writer.bytes(), ret.addr))
                self.futures[node_id] = fut
                return await fut
    @bindto("send_stream")
    async def _lower_send_stream(self, node_id, data):
        return
    @bindto("close_stream")
    async def _lower_close_stream(self,  node_id: bytes, user: bool):
        return

    @bindto("has_connection")
    async def _lower_has_connection(self,  node_id: bytes) -> bool:
        return
    async def send_stream(self, node_id, data):
        if self._lower_has_connection(node_id):
            print("does have connection")
            await self._lower_send_stream(node_id, b'x\01' + data)
        else:
            if self.futures.get(node_id) != None:
                ret = await self.futures.get(node_id)
                
            else:
                print("didn't have it")
                loop = asyncio.get_event_loop()
                fut = loop.create_future()
                self.futures[node_id] = fut
                ret = self.get_peer(node_id)
                if ret == None:
                    return False
                writer = byte_writer(header=TCPHolePuncher.REQUEST_CONNECTION)
                writer.write_raw(self.peer.id_node)
                self.get_addr(writer)
                loop.create_task(self.send_datagram(writer.bytes(), ret.addr))
                ret = await fut
            if not ret:
                return
            print("sending")
            await self._lower_send_stream(node_id, b'x\01' + data)
                
        