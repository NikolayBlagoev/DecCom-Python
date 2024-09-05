# DecCom-Python
[DecCom](https://theworkerthread.com/tool/deccom) - Decentralised communication with Python made easy. 

DecCom provides an easy interface to stack modular protocols on top of each other to create the application you need. The package comes with several protocols you can already use in your development. 

THE PROJECT IS STILL A WORK IN PROGRESS!! ALL BINDINGS ARE SUBJECT TO CHANGE! USE AT YOUR OWN RISK!

## Why DecCom?

Many popular frameworks for distributed applications are often overly complex, poorly maintained, or straight up not working. [IPv8](https://github.com/Tribler/py-ipv8) has an incredibly rigid structure and poor throughput. [LibP2P](https://libp2p.io/) has a tidiously slow developmental cycle and for many languages the repositories are no longer maintained. It is incredibly difficult to build your desired application on any of these.

This is where DecCom comes in. With just a few lines of code you too can build a complex distributed application ready for a production environment. The modular nature of the protocols means that you can modify and add functionality without needing to rewrite your entire codebase. DecCom comes prepackaged with several common protocols which take care of the boring stuff for you - processing large messages, reliable communication, peer discovery, security, etc.

**But why "DecCom"?** - DecCom is short for Decentralised Communication. There isn't much more to it.


## DecCom's philosophy

Many protocol architectures have a very rigid structure - one layer binds to all ports of a lower layer and provides some ports to the layer above it. DecCom violates this strucutre by allowing for any layer to connect to any set of bindings of layers under it. This may sometimes result in very ugly looking diagrams such as the one below.

![DecCom protocol stack](imgs/protocolstack.png "Example Protocol Stack in DecCom")

DecCom works with two types of bindings (see [wrappers.py](deccom/protocols/wrappers.py))- bindto and bindfrom. Bindto refers to methods a protocol calls from a lower protocol. For example, in the TCP/IP protocol stack, an application would call a "send" method to send to some other IP their message. Bindfrom are methods a lower protocol can call in an upper protocol. In the TCP/IP analogy an application would have a receive method which the lower layer would call when the entire message has been received. Thus bindto goes down, bindfrom goes up the stack. Typically your application should stand at the top.

## Identity

Within DecCom each node has an [identifier](deccom/peers/peer.py) and a public identity. The identifier is a SHA256 has of their public identity. Their public identity can be a public key (currently we support eliptic curve algorithms on the Ed25519 curve) or strings of arbitrary length. Public key identities are used in security layers for encrypting or signing messages. String identities are useful if you want to test an application with a small set of known nodes with specific ids.

## Discovery

Discovery can be performed with any of the available methods (currently a [Kademlia DHT](deccom/protocols/peerdiscovery/kademliadiscovery.py) or a [Gossip](deccom/protocols/peerdiscovery/biggossip.py) protocol). It is important to note that depending on the nodes you choose to connect to initially you can have many different peer networks built on DecCom, which do not communicate with each other. Unlike applications built on top of IPFS which use the IPFS network at all times, with DecCom you can create your own private group without ever contacting any of the publicly available ones.

## Protocols

DecCom currently has the following protocols implemented:

1. UDP transport [defaultprotocol.py](deccom/protocols/defaultprotocol.py)
2. TCP transport [streamprotocol.py](deccom/protocols/streamprotocol.py)
3. UDP hole punching [holepuncher.py](deccom/protocols/holepuncher.py)
4. TCP hole punching [tcpholepuncher.py](deccom/protocols/tcpholepuncher.py)
5. Reliable UDP [reliableudp.py](deccom/protocols/reliableudp.py)
6. Noise protocol [noiseprotocol.py](deccom/protocols/securityprotocols/noiseprotocol.py) - establishes a common secret between two nodes
7. Kademlia DHT [kademliadiscovery.py](deccom/protocols/peerdiscovery/kademliadiscovery.py) - for discovery
8. Gossip [gossipdiscovery.py](deccom/protocols/peerdiscovery/gossipdiscovery.py) - for discovery
9. BigGossip [biggossip.py](deccom/protocols/peerdiscovery/biggossip.py) - for discovery
10. Delay protocol [delayprotocol.py](deccom/protocols/delayprotocol.py) - for testing purposes as one might want to add artificial delay between nodes
11. Keep Alive protocol [keepalive.py](deccom/protocols/keepalive.py)
12. Faulty UDP transport [faultytransport.py](deccom/protocols/faultytransport.py) - for simulating random message drops (useful for testing your programs)