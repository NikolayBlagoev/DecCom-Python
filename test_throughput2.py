import asyncio
from time import sleep
from deccom.nodes.node import Node
from deccom.peers.peer import Peer
from deccom.protocols.faultytransport import FaultyProtocol
import torch
import pickle
from deccom.protocols.peerdiscovery import *
from deccom.protocols.defaultprotocol import DefaultProtocol
from deccom.protocols.reliableudp import ReliableUDP
from datetime import datetime
# t = datetime.now()
# sleep(2)
# print(datetime.now()-t)
protocol = FaultyProtocol(failure_p=0.00)
n = Peer(("127.0.0.1", 10015))
gossip = KademliaDiscovery([n],interval=10)
gossip.set_lower(protocol)
rudp = ReliableUDP()
rudp.set_lower(gossip)
peer = Peer(None, pub_key="1")
me = Node(peer,rudp, port = 10016)
loop = asyncio.new_event_loop()
def sendto():
    data = bytes(pickle.dumps(torch.zeros([1000, 1000])))
    # data = b'hellotherecutie'
    print(datetime.now(),"sending")
    loop.create_task(me.sendto(data, ("127.0.0.1", 10015)))
loop.run_until_complete(me.listen())
loop.call_later(4, sendto)
loop.run_forever()