# The Server

This component does not exist on bitcoin. This is just an interface provided to control the process of creating, viewing, and moving data around blocks. It should by all means just be taken as a virtual component, and any vulnerability found in it should not be taken as a vulnerability in bitcoin itself.

## Architecture

The server consists of two threads. The first thread, the daemon, handles all connections to the different nodes. The main loopback function listents for all incoming connections, and for each node connected, a new thread is created to maintain this connection.

This way, the daemon listens to the following messages from the nodes:
* **solution.** Appends a found solution to the list of candidates. This begins the voting process, where no more solutions are accepted and nodes vote on received blocks based on a FCFS (First-come, First-served) basis.  
* **verify.** Registers a node's vote on a sent solution. It will stop early once a consensus is reached, even if not every node has voted.
* **chain.** Validates a chain sent from another node. In the case that this new chain is valid and longer, it will also propagate it to all connected nodes.
* **keys.** Receives a keypair sent by a node.

The second thread, the user [interface](../README.md#interface), extends the original **InterfaceDaemon** class to accept commands through the command-line.

Both services are mostly independent from one another, except when it comes to mining. Once again, thread communication is managed through events and locks, and this process defines three states:
- **IDLE.** Does not accept any solutions or votes until the user writes the *mine* command in the interface.
- **VOTING STARTED.** Does not accept any votes until the first solution has been received and retransmited by the server.
- **VOTING OVER.** The server waits until all nodes vote or a consensus (over $50\%$ validation) has been reached. Based on the results of this vote, the server will either send the new validated block, try the next solution, or allow the mining process to begin again since a solution was not found.

[↑ Back to Top](#the-server)  

[← Back to Bitcoin](../README.md)  

[← Back to Home](../../README.md)