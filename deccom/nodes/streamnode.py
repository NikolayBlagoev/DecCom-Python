
import asyncio
from typing import Callable
from deccom.nodes.node import Node
from deccom.peers.peer import Peer
from deccom.utils.common import find_open_port
from deccom.protocols.streamprotocol import StreamProtocol
from deccom.cryptofuncs import SHA256
class StreamNode(Node):
    def __init__(self, p: Peer, protocol: StreamProtocol, ip_addr="0.0.0.0", port=None, tcp_port = None, call_back: Callable[[tuple[str, int], bytes], None] = lambda addr, data: print(addr, data)) -> None:
        super().__init__(p, protocol, ip_addr, port, call_back)
        if tcp_port == None:
            tcp_port = find_open_port()
        self.protocol_type = protocol
        self.tcp_port = tcp_port
        p.tcp = tcp_port
        # print("tcp_port", tcp_port)
        self.peer_reads = dict()
        self.peer_writes = dict()
    async def listen(self):
        loop = asyncio.get_running_loop()
        listen = loop.create_datagram_endpoint(self.protocol_type.get_lowest, local_addr=(self.ip_addr, self.port))
        self.transport, self.protocol = await listen
        print(self.protocol_type.get_lowest_stream().handle_connection)
        self.server = await asyncio.start_server(
                self.protocol_type.get_lowest_stream().handle_connection, self.ip_addr, self.tcp_port)
        
        await self.protocol_type.start(self.peer)
        
    async def stream_data(self, node_id, data):
        # print("sending stream")
        if not isinstance(node_id, bytes):
            node_id = SHA256(node_id)
        await self.protocol_type.send_stream(node_id,data)

        
    