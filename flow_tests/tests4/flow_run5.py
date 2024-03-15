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
            "9": 10,
            "5": 10,
            "6": 10
        },
        "1": {
            "0": 1,
            "2": 10,
            "3": 1,
            "9": 3,
            "5": 10,
            "6": 10
        },
        "2": {
            "1": 10,
            "0": 1,
            "3": 2,
            "9": 1,
            "5": 10,
            "6": 10
        },
        "3": {
            "1": 1,
            "2": 2,
            "0": 10,
            "9": 10,
            "5": 10,
            "6": 1
        },
        "9": {
            "1": 3,
            "2": 1,
            "3": 10,
            "0": 10,
            "5": 10,
            "6": 1
        },
        "6": {
            "1": 10,
            "2": 10,
            "3": 1,
            "9": 1,
            "5": 10,
            "0": 10
        },
    }
    return matrix[a1][a2]

peers = [Peer(("127.0.0.1", 10026), "6"), Peer(("127.0.0.1", 10021), "1"), Peer(("127.0.0.1", 10022), "2"), Peer(("127.0.0.1", 10024), "9")]
peer = Peer(("127.0.0.1", 10023), "3")
lowest = DefaultProtocol()
prs = FixedPeers(peers)
prs.set_lower(lowest)
fp = FlowProtocol(2, 3, 2, 0, 0, 0, costmap)
fp.set_lower(prs)
me = Node(peer,fp,"127.0.0.1",10023, print)
loop = asyncio.new_event_loop()
loop.run_until_complete(me.listen())
loop.run_forever()