import asyncio
from typing import Callable
from deccom.protocols.abstractprotocol import AbstractProtocol
from deccom.protocols.defaultprotocol import DefaultProtocol
from deccom.peers import Peer
from random import randint, sample


class GossipProtocol(AbstractProtocol):
    INTRODUCTION = int.from_bytes(b'\xe1', byteorder="big")
    PUSH = int.from_bytes(b'\xc4', byteorder="big")
    PULL = int.from_bytes(b'\xe5', byteorder="big")
    PULLED = int.from_bytes(b'\xc3', byteorder="big")
    FIND = int.from_bytes(b'\xf6', byteorder="big")
    offers = dict(AbstractProtocol.offers, **{
        "find_peer": "find_peer",
        "disconnect_callback": "set_disconnect_callback",
        "get_peer": "get_peer",
        "connected_callback": "set_connected_callback",
        "send_ping": "send_ping"
    })
    bindings = dict(AbstractProtocol.bindings, **{
                    "remove_peer": "set_disconnect_callback",
                    "add_peer": "set_connected_callback",
                    "_lower_ping": "send_ping"
                    })
    required_lower = AbstractProtocol.required_lower + ["send_ping"]

    def __init__(self, bootstrap_peers: list[Peer], interval: int = 10, submodule: DefaultProtocol | AbstractProtocol = None,
                 callback: Callable[[tuple[str, int], bytes], None] = lambda addr, data: ..., disconnect_callback=lambda addr, nodeid: ...,
                 peer_connected_callback=lambda nodeid: ...):
        super().__init__(submodule, callback)

        self.peers: dict[bytes, Peer] = dict()
        self.interval = interval
        for peer in bootstrap_peers:
            self.peers[peer.id_node] = peer
        self.disconnect_callback = disconnect_callback
        self.peer_crawls = dict()
        self.sent_finds = dict()
        self._lower_ping = lambda addr, success, failure, timeout: ...
        self.peer_connected_callback = peer_connected_callback

    async def start(self):
        await super().start()
        for k, p in self.peers.items():
            await self.introduce_to_peer(p)
        self.push_or_pull()

    def add_peer(self, p: Peer):
        return

    def set_connected_callback(self, callback):
        self.peer_connected_callback = callback

    def set_disconnect_callback(self, callback):
        self.disconnect_callback = callback

    def push_or_pull(self):
        loop = asyncio.get_event_loop()
        loop.create_task(self._push_or_pull())

    def remove_peer(self, addr, node_id):
        del self.peers[node_id]
        self.disconnect_callback(addr, node_id)

    async def _push_or_pull(self):
        # print("push or pull")
        rand = randint(0, 1)
        # print(rand)
        ids = list(self.peers.keys())
        if len(ids) >= 1:
            strt = randint(0, len(ids)-1)
            for i in range(strt, strt+5):
                if i >= len(ids):
                    break
                await self._lower_ping(self.peers[ids[i]].addr, print, lambda addr, node_id=ids[i], self=self: self.remove_peer(addr, node_id), 10)

        if rand == 0 and len(ids) >= 2:

            p1 = ids[randint(0, len(ids)-1)]
            p2 = p1

            while p1 == p2:
                p2 = ids[randint(0, len(ids)-1)]
            msg = bytearray([GossipProtocol.PUSH])
            msg = msg + bytes(self.peers[p2])
            await self._lower_sendto(msg, self.peers[p1].addr)

            msg = bytearray([GossipProtocol.PUSH])
            msg = msg + bytes(self.peers[p1])
            await self._lower_sendto(msg, self.peers[p2].addr)
        elif len(ids) >= 1:

            p1 = ids[randint(0, len(ids)-1)]
            msg = bytearray([GossipProtocol.PULL])
            msg = msg + bytes(Peer.me)
            await self._lower_sendto(msg, self.peers[p1].addr)
        loop = asyncio.get_running_loop()
        self.refresh_loop = loop.call_later(self.interval, self.push_or_pull)

    async def introduce_to_peer(self, peer: Peer):
        msg = bytearray([GossipProtocol.INTRODUCTION])
        msg = msg + bytes(Peer.get_current())
        await self._lower_sendto(msg, peer.addr)

    async def sendto(self, msg, addr):
        tmp = bytearray([b'\x01'])
        tmp = tmp + msg
        return await self._lower_sendto(tmp, addr)

    def process_datagram(self, addr: tuple[str, int], data: bytes):
        if data[0] == GossipProtocol.INTRODUCTION:

            other, i = Peer.from_bytes(data[1:])
            # print("introduction form", other.pub_key)
            other.addr = addr
            if self.peer_crawls.get(other.id_node) != None:
                self.peer_crawls[other.id_node].set_result("success")
                del self.peer_crawls[other.id_node]
            if self.peers.get(other.id_node) != None:

                self.peers[other.id_node].addr = addr
            else:

                self.peers[other.id_node] = other
                self.peer_connected(other.id_node)

        elif data[0] == GossipProtocol.PULL:
            # print("request to pull")
            flag = False
            other, i = Peer.from_bytes(data[1:])
            if self.peer_crawls.get(other.id_node) != None:
                self.peer_crawls[other.id_node].set_result("success")
                del self.peer_crawls[other.id_node]
            if self.peers.get(other.id_node) == None:

                self.peers[other.id_node] = other
                flag = True
            else:
                self.peers[other.id_node].addr = other.addr
                self.peers[other.id_node].tcp = other.tcp
            ids = list(self.peers.keys())
            if len(ids) > 1:
                rand_node = randint(0, len(ids)-1)
                while ids[rand_node] == other.id_node:
                    rand_node = randint(0, len(ids)-1)
                msg = bytearray([GossipProtocol.PULLED])
                msg = msg + bytes(self.peers[ids[rand_node]])
                loop = asyncio.get_running_loop()
                loop.create_task(self._lower_sendto(msg, addr))
            if flag:
                self.peer_connected(other.id_node)
        elif data[0] == GossipProtocol.PULLED:
            # print("pulled")
            other, i = Peer.from_bytes(data[1:])
            if self.peer_crawls.get(other.id_node) != None:
                self.peer_crawls[other.id_node].set_result("success")
                del self.peer_crawls[other.id_node]
            self.peers[other.id_node] = other
            self.peer_connected(other.id_node)
            loop = asyncio.get_running_loop()
            loop.create_task(self.introduce_to_peer(other))

        elif data[0] == GossipProtocol.PUSH:
            # print("request to push")
            other, i = Peer.from_bytes(data[1:])
            if self.peer_crawls.get(other.id_node) != None:
                self.peer_crawls[other.id_node].set_result("success")
                del self.peer_crawls[other.id_node]
            self.peers[other.id_node] = other
        elif data[0] == GossipProtocol.FIND:
            # print("peer looking")
            if self.sent_finds.get(data) != None:
                return

            seeker, i = Peer.from_bytes(data[1:])

            id = data[i+1:]
            # print(seeker.id_node," is looking for ",id)
            self.sent_finds[data] = i
            if id == Peer.me.id_node:
                # print("THATS ME")
                loop = asyncio.get_running_loop()
                loop.create_task(self.introduce_to_peer(seeker))

                self.peers[seeker.id_node] = seeker
                self.peer_connected(seeker.id_node)
            elif self.peers.get(id) == None:
                l = list(self.get_peers())
                for p in l:
                    if self.get_peers().get(p) is None:
                        continue
                    loop = asyncio.get_running_loop()
                    loop.create_task(self._lower_sendto(
                        data, self.peers[p].addr))

            else:
                peer = self.peers.get(id)
                loop = asyncio.get_running_loop()
                loop.create_task(self._lower_sendto(data, peer.addr))

        else:
            self.callback(addr, data[1:])
        return

    def get_peer(self, id) -> Peer:

        return self.peers.get(id)

    async def send_ping(self, addr, success, fail, timeout):
        await self._lower_ping(addr, success, fail, timeout)

    def get_peers(self) -> dict[bytes, Peer]:
        return self.peers

    async def _find_peer(self, fut, id):
        self.peer_crawls[id] = fut
        msg = bytearray([GossipProtocol.FIND])
        if isinstance(id, str):
            id = id.encode("utf-8")
        msg = msg + bytes(Peer.me) + id
        l = list(self.get_peers())
        for p in l:
            if self.get_peers().get(p) is None:
                continue
            await self._lower_sendto(msg, self.peers[p].addr)

        return

    async def find_peer(self, id) -> Peer:
        if self.peers.get(id) == None:
            if self.peer_crawls.get(id) == None:
                loop = asyncio.get_running_loop()
                fut = loop.create_future()
                await self._find_peer(fut, id)
                await fut
            else:
                await self.peer_crawls.get(id)
        return self.get_peer(id)
