from dataclasses import dataclass
from deccom.peers.peer import Peer
import heapq
@dataclass
class NodeaAbstraction:
    idx: bytes = None
    p: Peer = None
    idint: int = 0
    


class Finder(object):
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
        
        pass

    def find_peer(self):
        if len(self.peers) == 0:
            return []
        ret: list[Peer] = []
        for i in range(self.alpha):
            if len(self.peers) == 0:
                break
            ret.append(heapq.heappop(self.peers)[1].p)
        return ret
    
    def add_peer(self, peers: list[Peer]):
        for p in peers:
            prv = len(self.contacted)
            self.contacted.add(p.id_node)
            if prv < len(self.contacted):
                pi = NodeaAbstraction(p.id_node,p,int.from_bytes(p.id_node, byteorder="big"))
                heapq.heappush(self.peers, (pi.idint ^ self.look_for_int, pi))

                