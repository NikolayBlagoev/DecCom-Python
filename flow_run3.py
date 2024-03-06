import asyncio
from deccom.peers.peer import Peer
from deccom.protocols.peerdiscovery import FixedPeers
from deccom.protocols.defaultprotocol import DefaultProtocol
from flowprotocol import FlowProtocol
from deccom.nodes import Node



def costmap(a1, a2):
    matrix = {
        "0": {
            "1": 1,
            "2": 1,
            "3": 10,
            "4": 10,
            "5": 10,
            "6": 10
        },
        "1": {
            "0": 1,
            "2": 10,
            "3": 1,
            "4": 3,
            "5": 10,
            "6": 10
        },
        "2": {
            "1": 10,
            "0": 1,
            "3": 2,
            "4": 1000,
            "5": 10,
            "6": 10
        },
        "3": {
            "1": 1,
            "2": 2,
            "0": 10,
            "4": 10,
            "5": 10,
            "6": 1
        },
        "4": {
            "1": 3,
            "2": 1000,
            "3": 10,
            "0": 10,
            "5": 10,
            "6": 1
        },
        "6": {
            "1": 10,
            "2": 10,
            "3": 1,
            "4": 1,
            "5": 10,
            "0": 10
        },
    }
    return matrix[a1][a2]


peers = [Peer(("127.0.0.1", 10020), "0"), Peer(("127.0.0.1", 10023), "3"), Peer(("127.0.0.1", 10024), "4"), Peer(("127.0.0.1", 10021), "1")]
Peer.me = Peer(("127.0.0.1", 10022), "2")
lowest = DefaultProtocol()
prs = FixedPeers(peers)
prs.set_lower(lowest)
fp = FlowProtocol(1, 3, 1, 0, 0, 0, costmap)
fp.set_lower(prs)
me = Node(fp,"127.0.0.1",10022, print)
loop = asyncio.new_event_loop()
loop.run_until_complete(me.listen())
loop.run_forever()