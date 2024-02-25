import random
from deccom.cryptofuncs.hash import SHA256
from deccom.cryptofuncs.signatures import *
from ecdsa import SigningKey
class Peer(object):
    me = None
    def __init__(self, addr, pub_key: SigningKey  = None, tcp = None, id_node = None, proof_of_self = None) -> None:
       
        self.priv_key = None
        if pub_key == None:
            self.key = gen_key()
            pub_key = self.key.verifying_key.to_der()
            self.priv_key = self.key.to_string()
            print(type(self.key))
            # print(pub_key)
        elif pub_key == "":
            pub_key = f"{random.randint(0,100000)}"
        
        if id_node == None:
            id_node = SHA256(pub_key)
        
        self.id_node = id_node
        self.pub_key = pub_key
        self.addr = addr
        self.tcp = tcp
        # if proof_of_self != None:
        #     proof_of_self = SHA256([pub_key,addr[0],addr[1],])
        # print("pub_key",pub_key)
        pass

    def __bytes__(self)->bytes:
        ret = bytearray()
        ret += len(self.id_node).to_bytes(4, byteorder="big") + self.id_node
        if isinstance(self.pub_key, bytes):
            encd = self.pub_key
            ret += len(encd).to_bytes(4, byteorder="big") + int(1).to_bytes(1, byteorder="big") + encd
        elif isinstance(self.pub_key, str):
            # print("STRING INSTANCE")
            encd = self.pub_key.encode("utf-8")
            ret += len(encd).to_bytes(4, byteorder="big") + int(2).to_bytes(1, byteorder="big") + encd
        else:
            raise Exception("INVALID PUBLIC KEY")
        encd = self.addr[0].encode(encoding="utf-8")
        ret += len(encd).to_bytes(4, byteorder="big") + encd
        ret += self.addr[1].to_bytes(2, byteorder="big")
        if self.tcp != None:
            ret += self.tcp.to_bytes(2, byteorder="big")
        else:
            ret += int(0).to_bytes(2, byteorder="big")
        return bytes(ret)
    
    def from_bytes(b: bytes):
        i = 0
        tmp = int.from_bytes(b[0:4], byteorder="big")
        i+=4
        
        id_node = b[i:i+tmp]
        i+=tmp
        
        tmp = int.from_bytes(b[i:i+4], byteorder="big")
        i+=4
        
        ver = int.from_bytes(b[i:i+1], byteorder="big")
        i+=1
        

        if ver == 1:
        
            pub_key = b[i:i+tmp]
        elif ver == 2:
            pub_key = b[i:i+tmp].decode("utf-8")
        i+=tmp
        

        tmp = int.from_bytes(b[i:i+4], byteorder="big")
        i+=4
        

        ip = b[i:i+tmp].decode("utf-8")
        i+=tmp
       
        port = int.from_bytes(b[i:i+2], byteorder="big")
        i+=2
        
        
        
        tcp = int.from_bytes(b[i:i+2], byteorder="big")
        if tcp == 0:
            tcp = None
        i+=2
        
        return Peer((ip,port),pub_key,tcp,id_node), i

    def get_current():
        return Peer.me
