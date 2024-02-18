from socket import socket
def find_open_port():
    ret = 10010
    with socket() as s:
        s.bind(('',0))
        ret = s.getsockname()[1]
    return ret

def ternary_comparison(b1,b2):
    if b1 > b2:
        return 1
    if b1 < b2:
        return -1
    return 0