# Blocks

In bitcoin, blocks carry out the many transactions inside the blockchain. In very simple terms, a block is composed of a header (which is the focus of the *hashcash* problem), and a series of transactions, which can make for a total of about 2MB worth of data.

[← Back to Bitcoin](../README.md)  

[← Back to Home](../../README.md)

---

## Table of Contents
- [Block Header](#the-header)
    - [Merkle Tree](#merkle-tree)
    - [Hashcash and Difficulty](#hashcash-problem-and-difficulty)
- [Transactions](#the-transactions)
    - [Ownership](#ownership-on-transactions)
    - [Mining Reward](#mining-reward)

---

## The Header

A block header is composed of the following fields (adapted from [here](https://learnmeabitcoin.com/technical/block/#structure)):


| **Field**  | **Size** | **Format**      | **Description**
|-------|-----|----------|---------
**Version** | 4 bytes | little-endian | The version number for the block.
**Previous Block** | 32 bytes | natural byte order | The block hash of a previous block this block is building on top of.
**Merkle Root** | 32 bytes | natural byte order | A fingerprint for all of the transactions included in the block.
**Time** | 4 bytes | little-endian | The current time as a Unix timestamp.
**Bits** | 4 bytes | little-endian | A compact representation of the current target.
**Nonce** | 4 bytes | little-endian | Hashcash problem target

With the fields given above, the size of the header is of 80 bytes. However, to simplify the readability of fields, avoid conversion operations (for example, to parse to little endian) and simplify the computation of the block hash, most of these characteristics were ignored. 

The simplified **BlockHeader** dataclass contains the following fields:

| **Field**  | **Type** | **Description**
|------------|----------|----------------|
**Version**  | int      | In bitcoin, the first 3 bits of this number are used to determine the block version, and the other 29 are used for [soft-forks](https://learnmeabitcoin.com/technical/block/version/). In this use-case, since only one implementation of the chain will be used, the version is hardcoded to **1**.
**Parent Hash** | str | Changed the byte representation to string, using twice as much storage (one digit per nibble).
**Merkle Root** | str | Changed the byte representation to string, using twice as much storage (one digit per nibble).
**Time** | int | No changes from the original
**Target** | str | Changed the byte representation to string, using twice as much storage (one digit per nibble).
**Nonce** | int | In bitcoin, this value can only generate up to [$2^{32}$ hashes per block](https://learnmeabitcoin.com/technical/block/#nonce), after which the timestamp value must be recomputed, or the transaction order in the merkle tree shuffled. In this 

To hash this header, the string representation of all fields are concatenated, and then hashed by using a double-SHA256 algorithm.

### Merkle Tree
A merkle tree is, simply put, a set of different data points that are hashed in pairs, until only one remains. This requires the tree to be balanced (have an even number of nodes), and trees with an odd number of transactions usually have the last element duplicated (but not re-inserted in the block).

The algorithm to compute a merkle root is the following:

**1.** Hash all entries in the tree -> $H_1, H_2, H_3, H_4, ...$  
**2.** Concatenate the hashed entries in pairs and hash them again -> $h(H_1+H_2), \ h(H_3+H_4), ...$  
**3.** Repeat step 2 until only one hash value remains.

### Hashcash Problem and Difficulty

The basis of this Proof-of-Work algorithm is the hashcash problem, or "partial hash inversion". This algorithm consists in constantly increasing the *nonce* value in the header, and checking **how many consecutive leading 0's** the resulting hash has. In bitcoin, this is represented by the [bits](https://learnmeabitcoin.com/technical/block/bits/) field, where the first byte corresponds to the exponent (number of zeroes) and the second to the coefficient.

For example, given the difficulty value `0x1DFFFFFF`, the target to beat would be computed this way.

$target =$ `0xFFFFFF` $\times 256$ ^ (`0x1D` $- \  3$)   
$target = $`0x000000FFFFFF0000000000000000000000000000000000000000000000000000` 

The coefficient can be any number of three bytes, and the hash has to be under (or equal) the computed value. In this application, it is fixed to this value to reduce the problem to a leading number of zeroes instead.

Bitcoin updates this difficulty field once every two weeks, to keep the solution arrival time to around 10 minutes. In our case, this difficulty is automatically adjusted based on the number of nodes (processes) that join the network. The time required to arrive at a solution is significantly under 10 minutes, because let's face it, no one wants to wait 10 minutes to test a command line application.

---

## The Transactions

As mentioned above, a block in bitcoin is usually 2MB in size. This means that not every transaction from a miner's pool is chosen to take part of a block, and instead some sorting criteria is applied. Usually, as mining is done for monetary profit (electricity is consumed for the hashcash problem), this means that transactions with the highest **mining fee** are prioritized over others on blocks.

To understand how transactions and moving coins works in bitcoin, let us use a very simple JSON example from this application (the [original](https://learnmeabitcoin.com/technical/transaction/#structure) transaction structure is more complicated):
```json
"version": 1,
"inputs": [
    {
    "tx_id": "0011223344...",
    "v_out": 0,
    "key": "my-public-key",
    "signature": "data-signature"
    }
],
"outputs": [
    {
    "amount": 10,
    "keyhash": "new-owner-key-hash"
    },
    {
    "data": "some-other-data",
    "keyhash": "new-owner-key-hash"
    }
]
```
Transactions in bitcoin work through using both **inputs** (where the money comes from) and **outputs** (where the money goes to). Once an input is spent, it cannot be used again. So, from the previous example, suppose that:
- The outpoint (transaction id + v_out) contains 11 bitcoin.
- You are paying 10 bitcoin to some entity, whose public key (address) hashes to `"new-owner-hey-hash"`

Then, what would happen to the one remaining bitcoin from your initial input (which you own), is it just *partially spent*? The short answer is **no**. The long answer is "no, the rest of it goes to the miner as a **mining fee**".

### Ownership on Transactions

By this point, you've seen that you need an input from which to pay your transactions, which must be yours. But, how exactly do you know which input belongs to you, and how do you convince the blockchain that it is yours?

For that, you need to use **public cryptography** to sign your data. From the previous example, we've sent 10 bitcoin to an account whose **public key** resolves to the hash `"new-owner-key-hash"`. To use those 10 coins in a future transaction, that account should fill out an input with the following data:
- **The outpoint** (txid:v_out) where the transaction is located. From our example, if the transaction resolves to the id `"1234"`, then this outpoint would be `"1234":0`, the first element in the array.
- **Their public key**. When a node hashes this key, it should match the value contained in the `"keyhash"` field. In any other case, the money is trying to be accessed by another account.
- **A signature**. This value is especially crucial, since public keys are, well, **public**. Everyone has access to public keys (i.g., Satoshi Nakamoto's), as it is required for this sort of cryptographic operations to work. With a signature, a **private** key is used on the coins or data to use as inputs, completing the equation $D_{pub}(E_{priv}(data)) = data$. No account other than the one with the private key can create this signature.

This is just one of the many ownership validation algorithms implemented by bitcoin, the peer-to-peer-key-hash ([P2PKH](https://learnmeabitcoin.com/technical/script/p2pkh/)) validation. In reality, the original transaction contains many more fields, and validation is done via a "mini-programming language" called [script](https://learnmeabitcoin.com/technical/script/).

### Mining Reward

When a miner transmits a solution through the network, **"the chain"** assigns a mining reward to it if this block is accepted. This reward is halved every 4 years, and it is $3.125$ bitcoin as of April 2025. So, how is this reward distributed? Or better yet, what prevents another node from stealing and flooding your obtained block for itself?

The answer is simple: through what is called a [coinbase transaction](https://learnmeabitcoin.com/technical/mining/coinbase-transaction/). In bitcoin, this special transaction is placed first on the list of transactions, and contains both the sum of fees and the reward. In our case, we just add it, since our transactions are stored on a **dictionary** where order is not guaranteed. This, of course, includes the **public key hash** of our miner node, which is also taken into account when you compute the **merkle tree root**. If another node were to try and overwrite our solution by changing the public key, this value would change, and the solution would have to be re-computed.

[↑ Back to Top](#blocks)  

[← Back to Bitcoin](../README.md)  

[← Back to Home](../../README.md)