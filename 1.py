import asyncio
from deccom.nodes import StreamNode, Node
from deccom.protocols.defaultprotocol import DefaultProtocol
from deccom.protocols.gossipprotocol import GossipProtocol
from deccom.peers import Peer
from deccom.protocols.streamprotocol import StreamProtocol
n = Peer(("127.0.0.1", 10015), pub_key="1")
Peer.me = n

def send(nd: StreamNode):
    print(list(me.protocol_type.get_peers().values()))
    asyncio.ensure_future(nd.stream_data(list(me.protocol_type.get_peers().values())[0].id_node, b'\xe3\x32'))
protocol = DefaultProtocol()
gossip = GossipProtocol([])
gossip.set_lower(protocol)
stream = StreamProtocol(True)
stream.set_lower(gossip)


me = StreamNode(stream,"127.0.0.1", 10015)
Peer.me.tcp = me.tcp_port
print(Peer.me.id_node)
loop = asyncio.new_event_loop()
loop.call_later(5,
                                     send, me)
loop.run_until_complete(me.listen())

loop.run_forever()