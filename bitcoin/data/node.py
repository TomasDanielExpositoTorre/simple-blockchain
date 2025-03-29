"""
This module defines the structure and methods required for a PoW blockchain
node.
"""

from blockchain import Blockchain
from block import PoWBlock
from dataclasses import dataclass
from crypto import (
    load_pubkey,
    load_signature,
    hash_pubkey,
    verify,
    hash_transaction,
    create_keypair,
)
import logging
import threading
import socket
import json
import datetime

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(f"./logs/node-{datetime.datetime.now()}.log", mode="w"),
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

    blockchain = Blockchain(blocks=[], utxo_set={})
    pool: list[Transaction] = []
    reward: float = 3.125

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
        self.bufsize = 1024**2
        self.conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        # Threading data
        self.lock = threading.Lock()
        self.mining_signal = threading.Event()
        self.solution_found = False

    ###########################################################################
    # -                     PROPERTIES, GETTERS & SETTERS                    -#
    ###########################################################################

    def get_solution(self) -> bool:
        """
        Thread-safe wrapper to check if a solution has been found in the chain
        """
        self.lock.acquire()
        sol = self.solution_found
        self.lock.release()
        return sol

    def set_solution(self, value):
        """
        Thread-safe wrapper to set if a solution has been found in the chain
        """
        self.lock.acquire()
        self.solution_found = value
        self.lock.release()

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
        fee = sum([t.fee for t in self.pool]) + PoWNode.reward
        self.pool.append(
            Transaction(
                data={
                    "outputs": [
                        {"amount": fee, "keyhash": hash_pubkey(self.pub)},
                    ],
                    "coinbase": True,
                },
                fee=0,
            )
        )

        # Create the block and do the Proof-of-Work
        block = PoWBlock(
            transactions=[t.data for t in self.pool],
            parent=self.blockchain.last_hash,
            target=difficulty,
        )
        target = block.target_value

        while True:
            # Halt mining when another node finds the solution
            if self.get_solution():
                logging.debug("Solution found by another node")
                self.mining_signal.wait()
                self.mining_signal.clear()
                if self.get_solution():
                    logging.debug("Solution confirmed, exiting")
                    self.pool.pop(-1)
                    exit()

            # Hashcash PoW
            if int(block.hash, base=16) <= target:
                # Send found solution
                self.conn.sendall(
                    json.dumps(
                        {"type": "solution", "block": PoWBlock.dumps(block)}
                    ).encode()
                )
                logging.debug(f"Solution found! {PoWBlock.dumps(block)}")
                self.pool.pop(-1)
                exit()

            block.header.nonce += 1

    def verify_block(self, message: str):
        """
        Validates a block received from other nodes and appends it to own
        blockchain after consensus has been reached.

        Args:
            message (str): json-format containing the block to validate and
                the expected difficulty.
        """

        fee, total = 0, 0

        block = PoWBlock.loads(message["block"])

        # Validate block header values
        if block.header.hash_parent != self.blockchain.last_hash:
            logging.debug(
                "Block parent hash is incorrect"
                + f"\n\texpected:{self.blockchain.last_hash}"
                + f"\n\tgot: {block.header.hash_parent}"
            )
            return False

        if block.header.target != message["difficulty"]:
            logging.debug(
                "Block difficulty value is incorrect"
                + f"\n\texpected:{message['difficulty']}"
                + f"\n\tgot: {block.header.target}"
            )

            return False

        # Validate obtained hash
        if block.target_value < int(block.hash, 16):
            logging.debug(
                "Block target was not reached"
                + f"\n\texpected:{block.target_value}"
                + f"\n\tgot: {int(block.hash, 16)}"
            )
            return False

        # Validate individual transactions
        for txid, t in block.transactions.items():
            if hash_transaction(t) != txid:
                logging.debug(
                    "Transaction was tampered"
                    + f"\n\texpected hash:{txid}"
                    + f"\n\tgot: {hash_transaction(t)}"
                )
                return False

            if t.get("coinbase") and fee != 0:
                logging.debug("More than one coinbase transaction present in the block")
                return False
            elif t.get("coinbase"):
                fee = t["outputs"][0]["amount"]
                continue

            if (amount := self.blockchain.validate_transaction(t)) is False:
                return False

            total += amount

        if fee != (total + PoWNode.reward):
            logging.debug(
                "Reward value is incorrect"
                + f"\n\texpected:{total + PoWNode.reward}"
                + f"\n\tgot: {fee}"
            )
            return False

        logging.debug(f"Received block {message['block']} is valid!")
        return True

    def add_transaction(self, transaction: dict):
        """
        Appends a transaction to the current transaction pool.

        Args:
            transaction (dict): Blockchain transaction following the expected
            format.
        """
        if (fee := self.blockchain.validate_transaction(transaction)) is False:
            return

        logging.debug(f"Adding transaction {transaction} to the block!")

        self.transactions.append(Transaction(data=transaction, fee=fee))

    ###########################################################################
    # -                             MAIN PROGRAM                             -#
    ###########################################################################

    def run(self):
        """
        Main routine for this class. Attempts a connection to the main server
        and handles all events sent by it.
        """
        disconnected = False

        try:
            self.conn.connect(("localhost", 65432))
            logging.info("Connected to master.")

            while not disconnected:

                # Obtain data from master
                data = self.conn.recv(self.bufsize)
                message = json.loads(data.decode())

                match message.get("type"):
                    # Add a transaction to the chain (blocking)
                    case "transaction":
                        logging.debug(
                            f"Incoming transaction from master: {message['transaction']}"
                        )
                        self.add_transaction(
                            transaction=json.loads(message["transaction"])
                        )

                    # Mine current transactions (non-blocking)
                    case "mine":
                        logging.debug(
                            f"Beginning mining operation with transactions: {self.pool}"
                        )
                        self.mining_signal.clear()
                        self.set_solution(False)
                        threading.Thread(
                            target=self.mine_block, args=(message["difficulty"],)
                        ).start()

                    # Vote on solution (blocking)
                    case "verify":
                        self.set_solution(True)
                        valid = self.verify_block(message=message)
                        logging.debug(f"Vote on sent solution: {valid}")

                        self.conn.sendall(
                            json.dumps(
                                {"type": "verify", "vote": 1 if valid else 0}
                            ).encode()
                        )

                    # Add voted block (blocking)
                    case "veredict":
                        logging.debug(f"Received veredict: {message}")
                        # Append block and tell miner to stop
                        if message.get("block"):
                            trs = {hash_transaction(t.data) : t.fee for t in self.pool}

                            new_pool = self.blockchain.add_block(
                                PoWBlock.loads(message.get("block")),
                                transactions=[t.data for t in self.pool],
                            )

                            self.pool = [Transaction(data=t, fee=trs[hash_transaction(t)]) for t in new_pool]
                            self.mining_signal.set()

                        # Consensus was not reached, continue mining
                        elif message.get("final"):
                            self.set_solution(False)
                            self.mining_signal.set()

                    case "close_connection":
                        logging.debug(f"Master disconnection received")
                        disconnected = True
                    case _:
                        logging.debug(f"Message type not recognized")
        except Exception as e:
            logging.error(f"Error: {e}")

        self.conn.close()


priv, pub = create_keypair()
node = PoWNode(pub, priv)
node.run()
