from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.serialization import PublicFormat, PrivateFormat, Encoding, NoEncryption, KeySerializationEncryption
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives import hashes
from fe25519 import fe25519
from ge25519 import ge25519, ge25519_p3

def gen_key():
    return Ed25519PrivateKey.generate()

def sign(key: Ed25519PrivateKey, hash: bytes):
    if not isinstance(hash,bytes):
        raise AttributeError("Unsupported format to hash. Expected bytes but got ",type(hash))
    return key.sign(hash)

def load_key(bts):
    return Ed25519PrivateKey.from_private_bytes(bts)


"""
Verifies an ED25519 signature. 

Parameters
----------
key 
    Public key of the other party

hash : bytes 
    The hash of the message

sign : bytes
    The other party's signature

Returns
----------
bool
    Whether verification was successful

Raise
----------
AttributeError
"""

def verify(key: Ed25519PublicKey, hash: bytes, sign: bytes):
    if not isinstance(hash,bytes):
        raise AttributeError("Unsupported format to verify. Expected bytes but got ",type(hash))
    if isinstance(key,bytes):
        key = Ed25519PublicKey.from_public_bytes(key)
    try:
        key.verify(sign,hash)
        return True
    except InvalidSignature: 
        return False

def to_bytes(key: Ed25519PublicKey):
    return key.public_bytes(Encoding.Raw, PublicFormat.Raw)
def from_bytes(key: bytes):
    return Ed25519PublicKey.from_public_bytes(key)



"""
Given two Ed25519, computes a shared secret between them to be used in Ec-DH. The alogirthm is symmteric - so party one with their private key and the other 
party's public key will compute the same result as the other party with their private key and party one's public key. Read more at: 
https://en.wikipedia.org/wiki/Elliptic-curve_Diffie%E2%80%93Hellman

Parameters
----------
key : Ed25519PrivateKey
    Private key of one party

remote :  Ed25519PublicKey
    Public key of the other party


Returns
----------
shared key between the two parties

Raise
----------
ValueError
"""

def get_secret(key:Ed25519PrivateKey, remote: Ed25519PublicKey):
    bts = key.private_bytes(encoding=Encoding.Raw, format=PrivateFormat.Raw, encryption_algorithm=NoEncryption())
    privatedh = X25519PrivateKey.from_private_bytes(x25519_from_ed25519_private_bytes(bts))
    bts = remote.public_bytes(encoding=Encoding.Raw, format=PublicFormat.Raw)
    publicdh =  X25519PublicKey.from_public_bytes(x25519_from_ed25519_public_bytes(bts))
    
    return privatedh.exchange(publicdh)



# from: https://github.com/pyca/cryptography/issues/5557
# idk why they do not add it to their repo but oh well :/
def x25519_from_ed25519_private_bytes(private_bytes):
    
    hasher = hashes.Hash(hashes.SHA512())
    hasher.update(private_bytes)
    h = bytearray(hasher.finalize())
    
    h[0] &= 248
    h[31] &= 127
    h[31] |= 64

    return h[0:32]



"""
Generates a public x25519 key from a public ed25519 key
"""


def x25519_from_ed25519_public_bytes(public_bytes) -> X25519PublicKey:
    
    # This is libsodium's crypto_sign_ed25519_pk_to_curve25519 translated into
    # the Pyton module ge25519.
    if ge25519.has_small_order(public_bytes) != 0:
        raise ValueError("Doesn't have small order")

    # frombytes in libsodium appears to be the same as
    # frombytes_negate_vartime; as ge25519 only implements the from_bytes
    # version, we have to do the root check manually.
    A = ge25519_p3.from_bytes(public_bytes)
    if A.root_check:
        raise ValueError("Root check failed")

    one_minus_y = fe25519.one() - A.Y
    x = A.Y + fe25519.one()
    x = x * one_minus_y.invert()

    return bytes(x.to_bytes())
