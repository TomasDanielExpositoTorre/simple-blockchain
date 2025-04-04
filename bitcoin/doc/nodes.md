# Miner Nodes

Every miner node is a member of the network. You should always consider that these miners have conflicting interests (for example, all of them want to be the "winner" that mines a block and gets the reward), and having a great number of conflicting parties in the network helps keep it balanced and fair.

Not every member of the bitcoin network is a miner. When you use a digital wallet to store your cryptocurrency (ideally, through different public keys!), your small whacky device is not doing the expensive [hashcash problem](blocks.md/#hashcash-problem-and-difficulty) that other nodes do, it just contains the private keys required to prove you own that currency.

With this approach, some of the limitations of insecure software become *slightly* less relevant for bitcoin. That is, if one mining node is compromised and accepts all transactions sent to it, every other **honest** node in the chain will just reject its solutions when an invalid transaction is found. This works as long as $51\%$ of the network remains **honest**. As for honesty, we assume this is always the case since these nodes are wasting tons of electricity (and that costs money) to solve the hashcash problem and keep running. 

[← Back to Bitcoin](../README.md)  

[← Back to Home](../../README.md)

---

## Table of Contents
- [Creating & Mining Blocks](#creating--mining-blocks)
- [Implementation Specifics](#implementation-specifics)

---

## Creating & Mining Blocks

As it was said before, miners are [selfish](blocks.md/#the-transactions) and will try to make the most profit for the least amount of work. This, along the limited block size accepted by bitcoin, means that not all transactions are selected to form part of the block at a given time.

What does this mean? That nodes will always go for the transaction with the **highest fees** first. Again, the fee for a transaction is just the leftover amounts from an input, that have not been sent to an output. In this implementation, however, transactions are added [manually](../README.md/#transaction-creator), which takes a lot of time. From this, it is unlikely that blocks will ever reach 2MB of data (you're welcome to create transactions for a couple of hours if you want), so all transactions are just appended to the block as-is. That being said, this sorting of transactions is still supported through the **Transaction** dataclass, it just isn't being used on block creation.

When a block is created, its header is mined until the expected difficulty is reached. But no miner will work more than it needs; if another miner finds a solution, one could (or could not, depending on how much you decide to trust the other miner) stop mining temporarily until a consensus is reached. This would mean a bit of lost time when a block is considered invalid, but taking electricity costs into account, that situation is unlikely.

---

## Implementation Specifics

The nodes in this implementation handle both the mining and validation process on demand. That is, instead of automatically grouping transactions, mining headers and validating received blocks, they handle all of these operations through commands received from a [main server](server.md). 

A node executes like a python script (see: bin/bitcoin-nodes) as a separate process. The process connects to the port the server is in (usually, a hardcoded 65432) and constantly listens for petitions. There are a total of six petition types it listens to:
* **transaction.** Validates and appends a transaction received from the server. Even if the server may allow the construction of an incorrect [transaction](../README.md/#transaction-creator), the node would not append such a transaction to its pool.
* **mine.** Ceates a new thread to mine a block with all the transactions in the pool. This also lets you create a block with empty transactions (for example, to have some bitcoin available to spend). Since a new thread is created, events need to be used for communication (if another solution is found while mining).
* **verify.** Votes on a sent solution (by [validating the block](blockchain.md/#validating-a-block)), which also implies stopping the mining process.
* **veredict.** Takes action depending on the reached consensus. If the block is accepted, it gets appended to the chain and the miner thread is stopped. If the block is instead rejected, the mining continues.
* **chain.** This indicates that a blockchain has been sent to the node, which happens either when first joining the network or when validating the integrity of a chain. A node needs not accept the new chain unless its the longest valid chain. In the off-case the node's chain is actually larger, it is instead propagated through the network as a candidate for the new chain.
* **keys.** Sends the node's public+private keypair to the main server. The public key gives you an address to move bitcoin to. The private key essentially gives you access to the miner's wallet in bitcoin, if you want to test moving currency earned by mining.
* **close_connection.** Message sent by the server for a graceful shutdown

[↑ Back to Top](#miner-nodes)  

[← Back to Bitcoin](../README.md)  

[← Back to Home](../../README.md)