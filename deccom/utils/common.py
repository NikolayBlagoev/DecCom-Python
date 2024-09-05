from socket import socket
from concurrent.futures import ThreadPoolExecutor

"""
Find an open port

Return
--------
int
    Avaialble open port
"""

def find_open_port():
    ret = None
    with socket() as s:
        s.bind(('',0))

        ret = s.getsockname()[1]
        s.close()
    return ret

def ternary_comparison(b1: bytes,b2: bytes):
    if b1 > b2:
        return 1
    if b1 < b2:
        return -1
    return 0

def get_executor(max_workers = 5):
    return ThreadPoolExecutor(max_workers=max_workers)

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


    def is_done(self):
        return self.head >= len(self.data)
    def check_health(self):
        if self.head > len(self.data):
            raise IndexError("Error parsing data. reading at:", self.head, "but data has length", len(self.data))
    def get_head(self):
        return self.head
    

class byte_writer:
    def __init__(self, header: int = None):
        
        if header != None:
            self.data = bytearray([header])
        else:
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