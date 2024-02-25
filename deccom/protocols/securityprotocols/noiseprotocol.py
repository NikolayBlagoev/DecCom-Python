import asyncio
from typing import Any, Callable, List
from deccom.cryptofuncs.hash import SHA256
from deccom.peers.peer import Peer
from deccom.protocols.abstractprotocol import AbstractProtocol
from ecdsa import VerifyingKey
from ecdsa.ecdh import ECDH
from os import urandom
from deccom.cryptofuncs.signatures import *
from ecdsa import SigningKey, NIST256p, VerifyingKey
class DictItem:
    def __init__(self,reader: asyncio.StreamReader,writer: asyncio.StreamWriter,fut: asyncio.Future, opened_by_me: int) -> None:
        self.reader = reader
        self.writer = writer
        self.fut = fut
        self.opened_by_me = opened_by_me
        pass
    
    
    

class Noise(AbstractProtocol):
    # zukertort opening transposing to Sicilian Defense
    CHALLENGE = int.from_bytes(b'\xf3', byteorder="big")
    RESPOND_CHALLENGE = int.from_bytes(b'\xc5', byteorder="big")
    FINISH_CHALLENGE = int.from_bytes(b'\xe4', byteorder="big")
    FALLTHROUGH = int.from_bytes(b'\x01', byteorder="big")
    bindings = dict(AbstractProtocol.bindings, **{
                    
                    "approve_peer": "set_approve_connection"
                    
                })
    required_lower = AbstractProtocol.required_lower + ["set_approve_connection"]
    def __init__(self,strict = True, encryption_mode = "plaintext", submodule=None, callback: Callable[[tuple[str, int], bytes], None] = lambda addr, data: print(addr, data)):
        super().__init__(submodule, callback)
        if encryption_mode.lower() not in ["plaintext", "aes"]:
            raise Exception(f"Encryption mode not recognised: ${encryption_mode}, should be one of plaintext or aes")
        self.encryption_mode = encryption_mode.lower()
        self.strict = strict
        self.awaiting_approval: dict[tuple[tuple[str,int],bytes], tuple[int, Peer, tuple[str,int], Callable, Callable]] = dict()
        self.approved_connections: dict[tuple[tuple[str,int],bytes], Peer] = dict()
    def process_datagram(self, addr: tuple[str, int], data: bytes):
        if data[0] == Noise.CHALLENGE:
            print("CHALLENGE FROM")
            other, i = Peer.from_bytes(data[1:])
            i+=1
            if addr[0] != other.addr[0] or addr[1] != other.addr[1]:
                print("wrong addy")
                return
            tmp = ECDH(curve=NIST256p)
            tmp.load_private_key(Peer.get_current().key)
            tmp.load_received_public_key_der(other.pub_key)
            shared = tmp.generate_sharedsecret()
            if not verify(other.pub_key,SHA256(shared),data[i:]):
                print("BAD VERIFICATION")
                return
            msg = bytearray([Noise.RESPOND_CHALLENGE])
            msg += bytes(Peer.get_current())
            msg += sign(Peer.get_current().key, SHA256(shared))
            loop = asyncio.get_running_loop()
            loop.create_task(self._lower_sendto(msg,addr))
            if self.awaiting_approval.get((addr,other.id_node)) != None:
                success = self.awaiting_approval[(addr,other.id_node)][3]
                peer = self.awaiting_approval[(addr,other.id_node)][1]
                addie = self.awaiting_approval[(addr,other.id_node)][2]
                success(addie,peer)
                del self.awaiting_approval[(addr,other.id_node)]
                self.approved_connections[(addr,other.id_node)] = peer
                return success(addie,peer)
            if self.approved_connections.get((addr,other.id_node)) == None:
                self.approved_connections[(addr,other.id_node)] = other
            
        elif data[0] == Noise.RESPOND_CHALLENGE:
            print("RESPONSE")
            other, i = Peer.from_bytes(data[1:])
            i+=1
            if self.awaiting_approval.get((addr,other.id_node)) == None or self.approved_connections.get((addr,other.id_node)) != None:
                print("IGNORING RESPONSE", self.awaiting_approval.get((addr,other.id_node)))
                return
            
            success = self.awaiting_approval[(addr,other.id_node)][3]
            shared = self.awaiting_approval[(addr,other.id_node)][0]
            if not verify(other.pub_key,SHA256(shared),data[i:]):
                print("BAD VERIFICATION")
                return
            del self.awaiting_approval[(addr,other.id_node)]
            self.approved_connections[(addr,other.id_node)] = other
            success(addr,other)
        elif data[0] == Noise.FALLTHROUGH:
            if self.encryption_mode == "plaintext":
                self.callback(data[1:])
    def send_challenge(self, addr, peer: Peer, success, failure):
        print("SENDING CHALLLENGE")
        loop = asyncio.get_running_loop()
        msg = bytearray([Noise.CHALLENGE])
        msg += bytes(Peer.get_current())
        tmp = ECDH(curve=NIST256p)
        tmp.load_private_key(Peer.get_current().key)
        tmp.load_received_public_key_der(peer.pub_key)
        shared = tmp.generate_sharedsecret()
        msg += sign(Peer.get_current().key, SHA256(shared))
        self.awaiting_approval[(addr,peer.id_node)] = (shared,addr,peer,success,failure)
        loop.create_task(self._lower_sendto(msg,addr))
        

    async def sendto(self, msg, addr):
        tmp = bytearray([Noise.FALLTHROUGH])
        if self.encryption_mode == "plaintext":
            tmp += msg
            await self._lower_sendto(tmp, addr)
        elif self.encryption_mode == "aes":
            if self.encryptions.get(addr) == None:
                raise Exception("NO AUTHENTICATED CONNECTION")
            self.encryptions[addr]
            
    def approve_peer(self, addr, peer: Peer, success, failure):
        if self.approved_connections.get((addr,peer.id_node)) != None and self.approved_connections.get((addr,peer.id_node)).id_node == peer.id_node  \
        and self.approved_connections.get((addr,peer.id_node)).addr[0] == peer.addr[0] \
        and self.approved_connections.get((addr,peer.id_node)).addr[1] == peer.addr[1]:
            return success(addr,peer)
            
        if self.awaiting_approval.get((addr,peer)) != None:
            print("already waiting")
            return
        if peer.id_node != SHA256(peer.pub_key):
            print("failed sha256")
            return failure(addr,peer)
        
        if not self.strict:
            return success(addr,peer)
        
        if addr[0] != peer.addr[0] or addr[1] != peer.addr[1]:
            print("wrong addy")
            return failure(addr,peer)
        
        if not isinstance(peer.pub_key, bytes):
            print("no pubkey", type(peer.pub_key))
            return failure(addr,peer)
        
        self.send_challenge(addr,peer,success,failure)
            
        
        
        