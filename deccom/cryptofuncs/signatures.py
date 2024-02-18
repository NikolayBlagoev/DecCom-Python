from ecdsa import SigningKey, NIST256p, VerifyingKey

def gen_key():
    return SigningKey.generate(curve=NIST256p)

def sign(key: SigningKey, hash):
    
    return key.sign(hash)
def verify(key: VerifyingKey, hash, sign):
    
    return key.verify(sign,hash)
