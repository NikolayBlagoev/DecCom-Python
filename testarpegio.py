import asyncio
import random
from sys import argv
import time
import unittest
from arpegio2 import Arpegio
from deccom.nodes.node import Node
from deccom.peers.peer import byte_reader
from deccom.peers.peer import Peer
from deccom.protocols.defaultprotocol import DefaultProtocol
from deccom.protocols.peerdiscovery.kademliadiscovery import KademliaDiscovery
from stubs.network_stub import NetworkStub
from stubs.node_stub import NodeStub
import os

# Fork a child process

delay_bandwidth_dict = {
    "Oregon-Virginia": (67, 0.79),
    "Oregon-Ohio": (49, 1.10),
    "Oregon-Tokyo": (96, 0.523),
    "Oregon-Seoul": (124, 0.46),
    "Oregon-Singapore": (163, 0.341),
    "Oregon-Sydney": (139, 0.36),
    "Oregon-London": (136, 0.42),
    "Oregon-Frankfurt": (143, 0.404),
    "Oregon-Ireland": (124, 0.482),
    "Virginia-Ohio": (11, 1.12),
    "Virginia-Tokyo": (143, 0.524),
    "Virginia-Seoul": (172, 0.500),
    "Virginia-Singapore": (230, 0.364),
    "Virginia-Sydney": (197, 0.383),
    "Virginia-London": (76, 1.16),
    "Virginia-Frankfurt": (90, 1.02),
    "Virginia-Ireland": (67, 1.05),
    "Ohio-Tokyo": (130, 0.694),
    "Ohio-Seoul": (159, 0.529),
    "Ohio-Singapore": (197, 0.452),
    "Ohio-Sydney": (185, 0.484),
    "Ohio-London": (86, 1.05),
    "Ohio-Frankfurt": (99, 0.799),
    "Ohio-Ireland": (77, 1.14),
    "Tokyo-Seoul": (34, 1.10),
    "Tokyo-Singapore": (73, 1.01),
    "Tokyo-Sydney": (100, 0.761),
    "Tokyo-London": (210, 0.366),
    "Tokyo-Frankfurt": (223, 0.36),
    "Tokyo-Ireland": (199, 0.465),
    "Seoul-Singapore": (74, 1.14),
    "Seoul-Sydney": (148, 0.58),
    "Seoul-London": (238, 0.342),
    "Seoul-Frankfurt": (235, 0.358),
    "Seoul-Ireland": (228, 0.335),
    "Singapore-Sydney": (92, 0.816),
    "Singapore-London": (169, 0.500),
    "Singapore-Frankfurt": (155, 0.535),
    "Singapore-Ireland": (179, 0.492),
    "Sydney-London": (262, 0.326),
    "Sydney-Frankfurt": (265, 0.328),
    "Sydney-Ireland": (254, 0.344),
    "London-Frankfurt": (14, 1.14),
    "London-Ireland": (12, 1.09),
    "Frankfurt-Ireland": (24, 1.08)
}
batch_size = 1e6 / 2048
layer_size = 24


peer_delay = None
peer_bandwidth = None
regions = None

# assigned task
batch_size_per_task = 1.25e5 / 2048
layer_size_per_task = 3
send_gradient_size = 1.3 * \
    4 * \
    layer_size_per_task / layer_size  # gigabytes

batch_size = 1e6 / 2048
partition_size = int(batch_size / batch_size_per_task)
locs = ["Virginia", "Oregon", "Sydney", "London", "Frankfurt", "Ireland", "Tokyo", "Ohio", "Seoul"]
def costmap(pk1, pk2):
    loc1 = locs[int(pk1) % 8]
    loc2 = locs[int(pk2) % 8]
    ret = delay_bandwidth_dict.get(loc1+"-"+loc2)
    if ret == None:
        ret = delay_bandwidth_dict.get(loc2+"-"+loc1)

    if ret == None:
        if loc1 == loc2:
            ret = (10, 1.02)
            # print(3*(ret[0] / 1e3 + send_gradient_size * 8 / (ret[1] * partition_size)))
        # print(loc1,loc2)
    return (ret[0] / 1e3 + send_gradient_size * 8 / (ret[1] * partition_size))/100
ret = (10, 1.02)
print(7 * (ret[0] / 1e3 + send_gradient_size * 8 / (ret[1] * partition_size)))
me = int(argv[1])
import numpy as np
np.random.seed(239)
stgs = np.random.permutation([i % 8 for i in range(32)])

protocol = DefaultProtocol()
gossip = KademliaDiscovery([])
if me != 0:
    gossip.bootstrap_peers.append(Peer(("127.0.0.1", 10015),"0"))

gossip.set_lower(protocol)

stream = Arpegio(costmap, stgs[me].item())
stream.set_lower(gossip)
me = Node( Peer(None, pub_key=argv[1]), stream,"127.0.0.1", 10015 if argv[1] == "0" else None)

loop = asyncio.new_event_loop()
print("run...")

loop.run_until_complete(me.listen())
loop.run_forever()