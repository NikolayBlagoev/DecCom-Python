import asyncio
from deccom.nodes import StreamNode, Node
from deccom.protocols.defaultprotocol import DefaultProtocol
from deccom.protocols.gossipprotocol import GossipProtocol
from deccom.peers import Peer
from deccom.protocols.streamprotocol import StreamProtocol
from random import randint

n = Peer(("127.0.0.1", 10015), pub_key="1")
def send(nd: StreamNode):
    asyncio.ensure_future(nd.find_node("3"))
protocol = DefaultProtocol()
gossip = GossipProtocol([n])
gossip.set_lower(protocol)
stream = StreamProtocol(True)
stream.set_lower(gossip)
me = StreamNode(stream,"127.0.0.1")
Peer.me = Peer((me.ip_addr,me.port), tcp=me.tcp_port, pub_key="2")
loop = asyncio.new_event_loop()
print(Peer.me.id_node)
# if Peer.me.pub_key == "2":
#     loop.call_later(5,
#                                         send, me)
loop.run_until_complete(me.listen())

loop.run_forever()