import asyncio
from typing import Any, Callable, List
from deccom.cryptofuncs.hash import SHA256
from deccom.peers.peer import Peer
from deccom.protocols.abstractprotocol import AbstractProtocol
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from os import urandom
from deccom.cryptofuncs.signatures import *

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
        if encryption_mode.lower() not in ["plaintext", "chacha", "sign_only"]:
            raise Exception(f"Encryption mode not recognised: ${encryption_mode}, should be one of plaintext, sign_only, or chacha")
        if not strict and encryption_mode != "plaintext":
            raise Exception("Not strict mode requires plaintext encryption mode")
        self.encryption_mode = encryption_mode.lower()
        self.strict = strict
        self.awaiting_approval: dict[tuple[tuple[str,int],bytes], tuple[int, Peer, tuple[str,int], Callable, Callable]] = dict()
        self.approved_connections: dict[tuple[tuple[str,int],bytes], Peer] = dict()
        self.keys: dict[tuple[str,int], tuple[ChaCha20Poly1305,Peer]] = dict()
    def process_datagram(self, addr: tuple[str, int], data: bytes):
        if data[0] == Noise.CHALLENGE:
            print("CHALLENGE FROM")
            other, i = Peer.from_bytes(data[1:])
            i+=1
            if addr[0] != other.addr[0] or addr[1] != other.addr[1]:
                print("wrong addy")
                return
            shared = get_secret(Peer.get_current().key, from_bytes(other.pub_key))
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
                self.keys[addr] = (ChaCha20Poly1305(shared),other)
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
            if addr[0] != other.addr[0] or addr[1] != other.addr[1]:
                print("wrong addy")
                return
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
            self.keys[addr] = (ChaCha20Poly1305(shared),other)
            success(addr,other)
        elif data[0] == Noise.FALLTHROUGH or data[0] ^ Noise.FALLTHROUGH == 64 or data[0] ^ Noise.FALLTHROUGH == 192:
            strategy = data[0] ^ Noise.FALLTHROUGH
            if strategy == 0:
                strategy == "plaintext"
            elif strategy == 192:
                strategy == "chacha"
            elif strategy == 64:
                strategy == "sign_only" 
            if self.strict and self.encryption_mode != strategy:
                return
            
            

            if strategy == "plaintext":
                self.callback(addr,data[1:])
            elif strategy == "sign_only":
                if len(data) < 66:
                    return
                signature = data[1:65]
                if self.keys.get(addr) == None:
                    return
                other = self.keys[addr][1]

                if not verify(other.pub_key,SHA256(data[65:]),signature):
                    return
                return self.callback(addr,data[65:])
            elif strategy == "chacha":
                if len(data) < 78:
                    return
                if self.keys.get(addr) == None:
                    return
                other = self.keys[addr][1]
                nonce = data[1:13]
                signature = data[13:77]
                try:
                    decrypted = self.keys[addr][0].decrypt(nonce,data[77:],signature)
                except:
                    return
                if not verify(other.pub_key,SHA256(decrypted),signature):
                    return
                return self.callback(addr, decrypted)


    def send_challenge(self, addr, peer: Peer, success, failure):
        print("SENDING CHALLLENGE")
        loop = asyncio.get_running_loop()
        msg = bytearray([Noise.CHALLENGE])
        msg += bytes(Peer.get_current())
        shared = get_secret(Peer.get_current().key, from_bytes(peer.pub_key))
        # print(len(sign(Peer.get_current().key, SHA256(shared))))
        msg += sign(Peer.get_current().key, SHA256(shared))
        self.awaiting_approval[(addr,peer.id_node)] = (shared,peer,addr,success,failure)
        loop.create_task(self._lower_sendto(msg,addr))
        

    async def sendto(self, msg, addr):
        prepend = Noise.FALLTHROUGH
        tmp = bytearray([])
        if self.encryption_mode == "plaintext":
            # prepend = prepend ^ b'00000000'
            tmp += bytes(prepend)
            tmp += msg
            return await self._lower_sendto(tmp, addr)
        elif self.encryption_mode == "chacha":
            if self.keys.get(addr) == None:
                raise Exception("NO AUTHENTICATED CONNECTION")
            prepend = bytes(prepend ^ b'11000000')
            tmp += prepend
            aed = self.keys[addr][0]
            nonce = urandom(12)
            signature = sign(Peer.me.key, SHA256(msg))
            tmp += nonce + signature
            tmp += aed.encrypt(nonce,msg,signature)
            return await self._lower_sendto(tmp, addr)

        elif self.encryption_mode == "sign_only":
            prepend = prepend ^ b'01000000'
            tmp += bytes(prepend)
            tmp+= sign(Peer.get_current().key,SHA256(msg))
            tmp += msg
            return await self._lower_sendto(tmp, addr)
            
            
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
            
        
        
        