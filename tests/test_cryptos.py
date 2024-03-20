
import unittest
from deccom.cryptofuncs.hash import _helper, SHA256
from deccom.cryptofuncs.signatures import *
from random import randint
from os import urandom
class test_crypts(unittest.TestCase):
    


    def test_enc_int(self):
        for _ in range(1000):
            t = randint(0,100000000000000)
            encd = _helper(t, "utf-8")
            self.assertEqual(t, int.from_bytes(encd, byteorder="big"))
    
    def test_enc_str_utf_8(self):
        for _ in range(1000):
            t = f"fa{randint(0,100000000000000)}+{randint(0,100000000000000)}"
            encd = _helper(t, "utf-8")
            self.assertEqual(t, encd.decode("utf-8"))    
        
    def test_enc_str_ascii(self):
        for _ in range(1000):
            t = f"fa{randint(0,100000000000000)}+{randint(0,100000000000000)}"
            encd = _helper(t, "ASCII")
            self.assertEqual(t, encd.decode("ASCII"))  

    def test_enc_bytes(self):
        for _ in range(1000):
            t = urandom(4)
            encd = _helper(t, "ASCII")
            self.assertEqual(t, encd)  
    def test_hash(self):
        for _ in range(10):
            t = randint(0,100000000000000)
            hsh = SHA256(t)
            self.assertEqual(32, len(hsh))
        for _ in range(10):
            t = f"fa{randint(0,100000000000000)}+{randint(0,100000000000000)}"
            hsh = SHA256(t)
            self.assertEqual(32, len(hsh)) 
    def test_salt(self):
        for _ in range(10):
            t = randint(0,100000000000000)
            hsh = SHA256(t)
            slt = SHA256(t, salt=urandom(4))
            self.assertNotEqual(hsh, slt)

    def test_key_gen(self):
        key = gen_key()
        pubkey = key.public_key()
        self.assertEqual(len(key.private_bytes(encoding=Encoding.Raw, format=PrivateFormat.Raw, encryption_algorithm=NoEncryption())),32)
        self.assertEqual(len(pubkey.public_bytes(encoding=Encoding.Raw, format=PublicFormat.Raw)),32)

    def test_sign_verify(self):
        key = gen_key()
        pubkey = key.public_key()
        ret = sign(key, SHA256(0))
        self.assertEqual(True, verify(pubkey, SHA256(0), ret))
    
    def test_secret(self):
        key1 = gen_key()
        pubkey1 = key1.public_key()
        key2 = gen_key()
        pubkey2 = key2.public_key()

        s1 = get_secret(key1, pubkey2)
        s2 = get_secret(key2, pubkey1)
        self.assertEqual(s1,s2)

    def test_conversion(self):
        for _ in range(5):
            key1 = gen_key()
            pubkey1 = key1.public_key()
            self.assertEqual(from_bytes(to_bytes(pubkey1)), pubkey1)

    def test_specific(self):
        
        key1 = load_key(b'\xdb\xf7U\x9bm\xa2q\xb6\xc1H\xde\xbfh$&\x98\xe0\xc9\xefC\x91\xd0`\xfe\xaa_\xf3\x9f\x87\x7f\xf4\x00')
        pubkey1 = key1.public_key()
        self.assertEqual(sign(key1, SHA256(43)), b'\x02\x17f"%Y\xf6y\xaf\xc8`\xff\x16L\xd1\x90\xce\xe8\xaeQ\xae\x1e2\xf4\xf2\x0c\x82P]\xd5:\x05\xcf\xc1k\xe5\x8c&\xac\xf5\x9d`\xdc\x9e\xbb\tX\x81\xb6Z\xa2\xb9z\xe9a}Z\xf6\x1e\x14\xe8\x85z\x0e')
if __name__ == '__main__':
    unittest.main()
