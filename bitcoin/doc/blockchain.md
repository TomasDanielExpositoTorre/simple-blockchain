# Blockchain

The blockchain is the composition of all blocks and the core of bitcoin (and, of course, the core of blockchains). There is no "true blockchain" that all of the nodes are subscribed to, instead, the longest **valid** chain is taken as a single source of truth, even if it may not be. This problem assumes all nodes have different interests, and so an immense amount of computational power, electricity, time and money is required to rewrite a valid blockchain.

[← Back to Bitcoin](../README.md)  

[← Back to Home](../../README.md)

---

## Table of Contents
- [Validating Data](#validating-data)
    - [Transactions](#validating-a-transaction)
    - [Blocks](#validating-a-block)
    - [The Blockchain](#validating-the-blockchain)
- [Accessing Data](#accessing-data)

---

## Validating Data

In blockchain, there are three key elements that need to be valid at all times: **transactions**, **blocks** and **the chain itself**. Given the nature of these operations, and their dependance on every chain, we have grouped all of them together in one python module.

### Validating a Transaction

As mentioned [before](blocks.md/#the-transactions), transactions are composed of inputs and outputs from which bitcoin is moved around. One cannot assume that all information sent by an account is valid, as the idea of using another account's bitcoin is a very tempting concept.  

Therefore, validating transaction inputs should take a number of factors into account:
- All input information must be valid.
- Only the owner may spend that input.
- No inputs may be spent twice.

Conversely, outputs must be properly checked, so that no bitcoin leakage or printing is happening:
- The sum of bitcoin generated from outputs must not exceed the provided inputs.
- Outputs may be generated multiple times, if the input amount allows for it.
- There cannot be more than one coinbase transaction per block.
- The coinbase transaction reward and fee must match the expected values.

In reality, a node may not check any of these conditions, and it should not be "forced" to. This would not be a vulnerability in the code, but rather a malicious node attempting to alter the behavior of the chain in some way. As long as over 50% of the network remains "honest", there are no issues with this validation.

### Validating a Block

As for the mined block itself, there is additional criteria required to validate it when compared to transactions. Of course, every transaction in a block must be valid (this is checked by all nodes), but the block itself needs to prove it was mined at a certain point in time.

By this, we do not mean that the timestamp has to be "current", but that the block itself should continue the chain in some way. This "some way" is by proving **the last block in the chain came right before it**. In reality, this is just filling the **Parent Hash** field in the header with the hash of the previous block. The [first block](https://www.blockchain.com/explorer/blocks/btc/000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f), mined by Sakamoto himself, does not have a parent hash (obviously). This is known as the **Genesis Block**, where the hash of the parent is just 0.

Other than validating the transactions (+ coinbase) and parent information, one must also check that the block hash matches the expected difficulty **target**. When all of this has been checked, the block is appended to the chain and all of its transactions are removed from a miner's pool.

This last factor can make what is known as a *double spending* attack. If two valid blocks appear at the same time, the chain is partitioned (both solutions are accepted, creating *parallel "universes"*) until a new solution is found for either block. When this conflict is eventually solved (*one "universe" is destroyed, no infinity stones required*), the block that becomes invalid has its transactions lost. That also includes the **coinbase transaction**, which means the node that mined it also loses its bitcoin.

### Validating the Blockchain

Validating the chain itself, is, surprisingly, the easiest of the three algorithms, while also the most complex. To validate it, you must validate every single block. That's it.

---

## Accessing Data

In bitcoin, when a transaction attempts to access one input, the chain is iteratively traversed to find the corresponding outpoin and whether it had been spent. To simplify this process, we store a *set of unspent transactions*, which is updated as blocks are added to the chain. 

With this approach, the only time this set is re-built is on chain validation, which makes it both easier to send this information to new nodes (as less data is sent) and more difficult to spread incorrect sets through the network as it must be computed every time. At the same time, for this simple example, it allows us to find unspent outputs and validate transactions faster.

[↑ Back to Top](#blockchain)  

[← Back to Bitcoin](../README.md)  

[← Back to Home](../../README.md)