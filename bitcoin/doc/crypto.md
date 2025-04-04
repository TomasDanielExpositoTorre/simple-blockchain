# Cryptography

Bitcoin makes use of many cryptographic algorithms to validate transactions, among which are hash functions and elliptic curves. We have decided to group all of this functionality in a single module, so the rest of the application only needs to call these functions, which can be adapted at any time.

[← Back to Bitcoin](../README.md)  

[← Back to Home](../../README.md)

---

## Table of Contents
- [Public Cryptography and Keypairs](#public-cryptography-and-keypairs)
    - [Serializers](#serializers)
    - [Signatures and Verification](#signatures-and-verification)
- [Hashing Algorithms](#hashing-algorithms)

---

## Public Cryptography and Keypairs

For this implementation, the asymmetric algorithm we use is RSA, instead of the [elliptic curve cryptography](https://learnmeabitcoin.com/technical/cryptography/elliptic-curve/) used by bitcoin. The basis remains the same: all the data that you want to own (be it bitc oin or arbitrary data) is associated to your public key, and ownership on that data is proved through your private key.

A method is provided to create a **2048-bit** keypair for this algorithm.

### Serializers

Some of the methods provided in the crypto module are only for use when testing this application, and are discouraged from use on any real-life scenarios. For instance, there are some **keypair serialization** methods that are used to share private keys between nodes and the main server. While this is okay for public key sharing, **private keys** should not be shared under any circumstances.

These methods are implemented with the keywords **dumps** and **loads**.

### Signatures and Verification

Again, private keys shoudl not be shared under any circumstances, but are required to prove ownership. This is done by **signing** (in our case, the amount/data we want to transfer), where the public key associated to the data can be used to **verify** that signature. No other private key can make this verification succeed, so it effectively proves you own the data.

---

## Hashing Algorithms

Hashing algorithms are widely utilized in bitcoin, if anything for the sole purpose of reducing the time it takes to validate data in the chain. As an example, creating a signature of data over 300TB would take half a year. The SHA256 hash of that value can be computed in under 42 hours, and the signature is produced immediately.

It also helps reducing the size of the chain, by, for example, hashing a public key like it is done in **P2PKH** to reduce its size to 160 bytes. Bitcoin uses RIPEMD160 along SHA256 to generate these keyhashes, and the idea is akin to buying **two firewalls from different companies**. If the first firewall has a security vulnerability, you wouldn't want it to also appear on the second firewall as well. The same can be said for both hashing algorithms.

Finally, we also hash the transactions. This is used to both verify that even if valid, the transactions have not been tampered on our specific implementation. In reality, these changes would be immediately reflected on the merkle tree root, so there is nothing to worry about. Additionally, we use these hashes to populate the UTXO set for easier access.

Algorithms like the dual-sha256 used to hash the block and some transactions were not included in this module, simply because they are not used outside the block itself.


[↑ Back to Top](#blockchain)  

[← Back to Bitcoin](../README.md)  

[← Back to Home](../../README.md)