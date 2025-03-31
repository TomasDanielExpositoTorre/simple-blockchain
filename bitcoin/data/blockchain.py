import hashlib
import datetime
import json
from dataclasses import asdict, dataclass, field
from crypto import hash_transaction
from block import PoWBlock
import logging

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
class Blockchain:
    blocks: list[PoWBlock]
    utxo_set: dict[str, UTXO] = field(default_factory=dict)
    reward: int = 3.125

    @property
    def last_hash(self) -> str:
        """
        Returns the hash of the last block in the chain
        """
        return self.blocks[-1].hash if len(self.blocks) else GENESIS_HASH

    def add_block(self, block: PoWBlock, transactions: list[dict]):
        """
        Add a block to the chain updating all required fees

        Args:
            block (PoWBlock): Mined block.
        """
        self.blocks.append(block)

        hashes = {hash_transaction(t): i for i, t in enumerate(transactions)}
        spent = dict()

        for txid, t in block.transactions.items():
            # Coinbase transaction, not in the pool and has no inputs
            if t.get("coinbase"):
                t.pop("coinbase")
                continue

            # Store all spent transactions
            for i in t.get("inputs"):
                spent.setdefault(i["tx_id"], []).append(t["v_out"])

            # Remove the transaction from the pool
            if txid in hashes:
                transactions.pop(hashes[txid])

        # Remove spent transactions inputs from utxo set
        for txid, vouts in spent.items():
            if self.utxo_set.get(txid):
                self.utxo_set[txid] = list(set(utxo_set[txid]) - set(vouts))

        # Add transaction outputs to the uxto set
        for txid, vouts in block.outpoints.items():
            self.utxo_set[txid] = vouts

        return transactions

    def validate_transaction(self, transaction: dict) -> bool | int:
        """
        Validates the integrity of a transaction, used either when adding
        transactions to the pool, or during the validation step after
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

            tx: dict = self.blocks[utxo.block_id].transactions[txid]["outputs"][out]

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
            logging.debug(
                f"Invalid transaction, some input data is not being transfered as outputs"
            )
            return False

        return total

    def validate_block(self, block: PoWBlock, difficulty: str, last_hash: str):
        """
        Validates a block received from other nodes and appends it to own
        blockchain after consensus has been reached.

        Args:
            message (str): json-format containing the block to validate and
                the expected difficulty.
        """

        fee, total = 0, 0

        # Validate block header values
        if block.header.hash_parent != last_hash:
            logging.debug(
                "Block parent hash is incorrect"
                + f"\n\texpected:{last_hash}"
                + f"\n\tgot: {block.header.hash_parent}"
            )
            return False

        if block.header.target != difficulty:
            logging.debug(
                "Block difficulty value is incorrect"
                + f"\n\texpected:{difficulty}"
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

        if fee != (total + Blockchain.reward):
            logging.debug(
                "Reward value is incorrect"
                + f"\n\texpected:{total + Blockchain.reward}"
                + f"\n\tgot: {fee}"
            )
            return False

        logging.debug(f"Block {PoWBlock.dumps(block)} is valid!")
        return True

    def is_valid(self) -> bool:
        """
        Verifies the integrity of the chain and rewrites the utxo chain.
        """

        if not len(self.blocks):
            return True

        # Genesis block validation
        with self.blocks[0] as genesis_block:
            self.validate_block(
                block=genesis_block,
                difficulty=genesis_block.header.target,
                last_hash=GENESIS_HASH,
            )
            for txid, vouts in genesis_block.outpoints.keys():
                self.utxo_set[txid] = vouts

        # Individual block validation
        for i, block in enumerate(self.blocks, start=1):
            if not self.validate_block(
                block=block,
                difficulty=block.header.target,
                last_hash=self.blocks[i - 1].hash,
            ):
                return False

            spent = {
                i["tx_id"]: spent.setdefault(i["tx_id"], []).append(t["v_out"])
                for t in block.transactions.values()
                for i in t.get("inputs")
            }

            # Remove spent transactions inputs from utxo set
            for txid, vouts in spent.items():
                if self.utxo_set.get(txid):
                    self.utxo_set[txid] = list(set(utxo_set[txid]) - set(vouts))

            # Add transaction outputs to the uxto set
            for txid, vouts in block.outpoints.keys():
                self.utxo_set[txid] = vouts

        logging.info("All blockchain transactions are valid!")

        return True
