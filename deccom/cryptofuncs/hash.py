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
        raise AttributeError("Unsupported format",type(inp))
    return inp


"""
Generates a SHA256 of a given input. Input can be of type string, bytes, int, or a list of them. 

Parameters
----------
name 
    Input to be hashed

salt : bytes 
    The salt to add to the hash (default is None). Salt is added to the end of the input.

encoding : str
    Encoding to use in case the input is a string. Integers are considered as a 64 big-endian byte string. Defaults to utf-8

Returns
----------
bytes
    The SHA256 representation of the input

Raise
----------
AttributeError
"""

def SHA256(inp, salt: bytes = None, encoding = "utf-8"):
    digest = hashlib.sha256()
    if isinstance(inp,str) or isinstance(inp,int) or isinstance(inp,bytes):
        digest.update(_helper(inp,encoding))
    elif isinstance(inp, list):
        for i in inp:
            digest.update(_helper(inp,encoding))
    else:
        raise AttributeError("Unsupported format",type(inp))

    if salt != None:
        digest.update(salt)

    return digest.digest()

