import asyncio
from deccom.nodes import StreamNode
from deccom.protocols.abstractprotocol import AbstractProtocol
from deccom.protocols.peerdiscovery.kademliadiscovery import KademliaDiscovery
from deccom.protocols.securityprotocols import Noise
from deccom.protocols.defaultprotocol import DefaultProtocol
from deccom.peers import Peer
from deccom.protocols.streamprotocol import StreamProtocol
Peer.me = Peer(("127.0.0.1", 10015)) # type:ignore

# def send(nd: StreamNode):
#     print(list(me.protocol_type.get_peers().values()))
#     asyncio.ensure_future(nd.stream_data(list(me.protocol_type.get_peers().values())[0].id_node, b'\xe3\x32'))
protocol = DefaultProtocol()
gossip = KademliaDiscovery()
gossip.set_lower(protocol)
print("\n\n",protocol._taken)

print(protocol.callback)
print(gossip._lower_sendto)
