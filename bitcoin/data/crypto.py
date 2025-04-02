"""
Wrapper module for required cryptography operations.
"""

import hashlib
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding
import json


def create_keypair() -> tuple:
    """
    Creates random 2048-bit private and public key for RSA.

    Returns:
        tuple: Private and public keys.
    """
    priv = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    pub = priv.public_key()
    return priv, pub


def hash_pubkey(pub: rsa.RSAPublicKey) -> str:
    """
    Hashes an RSA DER-encoded public key with sha256 and ripemd160, like
    in bitcoin. The openssl legacy provider must be enabled for this
    method to work, as there is no fallback function.

    Args:
        pub (rsa.RSAPublicKey): Key to hash

    Returns:
        str: String hexdigest for the key.
    """
    key_bytes = pub.public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    hash160 = hashlib.new("ripemd160")
    hash160.update(hashlib.sha256(key_bytes).digest())
    return hash160.hexdigest()


def dump_pubkey(pub: rsa.RSAPublicKey) -> bytes:
    """
    Serializes the received public key in DER format.

    Args:
        pub (rsa.RSAPublicKey): Key to hash.

    Returns:
        str: String hex value for the key.
    """
    key_bytes = pub.public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return key_bytes.hex()


def load_pubkey(pub: str) -> rsa.RSAPublicKey:
    """
    Loads a serialized DER public key.

    Args:
        pub (str): Serialized key.

    Returns:
        rsa.RSAPublicKey: Public key.
    """
    return serialization.load_der_public_key(bytes.fromhex(pub))


def dump_privkey(priv: rsa.RSAPrivateKey) -> str:
    """
    Serializes the received private key in DER format.

    Args:
        pub (rsa.RSAPrivateKey): Key to hash.

    Returns:
        str: String hex value for the key.
    """
    key_bytes = priv.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return key_bytes.hex()


def load_privkey(priv: str) -> rsa.RSAPrivateKey:
    """
    Loads a serialized DER private key.

    Args:
        priv (str): Serialized key.

    Returns:
        rsa.RSAPrivateKey: Public key.
    """
    return serialization.load_der_private_key(bytes.fromhex(priv), password=None)


def load_signature(data: str) -> bytes:
    """
    Parses a serialized signature.

    Args:
        data (str): Serialized signature.

    Returns:
        bytes: Byte representation of the signature.
    """
    return bytes.fromhex(data)


def sign(priv: rsa.RSAPrivateKey, data: str) -> str:
    """
    Signs the given data with a private key. The hash algorithm used for this
    signature is sha256.

    Args:
        priv (rsa.RSAPrivateKey): Private key.
        data (str): serialized data to sign.

    Returns:
        str: String representation of the signature.
    """
    return priv.sign(
        data=hashlib.sha256(data.encode()).digest(),
        padding=padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH
        ),
        algorithm=hashes.SHA256(),
    ).hex()


def verify(pub: rsa.RSAPublicKey, signature: bytes, data: str):
    """
    Verifies private key signed data.

    Args:
        signature (bytes): Byte representation of the signature.
        data (str): serialized data that was signed.
    """
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


def hash_transaction(t: dict) -> str:
    """
    Computes the sha256 hash for a transaction.

    Args:
        t(dict): Transaction

    Returns:
        str: Hash value of the transaction.
    """
    return hashlib.sha256(json.dumps(t).encode()).hexdigest()
