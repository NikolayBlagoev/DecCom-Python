import asyncio
import sys
from deccom.peers.peer import Peer
from deccom.protocols.peerdiscovery import FixedPeers, KademliaDiscovery, BigGossip
from deccom.protocols.defaultprotocol import DefaultProtocol
from deccom.protocols.securityprotocols import Noise
from flowprotocol import FlowProtocol
from deccom.nodes import Node
import json

from flowprotocol_ss import FlowProtocolSS
with open("config.json", "r") as js:
    data = json.load(js)

pr = sys.argv[1]
pr_int = int(pr)
def costmap(a1, a2):
    a1 = int(a1)
    a2 = int(a2)
    if a2 == data['N'] or a1 == data['N']:
        return 1
    return data['costmap'][a1][a2]

peer = Peer(None, pr)
lowest = DefaultProtocol()
prs = BigGossip(interval=5, k = 30)
if pr_int != 0:
    prs.bootstrap_peers.append(Peer(("127.0.0.1", 10020), "0"))
prs.set_lower(lowest)

noise = Noise(strict=False)
noise.set_lower(prs)
print(noise._lower_sendto)
if pr != "0" and pr != "1" and pr_int != data['N']:
    stg = 0
    for i,a in enumerate(data['assignment']):
        if pr_int in a:
            stg = i
            break
    fp = FlowProtocol(i, data['S'] + 1, data['workload'][pr_int], 0, 0, 0, costmap)
elif pr == "0" or pr == "1":

    fp = FlowProtocolSS(0, data['S'] + 1, data['workload'][pr_int], 0, 0, data['workload'][pr_int], costmap)

fp.set_lower(noise)
print(prs.connected_callback)
me = Node(peer, fp,"127.0.0.1",10020 if pr == "0" else None, print)
loop = asyncio.new_event_loop()
loop.run_until_complete(me.listen())
loop.run_forever()