
from collections import OrderedDict
from typing import Callable
from deccom.peers.peer import Peer

class KBucket(object):
    def __init__(self, min_dist, max_dist, k, originator = False):
        self.min_dist = min_dist
        self.max_dist = max_dist
        self.mid_point =  (self.max_dist + self.min_dist)//2
        self.peers: OrderedDict[bytes,Peer] = OrderedDict()
        self.k = k
        self.originator = originator
        self.toadd: list[tuple[bytes,Peer]] = []
    def split_bucket(self):
        to_split = self.mid_point
        left = KBucket(self.min_dist, to_split, self.k)
        right = KBucket(to_split + 1, self.max_dist, self.k) # since rule is greater than or equal to, we need one extra step
        if self.originator:
            left.originator = True
        
        for dist, peer in self.peers.items():
            if dist <= to_split:
                left.add_peer(dist, peer)
            else:
                right.add_peer(dist, peer)
        for dist, peer in self.toadd:
            if dist <= to_split:
                left.add_peer(dist, peer)
            else:
                right.add_peer(dist, peer)
        self.toadd = []
        self.peers = dict()
        return (left,right)
        
        
    def update_peer(self, dist, node):
            if self.peers.get(dist) == None:
                self.peers[dist] = node
                return
            del self.peers[dist]
            self.peers[dist] = node
    def remove_peer(self, dist):
            if self.peers.get(dist) == None:
                return
            del self.peers[dist]
            if len(self.toadd) < 0:
                dist,peer = self.toadd.pop()
                self.peers[dist] = peer

    def get_peer(self, dist):
        
        return self.peers.get(dist)
    def add_peer(self, dist, node):
            if self.peers.get(dist) != None:
                del self.peers[dist]
                self.peers[dist] = node
                return None
            if len(self.peers) == self.k:
                if self.originator:
                    self.peers[dist] = node
                    return self.split_bucket()
                else:
                    self.toadd.append((dist,node))
                    self.toadd = self.toadd[:5]
                    return list(self.peers.values())[0]

            else:
                self.peers[dist] = node
                return None
        
        
        

class BucketManager(object):
    def __init__(self, id, k) -> None:
        self.id = int.from_bytes(id, byteorder="big")
        self.k = k
        self.buckets = [KBucket(0, 2**256, k, originator=True)]
    def bytexor(self, b1,b2):
        if len(b1) != len(b2):
            raise Exception("WRONG IDS")
        return bytes(a ^ b for a, b in zip(b1, b2))
    def get_peer(self, id) -> Peer:
        id = int.from_bytes(id, byteorder="big")
        dist = self.id ^ id
        indx = self._get_index(dist)
        return self.buckets[indx].get_peer(dist)
    
    
    
    def update_peer(self, id, node) -> Peer:
        id = int.from_bytes(id, byteorder="big")
        dist = self.id ^ id
        indx = self._get_index(dist)
        return self.buckets[indx].update_peer(dist, node)
   
    
    def add_peer(self,id,node):
        id = int.from_bytes(id, byteorder="big")
        dist = self.id ^ id
        indx = self._get_index(dist)
        
        ret = self.buckets[indx].add_peer(dist,node)
        if isinstance(ret,tuple):
            self.buckets[indx] = ret[0]
            self.buckets.insert(indx+1,ret[1])
            return None
        return ret
    def _get_index(self, dist)->int:
        indx = -1
        for i, bucket in enumerate(self.buckets):
            if dist < bucket.max_dist:
                indx = i
                break
        return indx
    def remove_peer(self, id):
        id = int.from_bytes(id, byteorder="big")
        dist = self.id ^ id
        idx = self._get_index(dist)
        self.buckets[idx].remove_peer(dist)
    def get_closest(self, id, alpha = None) -> list[Peer]:
        id = int.from_bytes(id, byteorder="big")
        if alpha == None:
            alpha = self.k
        dist = self.id ^ id
        idx = self._get_index(dist)
        lst: list[Peer] = []
        lst += list(self.buckets[idx].peers.values())
        diff = 1
        idx += diff
        stopper = max(idx, len(self.buckets)-idx)
        while len(lst) < alpha:
            if idx >= 0 and idx < len(self.buckets):
                lst += list(self.buckets[idx].peers.values())
            if diff < 0:
                diff *= -1
                diff += 1
            else:
                diff *= -1
            if abs(diff) > stopper:
                break
        lst = lst[:alpha]    
        return lst

        
    
            

