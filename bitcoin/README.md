# Simple Bitcoin

Bitcoin-inspired implementation for a Proof-of-Work consensus algorithm on public blockchains. For this architecture, communication is not done following the peer-to-peer (P2P) protocol, but instead done through sockets on different processes.

[← Back to Home](../README.md)

---

## Table of Contents
- Implementation
    - [Blocks](doc/blocks.md)
    - [The Blockchain](doc/blockchain.md)
    - [Cryptographic Functions](doc/crypto.md)
    - [Miner Nodes](doc/nodes.md)
    - [Interface](doc/server.md)
- [How to Use](#how-to-use)
    - [Interface](#interface)
    - [Transaction Creator](#transaction-creator)
    - [Execution Example](#execution-example)

---

## How to Use

To play around with this application, use both of the provided scripts on different command lines:
```sh
$ bin/bitcoin-interface
$ bin/bitcoin-nodes -h <honest-miners> -s <selfish-miners> # Run in a different shell
```

Since bitcoin uses a legacy hashing algorithm, ripemd160, you may need to change your openssl configuration to enable it:
```sh
# In your command line
$ openssl version -d
$ cd <your-openssl-dir>
$ nano openssl.cnf

# Change these lines in openssl.cnf (you can use vim if you know how to exit)
openssl_conf = openssl_init

[openssl_init]
providers = provider_sect

[provider_sect]
default = default_sect
legacy = legacy_sect

[default_sect]
activate = 1

[legacy_sect]
activate = 1
```
### Interface
The main interface (`bin/bitcoin-interface`) allows you to supply commands through the command line to test the different workflows achievable by the application. The supported commands can be viewed by typing `help`, and they are as follows:
- **transaction**. This opens the transaction creation helper, the only means of sending transactions to nodes inside the network.
- **mine**. Sends a signal to all nodes to begin mining their transaction pool, votes on sent solutions and appends winning blocks to the chain. *This command blocks the main server thread until a consensus is reached.*
- **chain**. Shows a scrollable page with the contents of the entire blockchain, formatted for terminals of at least 83 pixels wide. To exit this view, press `q`. Search is supported, just like with the python *help* function.
- **integrity**. Verifies the integrity of the chain, both on the main server and every node. From this command, the longest valid chain found is retransmitted to all nodes.
- **keys**. Like the *chain* command, shows all keys currently in your possession. For readability purposes, a `ripemd160+sha256` hash of the key is shown. This same value is reflected in the chain on the *owner* field. Private/Public keypairs are sent by nodes when they join the chain, effectively granting access to every miner wallet on the chain. *On the real chain (or public cryptography), private keys should not be sent at all; they are sent here just so the user can test creating transactions*.
- **exit**. Closes the application.
- **help**. Shows this command suite.
- **clear**. Clears the screen.

The outputs for most of these commands, as well as the node responses, can be seen in the `bitcoin/logs` directory.

### Transaction Creator
This second command-line interface is accessed via the *transaction* option in the main program, which lets you create transactions to send your nodes and effectively use the blockchain. The supported commands for this mode are the following:
- **input.** Adds an input data to the transaction, where you must specify the input location (transaction id, output locaton) and ownership (which public key you want to use).
- **output.** Adds output data to the transaction, which can be either Satoshis ($10^{-8}$ BTC) or arbitrary data.
- **chain.** The *chain* command from the main interface.
- **keys.** The *keys* command from the main interface.
- **clear**. Clears the screen.
- **done**. Sends the transaction to all nodes and closes this menu.
- **help**. Shows this command suite.

Note that, even if you build an incorrect transaction, it will still be sent to the nodes, which will then decide if they want to append it to their existing pool or not. Furthermore, any amount not distributed from your selected inputs will be taken as a mining fee.

### Execution Example

Assuming the following setup, on two different terminal tabs:
```sh
$ bin/bitcoin-interface
$ bin/bitcoin-nodes -h 2 # Run in a different shell
```

This is how you would create two blocks in the chain to transfer data and some coins:

<pre><code><span style="color: #f76587;"># Create the first transaction</span>
Enter a command: <b>transaction</b>

Transaction Creator
Available keys
0: <b>&lt;keyhash-a&gt;</b>
1: <b>&lt;keyhash-b&gt;</b>

<span style="color: #65b6f7;"># Create a data output</span>
[transaction-creator] Enter a command: <b>output</b>
Select a destination key index: <b>0</b>
Enter an amount to transfer or data: <b>new york times</b>

<span style="color: #65b6f7;"># Create a data output</span>
[transaction-creator] Enter a command: <b>output</b>
Select a destination key index: <b>1</b>
Enter an amount to transfer or data: <b>times new roman</b>

<span style="color: #65b6f7;"># Send the transaction</span>
[transaction-creator] Enter a command: <b>done</b>

<span style="color: #f76587;"># Mine the first block</span>
Enter a command: <b>mine</b>

<span style="color: #f76587;"># Create the second transaction</span>
Enter a command: <b>transaction</b>

Transaction Creator
Available keys
0: <b>&lt;keyhash-a&gt;</b>
1: <b>&lt;keyhash-b&gt;</b>

<span style="color: #f76587;"># Get the coinbase transaction hash and winner key</span>
[transaction-creator] Enter a command: <b>chain</b>

<span style="color: #65b6f7;"># Get funds from a data input</span>
[transaction-creator] Enter a command: <b>input</b>
Select an origin key index: <b>0</b> (the winner)
Enter a transaction id: <b>&lt;transaction-hash&gt;</b>
Enter an output index: <b>0</b>

<span style="color: #65b6f7;"># Create a data output</span>
[transaction-creator] Enter a command: <b>output</b>
Select a destination key index: <b>0</b>
Enter an amount to transfer or data: <b>30000</b>

<span style="color: #65b6f7;"># Create a data output</span>
[transaction-creator] Enter a command: <b>output</b>
Select a destination key index: <b>1</b>
Enter an amount to transfer or data: <b>120</b>

<span style="color: #65b6f7;"># Create a data output</span>
[transaction-creator] Enter a command: <b>output</b>
Select a destination key index: <b>1</b>
Enter an amount to transfer or data: <b>you're welcome, miner</b>

<span style="color: #65b6f7;"># Send the transaction</span>
[transaction-creator] Enter a command: <b>done</b>

<span style="color: #f76587;"># Mine the second block</span>
Enter a command: <b>mine</b>

<span style="color: #f76587;"># View the resulting chain</span>
Enter a command: <b>chain</b>
</code></pre>


## Attacking the Network
To attack this project, we provide a second option in the `bin/bitcoin-nodes` script that lets you launch "selfish" or dishonest nodes. All this script does is override the block validation method on the node to mark everything it receives as invalid. Given the following example of an execution:

```bash
bin/bitcoin-interface
bin/bitcoin-nodes -h 2 -s 3 # Run in a different shell
```

No matter how many times you try to use the `mine` command, the chain will never grow. This is because the selfish pool has control of over 50% of the chain's nodes, so the "majority" consensus will always belong to them. 

[↑ Back to Top](#simple-bitcoin)  

[← Back to Home](../README.md)