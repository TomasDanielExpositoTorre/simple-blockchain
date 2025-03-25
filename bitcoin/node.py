"""
This module defines the structure and methods required for a PoW blockchain
node.
"""

from block import PoWBlock
from dataclasses import dataclass
from crypto import load_pubkey, load_signature, hash_pubkey, verify, hash_transaction
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
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
    pid: int

    def __init__(self, pub, priv, pid=1):
        """Constructor method for this class.

        Args:
            pub (rsa.RSAPrivateKey): Private Key used by this node
            priv (rsa.RSAPublicKey): Public Key used by this node
            pid (int): Optional field "pool identifier", can be used when
                launching pools to distribute the work.
        """
        self.pub = pub
        self.priv = priv
        self.pid = pid

    @property
    def last_hash(self) -> str:
        """
        Returns the hash of the last block in the chain
        """
        return self.blockchain[-1].hash if len(self.blockchain) else GENESIS_HASH

    def mine_block(self, difficulty: str):
        """
        Applies the proof-of-work operation to all current (valid) transactions,
        and transmits it to other nodes.

        Args:
            difficulty (str): Target for the PoW operation

        TODO send block, await for consensus, turn off PoW on signal
        """

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
        while int(block.hash, base=16) > target:
            block.header.nonce += self.pid

        # Add mined block to the chain after consensus has been reached
        self.add_block(block)

    def validate_block(self, message: str):
        """
        Validates a block received from other nodes and appends it to own
        blockchain after consensus has been reached.

        Args:
            message (str): json-format containing the block to validate and
                the expected difficulty.

        TODO send validation status, await for consensus
        """

        fee, total = 0, 0
        block = PoWBlock.loads(message["block"])

        # Validate block header values
        if block.header.hash_parent != self.last_hash:
            logging.error("Block parent hash is incorrect")
            return False

        if block.header.target != message["difficulty"]:
            logging.error("Block difficulty value is incorrect")
            return False

        # Validate obtained hash
        if block.target_value < int(block.hash, 16):
            logging.error("Block target was not reached")
            return False

        # Validate individual transactions
        for txid, t in block.transactions.items():
            if hash_transaction(t) != txid:
                logging.error("Transaction was tampered")
                return False

            if t.get("coinbase") and fee != 0:
                logging.error("More than one coinbase transaction present in the block")
                return False
            elif t.get("coinbase"):
                fee = t["outputs"][0]["amount"]
                continue

            if (amount := self.validate_transaction(t)) is False:
                return False

            total += amount

        if fee != (total + PoWNode.reward):
            logging.error("Reward value is incorrect")
            return False

        # Add mined block to the chain after consensus has been reached
        self.add_block(block)

    def add_block(self, block: PoWBlock):
        """
        Add a block to the chain updating all required fees

        Args:
            block (PoWBlock): Mined block.
        """
        self.blockchain.append(block)
        hashes = {hash_transaction(t): i for i, t in enumerate(self.transactions)}

        for txid, t in block.transactions.items():
            # Remove spent transactions from the utxo set
            utxo = self.utxo_set[txid]
            spent = [i["v_out"] for i in t["inputs"]]
            utxo.v_outs = [v for v in utxo.v_outs if v not in spent]

            # Remove the transaction from the pool
            if txid in hashes:
                self.transactions.pop(hashes[txid])

    def add_transaction(self, transaction: dict):
        """
        Appends a transaction to the current transaction pool.

        Args:
            transaction (dict): Blockchain transaction following the expected
            format.
        """
        if (fee := self.validate_transaction(transaction)) is False:
            return

        self.transactions.append(Transaction(data=transaction, fee=fee))

    def validate_transaction(self, transaction: dict) -> bool | int:
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

        if transaction["version"] != 1:
            logging.error("Wrong transaction version")
            return False

        for i in transaction["inputs"]:

            # Extract data from the input
            txid, out = i["tx_id"], i["v_out"]
            pub, sig = load_pubkey(i["key"]), load_signature(i["signature"])

            # Look up output in unspent set
            utxo = self.utxo_set.get(txid, None)
            if not utxo or out not in utxo.v_outs:
                logging.error(f"The outpoint {txid}:{out} is invalid")
                return False

            tx: dict = self.blockchain[utxo.block_id].transactions[txid]["outputs"][out]

            # Compare public keys
            keyhash = hash_pubkey(pub)
            if keyhash != tx["keyhash"]:
                logging.error(f"Invalid public key for outpoint {txid}:{out}")
                return False

            # Compare signature for ownership
            if not verify(pub=pub, signature=sig, data=d):
                logging.error(f"Invalid ownership for outpoint {txid}:{out}")
                return False

            # Append remainder to total fee
            if amount := tx.get("amount"):
                total += amount
                d = str(amount)
            else:
                data.append(tx["data"])
                d = tx["data"]

        # Check resulting fee and data ownership transfer
        total -= sum([t.get("amount", 0) for t in transaction["outputs"]])
        outs = [t["data"] for t in transaction["outputs"] if t.get("data")]

        if total < 0:
            logging.error(f"Invalid transaction fee: {total}")
            return False

        if len(set(data) - set(outs)) > 0:
            logging.error(f"Invalid transaction, some data is not being transfered")
            return False

        return total
