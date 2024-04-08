import asyncio
from deccom.nodes.node import Node
from deccom.peers.peer import Peer
from deccom.protocols.faultytransport import FaultyProtocol
from deccom.protocols.peerdiscovery import *
from deccom.protocols.defaultprotocol import DefaultProtocol
from deccom.protocols.reliableudp import ReliableUDP
from datetime import datetime
protocol = FaultyProtocol(failure_p=0.05)
gossip = KademliaDiscovery([],interval=10)
gossip.set_lower(protocol)
rudp = ReliableUDP()
rudp.set_lower(gossip)
peer = Peer(None, pub_key="0")
me = Node(peer,rudp, port = 10015,call_back=lambda addr,data: print(datetime.now(),"received", len(data)))

loop = asyncio.new_event_loop()

loop.run_until_complete(me.listen())
loop.run_forever()