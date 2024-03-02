
from collections import OrderedDict
from deccom.peers.peer import Peer

class KBucket(object):
    def __init__(self, min_dist, max_dist, k, originator = False, success_call = lambda addr, p : ...):
        self.min_dist = min_dist
        self.max_dist = max_dist
        self.mid_point =  (self.max_dist + self.min_dist)//2
        self.peers: OrderedDict[bytes,Peer] = OrderedDict()
        self.k = k
        self.success_call = success_call
        self.originator = originator
        self.toadd: list[tuple[bytes,Peer]] = []
    def split_bucket(self):
        to_split = self.mid_point
        left = KBucket(self.min_dist, to_split, self.k, success_call = self.success_call)
        right = KBucket(to_split + 1, self.max_dist, self.k, success_call = self.success_call) # since rule is greater than or equal to, we need one extra step
        if self.originator:
            left.originator = True
        
        for dist, peer in self.peers.items():
            if dist <= to_split:
                left.add_peer(dist, peer)
            else:
                right.add_peer(dist, peer)
        
        for dist, peer in self.toadd:
            ret = -1
            if dist <= to_split:
                ret = left.add_peer(dist, peer)
            else:
                ret = right.add_peer(dist, peer)
            # if ret == 0:
                # self.success_call(dist, peer)
            
        self.toadd = []
        self.peers = dict()
        return (left,right)
        
        
    def update_peer(self, dist, node):
            if self.peers.get(dist) == None and len(self.peers) < self.k:
                self.peers[dist] = node
            elif self.peers.get(dist) != None:

                del self.peers[dist]
                self.peers[dist] = node
            elif len(self.peers) > self.k:
                if (dist,node) in self.toadd:
                    self.toadd.remove((dist,node))
                
                self.toadd.append((dist,node))
                self.toadd = self.toadd[-5:]
                    
    def remove_peer(self, dist):
            
            if self.peers.get(dist) == None:
                return
            del self.peers[dist]
            if len(self.toadd) > 0:
                
                dist,peer = self.toadd.pop()
                # self.success_call(dist, peer)
                self.peers[dist] = peer

    def get_peer(self, dist):
        
        return self.peers.get(dist)
    def add_peer(self, dist, node):
            if self.peers.get(dist) != None:
                del self.peers[dist]
                self.peers[dist] = node
                return 0
            if len(self.peers) >= self.k:
                if self.originator:
                    self.toadd.append((dist,node))
                    return 1
                    
                else:
                    if (dist,node) in self.toadd:
                        return 2
                    
                    self.toadd.append((dist,node))
                    self.toadd = self.toadd[-5:]
                    
                    return 2
            else:
                self.peers[dist] = node
                return 0
    def get_top(self) -> tuple[bytes,Peer]:
        return list(self.peers.items())[0]
        
        
        

class BucketManager(object):
    def __init__(self, id, k, success_call, max_l = 256) -> None:
        if isinstance(id, bytes):
            id = int.from_bytes(id, byteorder="big")
        self.id = id
        self.k = k
        self.success_call = success_call
        self.buckets = [KBucket(0, 2**max_l, k, originator=True, success_call=self.success_call)]
    def bytexor(self, b1,b2):
        if len(b1) != len(b2):
            raise Exception("WRONG IDS")
        return bytes(a ^ b for a, b in zip(b1, b2))
    def get_peer(self, id) -> Peer:
        if isinstance(id, bytes):
            id = int.from_bytes(id, byteorder="big")
        dist = self.id ^ id
        indx = self._get_index(dist)
        return self.buckets[indx].get_peer(dist)
    
    
    
    def update_peer(self, id, node) -> Peer:
        if isinstance(id, bytes):
            id = int.from_bytes(id, byteorder="big")
        dist = self.id ^ id
        indx = self._get_index(dist)
        return self.buckets[indx].update_peer(dist, node)
   
    
    def add_peer(self,id,node, lv=0):
        # print(lv)
        if isinstance(id, bytes):
            id = int.from_bytes(id, byteorder="big")
        dist = self.id ^ id
        indx = self._get_index(dist)
        
        ret = self.buckets[indx].add_peer(dist,node)
        if ret == 0:
            return None
        elif ret == 1:
            l,r = self.buckets[indx].split_bucket()
            self.buckets[indx] = l
            self.buckets.insert(indx+1,r)
            return self.add_peer(id,node,lv+1)
        elif ret == 2:
            return self.buckets[indx].get_top()
    def _get_index(self, dist)->int:
        indx = -1
        
        for i, bucket in enumerate(self.buckets):
            if dist <= bucket.max_dist:
                indx = i
                break
        # print("indx for", dist, "is",indx)
        return indx
    def remove_peer(self, id):
        if isinstance(id, bytes):
            id = int.from_bytes(id, byteorder="big")
        dist = self.id ^ id
        idx = self._get_index(dist)
        self.buckets[idx].remove_peer(dist)
    
    def get_closest(self, id, alpha = None) -> list[Peer]:
        if isinstance(id, bytes):
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

        
    
            

