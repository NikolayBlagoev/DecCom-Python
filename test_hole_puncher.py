


import asyncio
from sys import argv
from deccom.peers.peer import Peer
from deccom.protocols.defaultprotocol import DefaultProtocol
from deccom.protocols.holepuncher import HolePuncher
from deccom.protocols.peerdiscovery import KademliaDiscovery
from deccom.protocols.streamprotocol import StreamProtocol
from deccom.protocols.tcpholepuncher import TCPHolePuncher
from deccom.nodes.streamnode import StreamNode
def send_data():
    loop = asyncio.get_running_loop()
    loop.create_task(me.stream_data("0",bytearray([0,0,0,0,0,0])))
protocol = DefaultProtocol()
pnchr = HolePuncher()
pnchr.set_lower(protocol)
gossip = KademliaDiscovery([],interval=5)

gossip.set_lower(pnchr)

stream = StreamProtocol(False)
stream.set_lower(gossip)
tcppnchr = TCPHolePuncher()
tcppnchr.set_lower(stream)
if argv[1] != "0":
    gossip.bootstrap_peers.append(Peer(("127.0.0.1",10080)))
    tcppnchr.known_peers.append(Peer(("127.0.0.1",10080)))
peer = Peer(None, pub_key=argv[1])
me = StreamNode(peer, tcppnchr,"0.0.0.0", port = 10080 if argv[1] == "0"  else None, tcp_port=10082 if argv[1] == "0"  else None)
loop = asyncio.new_event_loop()
loop.run_until_complete(me.listen())
if argv[1] != "0":
    loop.call_later(5, send_data)

loop.run_forever()





