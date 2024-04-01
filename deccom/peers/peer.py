import random
from deccom.cryptofuncs.hash import SHA256
from deccom.cryptofuncs.signatures import gen_key, to_bytes
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from typing import Union

class Peer(object):
    def __init__(self, addr, pub_key: Ed25519PrivateKey  = None, tcp = None, id_node = None, proof_of_self = None) -> None:
        self.priv_key = None
        if pub_key == None:
            self.key = gen_key()
            pub_key = to_bytes(self.key.public_key())
        elif pub_key == "":
            pub_key = f"{random.randint(0,100000)}"

        if id_node == None:
            id_node = SHA256(pub_key)

        self.id_node = id_node
        self.pub_key = pub_key
        self.addr = addr
        self.tcp = tcp
        self.external_addr = addr
        # self.heard_from = None
        # if proof_of_self != None:
        #     proof_of_self = SHA256([pub_key,addr[0],addr[1],])
        # print("pub_key",pub_key)
        pass

    # |------------------------|
    # | Control header (1B)    |
    # |------------------------|
    # | pub_key (MAX 63B)      |
    # |------------------------|
    # | addr[0] (4B)           |
    # |------------------------|
    # | addr[1] (2B)           |
    # |------------------------|
    # | tcp (2B)               |
    # |------------------------|
    # Control header contains (LSB FIRST):
    # 6 Bits size of pub_key
    # 1 Bits type of pub_key
    # 1 Bit if TCP is present


    def __bytes__(self)->bytes:
        writer = byte_writer()
        control_header = 0
        pb_key_encoded = None
        if isinstance(self.pub_key, bytes):
            pb_key_encoded = self.pub_key
            
        elif isinstance(self.pub_key, str):
            pb_key_encoded = self.pub_key.encode("utf-8")
            control_header += 64
        else:
            raise Exception("INVALID PUBLIC KEY")
        control_header += len(pb_key_encoded)
        # print("CONTROL HEADER", control_header, "lnpubkey", len(pb_key_encoded),".")
        if self.tcp != None:
            control_header += 128
        writer.write_int(1, control_header)
        writer.write_raw(pb_key_encoded)
        writer.write_ip(self.addr[0])
        writer.write_int(2, self.addr[1])
        if self.tcp != None:
            writer.write_int(2, self.tcp)
        return writer.bytes()

    @staticmethod
    def from_bytes(b: bytes) -> tuple["Peer", int]:
        # print(len(b))
        reader = byte_reader(b)
        control_header = reader.read_next_int(1)
        ln_pub_key = control_header % 64
        # print("CONTROL HEADER", control_header, "lnpubkey", ln_pub_key,".")
        control_header = control_header // 64
        type_of_key = control_header % 2
        tcp_present = control_header // 2 == 1
        pub_key = reader.read_next(ln_pub_key)
        ip = reader.read_ip()
        port = reader.read_next_int(2)

        if type_of_key == 0:
            pub_key = pub_key
        elif type_of_key == 1:
            pub_key = pub_key.decode("utf-8")
        else:
            raise TypeError("Error parsing bytes. Malformed version number detected.",type_of_key)
        tcp = None
        if tcp_present:
            tcp = reader.read_next_int(2)
        
        return Peer((ip,port), pub_key = pub_key, tcp = tcp), reader.get_head() #type: ignore



class byte_reader:
    def __init__(self, data:bytes):
        self.data:bytes = data
        self.head:int = 0

    def read_next_variable(self, length: int):
        self.head += length
        size = int.from_bytes(self.data[self.head-length:self.head], byteorder="big")
        return self.read_next(size)

    def read_next(self, length: int):
        self.head += length
        self.check_health()
        return self.data[self.head-length:self.head]

    def read_next_int(self, length: int) -> int:
        self.head += length
        self.check_health()
        return int.from_bytes(self.data[self.head-length:self.head], byteorder="big")

    def read_ip(self) -> str:
        ret = ""
        for _ in range(4):
            
            ret += str(self.read_next_int(1)) + "."

        return ret[:-1]



    def check_health(self):
        if self.head > len(self.data):
            raise IndexError("Error parsing data. reading at:", self.head, "but data has length", len(self.data))
    def get_head(self):
        return self.head
    

class byte_writer:
    def __init__(self):
        self.data = bytearray()

    def write_variable(self, length:int, data):
        self.data += len(data).to_bytes(length, byteorder="big")
        self.data += data
        return self

    def write_int(self, length:int, data: int):
        
        self.data += data.to_bytes(length, byteorder="big")
        return self

    def write_raw(self, data:bytes):
        self.data += data

    def bytes(self):
        return bytes(self.data)
    
    def write_ip(self, ip: str):
        ret = 0
        split_ip = ip.split(".")
        for part in split_ip:
            ret *= 256
            ret += int(part)
            
        
        self.data += ret.to_bytes(4, byteorder="big")
        return self

