"""
This module defines the structure and methods required for a PoW blockchain
node.
"""

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


GENESIS_HASH = "0000000000000000000000000000000000000000000000000000000000000000"


@dataclass
class UTXO:
    """
    Dataclass representation for the set of "unspent" out transactions in
    the blockchain. Entries should be added or removed only after a block
    is added in the blockchain.
    """

    v_outs: list[int]
    block_id: int


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

    blockchain: list[PoWBlock] = []
    utxo_set: dict[str, UTXO] = {}
    transactions: list[Transaction] = []
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

    @property
    def last_hash(self) -> str:
        """
        Returns the hash of the last block in the chain
        """
        return self.blockchain[-1].hash if len(self.blockchain) else GENESIS_HASH

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

    def _validate_transaction(self, transaction: dict) -> bool | int:
        """
        Validates the integrity of a transaction, used either when adding
        transactions to the node pool, or during the validation step after
        a block has been found.

        This method should not be called to validate the coinbase transaction
        appended by the winning miner.

        Args:
            transaction (dict): Blockchain transaction following the expected
            format.

        Returns:
            False on an invalid transaction, or the resulting fee otherwise.
        """
        total = 0
        data = []
        inpairs = []

        if transaction["version"] != 1:
            logging.debug(
                "Wrong transaction version"
                + f"\n\texpected: 1"
                + f"\n\tgot: {transaction['version']}"
            )
            return False

        for i in transaction["inputs"]:

            # Extract data from the input
            txid, out = i["tx_id"], i["v_out"]
            pub, sig = load_pubkey(i["key"]), load_signature(i["signature"])
            outpoint = f"{txid}:{out}"

            # Look up output in unspent set
            if outpoint in inpairs:
                logging.debug(f"The outpoint {outpoint} was spent twice")
                return False
            inpairs.append(outpoint)

            utxo = self.utxo_set.get(txid, None)
            if not utxo or out not in utxo.v_outs:
                logging.debug(f"The outpoint {outpoint} is invalid")
                return False

            tx: dict = self.blockchain[utxo.block_id].transactions[txid]["outputs"][out]

            # Compare public keys
            keyhash = hash_pubkey(pub)
            if keyhash != tx["keyhash"]:
                logging.debug(f"Invalid public key for outpoint {outpoint}")
                return False

            # Append remainder to total fee
            if amount := tx.get("amount"):
                total += amount
                d = str(amount)
            else:
                data.append(tx["data"])
                d = tx["data"]

            # Compare signature for ownership
            if not verify(pub=pub, signature=sig, data=d):
                logging.debug(f"Invalid ownership for outpoint {outpoint}")
                return False

        # Check resulting fee and p ownership transfer
        total -= sum([t.get("amount", 0) for t in transaction["outputs"]])
        outs = [t["data"] for t in transaction["outputs"] if t.get("data")]

        if total < 0:
            logging.debug(f"Invalid transaction fee: {total}")
            return False

        if len(set(data) - set(outs)) > 0:
            logging.debug(f"Invalid transaction, some input data is not being transfered as outputs")
            return False

        return total

    def _add_block(self, block: PoWBlock):
        """
        Add a block to the chain updating all required fees

        Args:
            block (PoWBlock): Mined block.
        """
        self.blockchain.append(block)
        hashes = {hash_transaction(t): i for i, t in enumerate(self.transactions)}

        for txid, t in block.transactions.items():
            if t.get("coinbase"):
                t.pop("coinbase")
                continue

            # Remove spent transactions from the utxo set
            utxo = self.utxo_set[txid]
            spent = [i["v_out"] for i in t["inputs"]]
            utxo.v_outs = [v for v in utxo.v_outs if v not in spent]

            # Remove the transaction from the pool
            if txid in hashes:
                self.transactions.pop(hashes[txid])

    def mine_block(self, difficulty: str):
        """
        Applies the proof-of-work operation to all current (valid) transactions,
        and transmits it to other nodes.

        Args:
            difficulty (str): Target for the PoW operation
        """
        found = False
        # Compute the mining fee and add it as the coinbase transaction
        fee = sum([t.fee for t in self.transactions]) + PoWNode.reward
        self.transactions.append(
            {
                "outputs": [
                    {"amount": fee, "keyhash": hash_pubkey(self.pub)},
                ],
                "coinbase": True,
            }
        )

        # Create the block and do the Proof-of-Work
        block = PoWBlock(
            transactions=self.transactions, parent=self.last_hash, target=difficulty
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
                    self.transactions.pop(-1)
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
                self.transactions.pop(-1)
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
        if block.header.hash_parent != self.last_hash:
            logging.debug(
                "Block parent hash is incorrect"
                + f"\n\texpected:{self.last_hash}"
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

            if (amount := self._validate_transaction(t)) is False:
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
        if (fee := self._validate_transaction(transaction)) is False:
            return

        logging.debug(f"Adding transaction {transaction} to the block!")

        self.transactions.append(Transaction(data=transaction, fee=fee))

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
                            f"Beginning mining operation with transactions: {self.transactions}"
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
                            self._add_block(PoWBlock.loads(message.get("block")))
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
