from ecdsa import SigningKey, NIST256p, VerifyingKey

def gen_key():
    return SigningKey.generate(curve=NIST256p)

def sign(key: SigningKey, hash: bytes):
    
    return key.sign_deterministic(hash)
def verify(key: VerifyingKey, hash, sign):
    if isinstance(key,bytes):
        key = VerifyingKey.from_der(key)
    
    return key.verify(sign,hash)


# tst_key = gen_key()
# print(tst_key.verifying_key)
# pub_key = tst_key.verifying_key.to_der()
# pub_key = VerifyingKey.from_der(pub_key)
# print(pub_key)
# assert pub_key == tst_key.verifying_key