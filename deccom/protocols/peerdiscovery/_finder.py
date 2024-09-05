from dataclasses import dataclass
from deccom.peers.peer import Peer
import heapq
@dataclass
class NodeaAbstraction:
    idx: bytes = None
    p: Peer = None
    idint: int = 0
    


class Finder(object):
    """
    Finder class for the Kademlia Protocol. Given a list of initial peer and an alpha parameter of number of peers to contact in parallel, find a given 
    peer.
    """

    def __init__(self, look_for: bytes, initial: list[Peer], alpha: int = 5) -> None:
        self.look_for = look_for
        self.look_for_int = int.from_bytes(look_for, byteorder="big")
        self.peers: list[tuple(int, NodeaAbstraction)]  = []
        self.contacted: set[bytes] = set()
        self.alpha = alpha
        for i in initial:
            pi = NodeaAbstraction(i.id_node,i,int.from_bytes(i.id_node, byteorder="big"))
            heapq.heappush(self.peers, (pi.idint ^ self.look_for_int, pi))
            self.contacted.add(pi.idx)
        

    """
    Gives the next list of peers that should be contacted during the search of the peer


    Returns
    ----------
    ret
        A list of peers (of maximum size alpha) which are currently the closest known to the searched for peer.

    """

    def find_peer(self):
        if len(self.peers) == 0:
            return []
        ret: list[Peer] = []
        for i in range(self.alpha):
            if len(self.peers) == 0:
                break
            ret.append(heapq.heappop(self.peers)[1].p)
        return ret
    

    """
    Adds the list of peers to the internal heap queue

    Parameters
    ----------
    peers 
        List of peers to add
    """

    def add_peer(self, peers: list[Peer]):
        for p in peers:
            prv = len(self.contacted)
            self.contacted.add(p.id_node)
            if prv < len(self.contacted):
                pi = NodeaAbstraction(p.id_node,p,int.from_bytes(p.id_node, byteorder="big"))
                heapq.heappush(self.peers, (pi.idint ^ self.look_for_int, pi))

    def stop(self):
        self.contacted.clear()
        self.peers.clear()
                    