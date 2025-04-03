# Simple Bitcoin

Bitcoin-inspired implementation for a Proof-of-Work consensus algorithm on public blockchains. 

## Table of Contents


## How to Use

To play around with this application, use both of the provided scripts on different command lines:
```sh
$ bin/bitcoin-interface
$ bin/bitcoin-nodes -n <number-of-miners>
```

### Interface
The main interface (`bin/bitcoin-interface`) allows you to supply commands through the command line to test the different workflows achievable by the application. The supported commands can be viewed by typing `help`, and they are as follows:
- **transaction**. This opens the transaction creation helper, the only means of sending transactions to nodes inside the network.
- **mine**. Sends a signal to all nodes to begin mining their transaction pool, votes on sent solutions and appends winning blocks to the chain. *This command blocks the main server thread until a consensus is reached.*
- **visualize chain**. Shows a scrollable page with the contents of the entire blockchain, formatted for terminals of at least 83 pixels wide. To exit this view, press `q`. Search is supported, just like with the python *help* function.
- **integrity**. Verifies the integrity of the chain, both on the main server and every node. From this command, the longest valid chain found is retransmitted to all nodes.
- **acquire keys**. Obtains the private-public keypair for every node in the network. This effectively gives access to every miner wallet on the chain. *On the real chain (or public cryptography), private keys should not be sent at all; they are sent here just so the user can test creating transactions*.
- **visualize keys**. Like the *visualize chain* command, shows all keys currently in your possession. For readability purposes, a `ripemd160+sha256` hash of the key is shown. This same value is reflected in the chain on the *owner* field.
- **help**. Shows this command suite.
- **clear**. Clears the screen.
- **exit**. Closes the application.

The outputs for most of these commands, as well as the node responses, can be seen in the `bitcoin/logs` directory.

### Transaction Creator
This second command-line interface is accessed via the *transaction* option in the main program, which lets you create transactions to send your nodes and effectively use the blockchain. The supported commands for this mode are the following:
- **input.** Adds an input data to the transaction, where you must specify the input location (transaction id, output locaton) and ownership (which public key you want to use).
- **outputs.** Adds output data to the transaction, which can be either Satoshis ($10^{-9}$ BTC) or arbitrary data.
- **chain.** The *visualize chain* command from the main interface.
- **keys.** The *visualize keys* command from the main interface.

Note that, even if you build an incorrect transaction, it will still be sent to the nodes, which will then decide if they want to append it to their existing pool or not. Furthermore, any amount not distributed from your selected inputs will be taken as a mining fee.

### Execution Example

Assuming the following setup, on two different terminal tabs:
```sh
$ bin/bitcoin-interface
$ bin/bitcoin-nodes -n 2
```

This is how you would create two blocks in the chain to transfer data and some coins:

<pre><code>
<span style="color: #f76587;"># Get keys to transfer data</span>
Enter a command: <b>acquire keys</b>

<span style="color: #f76587;"># Create the first transaction</span>
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

<span style="color: #65b6f7;"># Create a first data output</span>
[transaction-creator] Enter a command: <b>input</b>
Select an origin key index: <b>0</b> (the winner)
Enter a transaction id: <b>&lt;transaction-hash&gt;</b>
Enter an output index: <b>0</b>

<span style="color: #65b6f7;"># Create a data output</span>
[transaction-creator] Enter a command: <b>output</b>
Select a destination key index: <b>0</b>
Enter an amount to transfer or data: <b>3</b>


<span style="color: #65b6f7;"># Create a data output</span>
[transaction-creator] Enter a command: <b>output</b>
Select a destination key index: <b>1</b>
Enter an amount to transfer or data: <b>0.125</b>

<span style="color: #65b6f7;"># Create a data output</span>
[transaction-creator] Enter a command: <b>output</b>
Select a destination key index: <b>1</b>
Enter an amount to transfer or data: <b>you're welcome</b>

<span style="color: #65b6f7;"># Send the transaction</span>
[transaction-creator] Enter a command: <b>done</b>

<span style="color: #f76587;"># Mine the second block</span>
Enter a command: <b>mine</b>

<span style="color: #f76587;"># View the resulting chain</span>
Enter a command: <b>visualize chain</b>
</code></pre>