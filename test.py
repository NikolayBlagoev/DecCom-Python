import asyncio
from deccom.nodes import StreamNode, Node
from deccom.protocols.abstractprotocol import AbstractProtocol
from deccom.protocols.peerdiscovery.kademliadiscovery import KademliaDiscovery
from deccom.protocols.securityprotocols import Noise
from deccom.protocols.defaultprotocol import DefaultProtocol
from deccom.peers import Peer
from deccom.protocols.streamprotocol import StreamProtocol
protocol = DefaultProtocol()
discovery = KademliaDiscovery()
discovery.set_lower(protocol)

peer = Peer(None)

me = Node(peer, discovery,"0.0.0.0", 10015)

print(peer.id_node)
loop = asyncio.new_event_loop()
print("run...")

loop.run_until_complete(me.listen())
loop.run_forever()



# def send(nd: StreamNode):
#     print(list(me.protocol_type.get_peers().values()))
#     asyncio.ensure_future(nd.stream_data(list(me.protocol_type.get_peers().values())[0].id_node, b'\xe3\x32'))
# protocol = DefaultProtocol()
# gossip = KademliaDiscovery()
# gossip.set_lower(protocol)
# print("\n\n",protocol._taken)

# print(protocol.callback)
# print(gossip._lower_sendto)
