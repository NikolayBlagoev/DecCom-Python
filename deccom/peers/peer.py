import random
from deccom.cryptofuncs.hash import SHA256
from deccom.cryptofuncs.signatures import gen_key, to_bytes
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


from deccom.utils.common import byte_reader, byte_writer

class Peer(object):

    """
    Peer object to store all information about a peer in the system (their identity, ip, port, etc...)
    """


    def __init__(self, addr, pub_key: Ed25519PrivateKey | str  = None, tcp = None, id_node = None, proof_of_self = None) -> None:
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

    

    """
    Generates a byte representation of the peer: 
    |------------------------|
    | Control header (1B)    |
    |------------------------|
    | pub_key (MAX 63B)      |
    |------------------------|
    | addr[0] (4B)           |
    |------------------------|
    | addr[1] (2B)           |
    |------------------------|
    | tcp (2B)               |
    |------------------------|
    Control header contains (LSB FIRST):
    6 Bits size of pub_key
    1 Bits type of pub_key
    1 Bit if TCP is present
    
    Hence a header of 10100000 means TCP is present, Public key is an Ed25519 identity, public key length of 32 bytes (256 bits)
    """

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


    """
    Given a byte representation generates a peer
    
    Return
    ----------

    Peer
        Peer object
    
    int
        The offset of the pointer on the byte list once the peer has been read
    """

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


