"""
Wrapper module for repeated cryptography operations
"""
import hashlib
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding
import json

def create_keypair():
    priv = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )
    pub = priv.public_key()
    return priv, pub

def hash_pubkey(pub: rsa.RSAPublicKey):
    key_bytes = pub.public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    hash160 = hashlib.new("ripemd160")
    hash160.update(hashlib.sha256(key_bytes).digest())
    return hash160.hexdigest()


def dump_pubkey(pub: rsa.RSAPublicKey):
    key_bytes = pub.public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return key_bytes.hex()


def load_pubkey(pub: str) -> rsa.RSAPublicKey:
    return serialization.load_der_public_key(bytes.fromhex(pub))

def load_signature(data: str):
    return bytes.fromhex(data)


def sign(priv: rsa.RSAPrivateKey, data: str):
    return priv.sign(
        data=hashlib.sha256(data.encode()).digest(),
        padding=padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH
        ),
        algorithm=hashes.SHA256(),
    ).hex()


def verify(pub: rsa.RSAPublicKey, signature: bytes, data: str):
    try:
        pub.verify(
            signature=signature,
            data=hashlib.sha256(data.encode()).digest(),
            padding=padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH
            ),
            algorithm=hashes.SHA256(),
        )
        return True
    except Exception:
        return False
    
def hash_transaction(t: dict):
    return hashlib.sha256(json.dumps(t).encode()).hexdigest()