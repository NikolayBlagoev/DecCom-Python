import asyncio
from arpegio import Arpegio
from deccom.nodes.node import Node
from deccom.peers.peer import Peer
from deccom.protocols.peerdiscovery import KademliaDiscovery
from deccom.protocols.defaultprotocol import DefaultProtocol
from sys import argv
me = int(argv[1])

def costmap(a1,a2):
    return abs(int(a1)-int(a2))

protocol = DefaultProtocol()
gossip = KademliaDiscovery([])
if me != 0:
    gossip.bootstrap_peers.append(Peer(("127.0.0.1", 10015),"0"))
gossip.set_lower(protocol)
stream = Arpegio(costmap,(me+2) % 3)
stream.set_lower(gossip)
me = Node( Peer(None, pub_key=argv[1]), stream,"127.0.0.1", 10015 if argv[1] == "0" else None)

loop = asyncio.new_event_loop()
print("run...")

loop.run_until_complete(me.listen())
loop.run_forever()