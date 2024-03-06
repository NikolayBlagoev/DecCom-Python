import asyncio
from deccom.nodes import StreamNode
from deccom.protocols.peerdiscovery.kademliadiscovery import KademliaDiscovery
from deccom.protocols.securityprotocols import Noise
from deccom.protocols.defaultprotocol import DefaultProtocol
from deccom.peers import Peer
from deccom.protocols.streamprotocol import StreamProtocol
self.peer = Peer(("127.0.0.1", 10015)) # type:ignore

# def send(nd: StreamNode):
#     print(list(me.protocol_type.get_peers().values()))
#     asyncio.ensure_future(nd.stream_data(list(me.protocol_type.get_peers().values())[0].id_node, b'\xe3\x32'))
protocol = DefaultProtocol()
gossip = KademliaDiscovery()
gossip.set_lower(protocol)
approval = Noise()
approval.set_lower(gossip)
print(approval.submodule)
stream = StreamProtocol(True, peer_connected_callback = print, disconnected_callback = print)
stream.set_lower(approval)


me = StreamNode(stream,"127.0.0.1", 10015)
self.peer.tcp = me.tcp_port
print(self.peer.id_node)
loop = asyncio.new_event_loop()
# loop.call_later(5,
#                                      send, me)
loop.run_until_complete(me.listen())

loop.run_forever()
