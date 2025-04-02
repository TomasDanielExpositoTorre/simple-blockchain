"""
This module defines the structure and methods required for a PoW blockchain
node.
"""

import logging
import threading
import socket
import json
import datetime
import sys
from dataclasses import dataclass
from bitcoin.data import crypto
from bitcoin.data.blockchain import Blockchain
from bitcoin.data.block import PoWBlock

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(
            f"bitcoin/logs/node-{datetime.datetime.now()}.log", mode="w"
        ),
    ],
)


@dataclass
class Transaction:
    """
    Dataclass representation of a transaction that has been validated by
    a node and added to its mining pool.

    Transactions can be sorted by their computed fee in descending order, so
    that if there is a block limit only the most profitable transactions will
    be appended to the block.
    """

    data: dict
    fee: int

    def __lt__(self, other: "Transaction") -> bool:
        """
        Defines the sorting criteria for transactions

        Args:
            other (Transaction): Transaction to compare to

        """
        return self.fee > other.fee


class PoWNode:
    """
    Class representing a node in the blockchain, which can both apply the
    proof-of-work operation and validate mined blocks.
    """

    blockchain = Blockchain(blocks=[])
    pool: list[Transaction] = []

    def __init__(self, pub, priv):
        """Constructor method for this class.

        Args:
            pub (rsa.RSAPrivateKey): Private Key used by this node
            priv (rsa.RSAPublicKey): Public Key used by this node
        """
        # Cryptography data
        self.pub = pub
        self.priv = priv

        # Network data
        self.conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        # Threading data
        self.lock = threading.Lock()
        self.mining_signal = threading.Event()
        self.solution_found = False

    ###########################################################################
    # -                      METHODS, GETTERS & SETTERS-                     -#
    ###########################################################################

    def get_solution(self) -> bool:
        """
        Thread-safe wrapper to check if a solution has been found in the chain.

        Return:
            bool: Solution found status.
        """
        with self.lock:
            sol = self.solution_found
        return sol

    def set_solution(self, value: bool):
        """
        Thread-safe wrapper to set if a solution has been found in the chain

        Args:
            value (bool): Setter value.
        """
        with self.lock:
            self.solution_found = value

    def send(self, data: dict):
        """
        Thread-safe sendall wrapper.

        Args:
            data (dict): Data to send.
        """
        with self.lock:
            self.conn.sendall(json.dumps(data).encode())

    ###########################################################################
    # -                           CALLBACK METHODS                           -#
    ###########################################################################

    def mine_block(self, difficulty: str):
        """
        Applies the proof-of-work operation to all current (valid) transactions,
        and transmits it to other nodes.

        Args:
            difficulty (str): Target for the PoW operation
        """
        found = False

        # Compute the mining fee and add it as the coinbase transaction
        fee = sum(t.fee for t in self.pool) + Blockchain.reward
        self.pool.append(
            Transaction(
                data={
                    "outputs": [
                        {"amount": fee, "keyhash": crypto.hash_pubkey(self.pub)}
                    ],
                    "coinbase": True,
                },
                fee=0,
            )
        )

        # Create the block from transaction pool (no sorting or limiting)
        block = PoWBlock(
            transactions=[t.data for t in self.pool],
            parent=self.blockchain.last_hash,
            target=difficulty,
        )
        target = block.target_value

        # Apply the Proof-of-Work
        while not found:

            # Hashcash
            if int(block.hash, base=16) <= target:
                # Send found solution
                self.send({"type": "solution", "block": PoWBlock.dumps(block)})
                logging.debug("Solution found! %s", PoWBlock.dumps(block))
                found = True

            # Halt mining when another node finds the solution
            if not found and self.get_solution():
                logging.debug("Solution found by another node")
                self.mining_signal.wait()
                self.mining_signal.clear()
                found = self.get_solution()

            block.header.nonce += 1

        logging.debug("Solution confirmed, exiting")
        self.pool.pop()
        sys.exit()

    def add_transaction(self, transaction: dict):
        """
        Appends a transaction to the current transaction pool.

        Args:
            transaction (dict): Blockchain transaction following the expected
            format.
        """
        if (fee := self.blockchain.validate_transaction(transaction)) is False:
            return

        logging.debug("Adding transaction %s to the block!", transaction)

        self.pool.append(Transaction(data=transaction, fee=fee))

    ###########################################################################
    # -                             MAIN PROGRAM                             -#
    ###########################################################################

    def run(self):
        """
        Main routine for this class. Attempts a connection to the main server
        and handles all events sent by it.
        """
        disconnected = False

        self.conn.connect(("localhost", 65432))
        logging.info("Connected to master.")

        while not disconnected:

            # Obtain data from master
            data = self.conn.recv(1024**2)
            message = json.loads(data.decode())

            match message.get("type").lower():
                # Add a transaction to the chain (blocking)
                case "transaction":
                    logging.debug(
                        "Incoming transaction from master: %s", message["transaction"]
                    )
                    self.add_transaction(transaction=message["transaction"])

                # Mine current transactions (non-blocking)
                case "mine":
                    logging.debug(
                        "Beginning mining operation with transactions: %s", self.pool
                    )
                    self.mining_signal.clear()
                    self.set_solution(False)
                    threading.Thread(
                        target=self.mine_block, args=(message["difficulty"],)
                    ).start()

                # Vote on solution (blocking)
                case "verify":
                    self.set_solution(True)
                    valid = self.blockchain.validate_block(
                        block=PoWBlock.loads(message["block"]),
                        difficulty=message["difficulty"],
                        last_hash=self.blockchain.last_hash,
                    )
                    logging.debug("Vote on sent solution: %s", valid)

                    self.send({"type": "verify", "vote": 1 if valid else 0})

                # Handle consensus response (blocking)
                case "veredict":
                    logging.debug("Received verdict: %s", message)

                    # Append block and tell miner to stop
                    if message.get("block"):
                        trs = {
                            crypto.hash_transaction(t.data): t.fee for t in self.pool
                        }

                        new_pool = self.blockchain.add_block(
                            PoWBlock.loads(message.get("block")),
                            transactions=[t.data for t in self.pool],
                        )

                        self.pool = [
                            Transaction(data=t, fee=trs[crypto.hash_transaction(t)])
                            for t in new_pool
                        ]

                        self.mining_signal.set()

                    # Consensus was not reached, continue mining
                    elif message.get("final"):
                        self.set_solution(False)
                        self.mining_signal.set()

                # Compare received blockchain with own
                case "chain":
                    blockchain = Blockchain(
                        blocks=[PoWBlock.loads(b) for b in message["blockchain"]]
                    )

                    logging.debug("Validating blockchain obtained from master")
                    new = blockchain.validate_chain()

                    logging.debug("Validating own blockchain")
                    old = self.blockchain.validate_chain()

                    # Override caller's chain
                    if len(blockchain) < len(self.blockchain) and old:
                        logging.debug("Previous chain is longer, sending to master")
                        self.send(
                            {"type": "chain", "blockchain": self.blockchain.serialize()}
                        )

                    # Override own chain
                    elif (len(blockchain) > len(self.blockchain) and new) or (
                        new and not old
                    ):
                        logging.debug("New chain is longer, overriding")
                        with self.lock:
                            self.blockchain = blockchain

                # Share keys with master
                case "keys":
                    self.send(
                        {
                            "type": "keys",
                            "priv": crypto.dump_privkey(self.priv),
                            "pub": crypto.dump_pubkey(self.pub),
                        }
                    )

                # Close connection and exit gracefully
                case "close_connection":
                    logging.debug("Master disconnection received")
                    disconnected = True

                case _:
                    logging.debug("Message type not recognized")


privkey, pubkey = crypto.create_keypair()
node = PoWNode(pubkey, privkey)

try:
    node.run()
except Exception as e:
    logging.error("Error: %s", e)

node.conn.close()
