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
            print(pub_key)
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
        writer = byte_writer()
        writer.write_variable(4, self.id_node)

        if isinstance(self.pub_key, bytes):
            writer.write_variable(4, self.pub_key).write(1,1)
        elif isinstance(self.pub_key, str):
            writer.write_variable(4, self.pub_key.encode("utf-8")).write(1,2)
        else:
            print(self.pub_key)
            raise Exception("INVALID PUBLIC KEY")

        writer.write_variable(4, self.addr[0].encode("utf-8")).write(2, self.addr[1])

        if self.tcp != None:
            writer.write(2, self.tcp)
        else:
            writer.write(2, 0)

        return writer.bytes()

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

class byte_writer:
    def __init__(self):
        self.data = bytearray()

    def write_variable(self, length:int, data):
        self.data += len(data).to_bytes(length, byteorder="big")
        self.data += data
        return self

    def write(self, length:int, data):
        self.data += data.to_bytes(length, byteorder="big")
        return self

    def write_raw(self, data:bytes):
        self.data += data

    def bytes(self):
        return bytes(self.data)
