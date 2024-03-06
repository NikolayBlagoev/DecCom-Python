import asyncio
from deccom.nodes import StreamNode, Node
from deccom.protocols.peerdiscovery.kademliadiscovery import KademliaDiscovery
from deccom.protocols.securityprotocols import Noise
from deccom.protocols.defaultprotocol import DefaultProtocol
from deccom.protocols.peerdiscovery import GossipDiscovery
from deccom.peers import Peer
from deccom.protocols.streamprotocol import StreamProtocol
from random import randint

n = Peer(("127.0.0.1", 10015))
def send(nd: StreamNode):
    print("TIME TO SEND")
    asyncio.create_task(nd.sendto(b'hi',("127.0.0.1", 10015)))
protocol = DefaultProtocol()
gossip = KademliaDiscovery(bootstrap_peers=[n])
gossip.set_lower(protocol)
approval  = Noise()
approval.set_lower(gossip)
stream = StreamProtocol(True, peer_connected_callback= print, disconnected_callback=print)
stream.set_lower(approval)
me = StreamNode(stream,"127.0.0.1")
self.peer = Peer((me.ip_addr,me.port), tcp=me.tcp_port)
loop = asyncio.new_event_loop()
print(self.peer.id_node)
if True:
    loop.call_later(5,
                                        send, me)
loop.run_until_complete(me.listen())

loop.run_forever()