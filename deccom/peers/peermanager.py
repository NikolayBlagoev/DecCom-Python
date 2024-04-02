'''
This class may hopefully one day come in handy. Instead of one protocol managing
the peers (currently the discovery protocols), they manage a part of them (addition and removal).
Together all protocols interact with the peer manager to modify peer information
'''
from collections import OrderedDict
from .peer import Peer
class PeerManager(object):
    def __init__(self, me: Peer, peer_limit = 200) -> None:
        self.me = me
        self.peers = OrderedDict()
    def __call__(self) -> Peer:
        return self.me

    