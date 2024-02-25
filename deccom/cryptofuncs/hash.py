import hashlib
def _helper(inp, encoding):
    if isinstance(inp, str):
        inp = inp.encode(encoding)
    elif isinstance(inp, int):
        inp = inp.to_bytes(64, byteorder="big")
    elif isinstance(inp, bytes):
        # print("bytes")
        inp = inp
    else:
        raise Exception("Unsupported format",type(inp))
    return inp
    
def SHA256(inp, salt: bytes = None, encoding = "utf-8"):
    digest = hashlib.sha256()
    if isinstance(inp,str) or isinstance(inp,int) or isinstance(inp,bytes):
        inp = _helper(inp,encoding)
    elif isinstance(inp, list):
        tmp = bytearray()
        for i in inp:
            tmp += _helper(inp,encoding)
        inp = bytes(tmp)
    else:
        print("unsupported format")
    if salt != None:
        digest.update(salt + inp)
    else:
        digest.update(inp)
    return digest.digest()

