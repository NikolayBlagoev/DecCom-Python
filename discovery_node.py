# this node is used as a template for 
# a default running bootstrap node


import asyncio
from deccom.protocols.peerdiscovery import KademliaDiscovery
from deccom.protocols.defaultprotocol import DefaultProtocol
from deccom.nodes import Node
from deccom.protocols.securityprotocols import Noise
from deccom.peers.peer import Peer


base_peer = Peer(None, "ava")


protocol = DefaultProtocol()
discovery = KademliaDiscovery([],interval=12, always_split = True)
discovery.set_lower(base_peer)
noise = Noise(strict=False)
noise.set_lower(discovery)
loop = asyncio.get_event_loop()
me = Node(base_peer , noise,port = 10015,call_back=lambda *args:...)
loop.run_until_complete(me.listen())
loop.run_forever()

        


        
        

