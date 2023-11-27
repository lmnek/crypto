import hashlib
import os
import ecdsa
import base58

def generate_address():
    private_key = os.urandom(32)
    public_key = derive_public_key(private_key)

    # Hash the public key - sha56 -> ripemd160
    sha256 = hashlib.sha256(public_key).digest()
    network_bitcoin_public_key = hashlib.new('ripemd160', sha256).digest()

    # Checksum = 4 bytes of double SHA-256  
    checksum = hashlib.sha256(hashlib.sha256(network_bitcoin_public_key).digest()).digest()[:4]

    # Append checksum and convert to base58
    binary_address = network_bitcoin_public_key + checksum
    bitcoin_address = base58.b58encode(binary_address)

    return private_key.hex(), bitcoin_address.decode()

# Use ECDSA
def derive_public_key(private_key):
    sk = ecdsa.SigningKey.from_string(private_key, curve=ecdsa.SECP256k1)
    return b'\x04' + sk.verifying_key.to_string()  # prefix for uncompressed public key 

