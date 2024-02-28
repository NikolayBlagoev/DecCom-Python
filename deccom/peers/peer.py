import random
from deccom.cryptofuncs.hash import SHA256
from deccom.cryptofuncs.signatures import gen_key, to_bytes
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from typing import Union

class Peer(object):
    me: 'Peer'

    def __init__(self, addr, pub_key: Ed25519PrivateKey  = None, tcp = None, id_node = None, proof_of_self = None) -> None:

        self.priv_key = None
        if pub_key == None:
            self.key = gen_key()
            pub_key = to_bytes(self.key.public_key())
            print(len(pub_key))
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


  # |------------------------|
  # | Length of id_node (4B) |
  # |------------------------|
  # | id_node (variable)     |
  # |------------------------|
  # | Length of pub_key (4B) |
  # |------------------------|
  # | pub_key (variable)     |
  # |------------------------|
  # | Type of pub_key (1B)   |
  # |------------------------|
  # | Length of addr[0] (4B) |
  # |------------------------|
  # | addr[0] (variable)     |
  # |------------------------|
  # | addr[1] (2B)           |
  # |------------------------|
  # | tcp (2B, if present)   |
  # |------------------------|

    def __bytes__(self)->bytes:
        ret = bytearray()
        ret += len(self.id_node).to_bytes(4, byteorder="big") + self.id_node
        if isinstance(self.pub_key, bytes):
            encd = self.pub_key
            ret += len(encd).to_bytes(4, byteorder="big") + encd + int(1).to_bytes(1, byteorder="big")
        elif isinstance(self.pub_key, str):
            # print("STRING INSTANCE")
            encd = self.pub_key.encode("utf-8")
            ret += len(encd).to_bytes(4, byteorder="big") + encd + int(2).to_bytes(1, byteorder="big")
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

    @staticmethod
    def from_bytes(b: bytes):
        reader = byte_reader(b)

        id_node = reader.read_next_variable(4)
        pub_key_bytes =  reader.read_next_variable(4)
        pub_key_version = int.from_bytes(reader.read_next(1))
        ip = reader.read_next_variable(4).decode("utf-8")
        port = int.from_bytes(reader.read_next(2))
        tcp: Union[int, None] = int.from_bytes(reader.read_next(2))

        pub_key: Union[bytes, str]
        if pub_key_version == 1:
            pub_key = pub_key_bytes
        elif pub_key_version == 2:
            pub_key = pub_key_bytes.decode("utf-8")
        else:
            raise TypeError("Error parsing bytes. Malformed version number detected.")

        if tcp == 0:
            tcp = None

        return Peer((ip,port), pub_key, tcp ,id_node), byte_reader.head #type: ignore

    @staticmethod
    def get_current():
        return Peer.me


class byte_reader:
    def __init__(self, data:bytes):
        self.data:bytes = data
        self.head:int = 0

    def read_next_variable(self, length: int):
        self.head += length
        size = int.from_bytes(self.data[self.head-length:self.head])
        return self.read_next(size)

    def read_next(self, length: int):
        self.head += length
        self.check_health()
        return self.data[self.head-length:self.head]

    def check_health(self):
        if self.head > len(self.data):
            raise IndexError("Error parsing data. reading at:", self.head, "/", len(self.data))
