import hashlib

def SHA256(inp, salt: bytes = None, encoding = "utf-8"):
    digest = hashlib.sha256()
    if isinstance(inp, str):
        inp = inp.encode(encoding)
    elif isinstance(inp, int):
        inp = inp.to_bytes(8, byteorder="big")
    elif isinstance(inp, bytes):
        # print("bytes")
        inp = inp
    else:
        print("unsupported format")
    if salt != None:
        digest.update(salt + inp)
    else:
        digest.update(inp)
    return digest.digest()

