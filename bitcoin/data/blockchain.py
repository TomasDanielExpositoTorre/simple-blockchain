import hashlib
import datetime
import json
from dataclasses import asdict, dataclass
from crypto import hash_transaction
from block import PoWBlock

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
    utxo_set: dict[str, UTXO]

    @property
    def last_hash(self) -> str:
        """
        Returns the hash of the last block in the chain
        """
        return self.blocks[-1].hash if len(self.blocks) else GENESIS_HASH

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
            if t.get("coinbase"):
                t.pop("coinbase")
                continue

            # Update utxo set with new transaction outputs
            if len(t.get("outputs", [])):
                utxo[txid] = list(range(t["outputs"]))

            # Store all spent transactions
            for i in t.get("inputs"):
                spent.setdefault(i["tx_id"], []).append(t["v_out"])

            # Remove the transaction from the pool
            if txid in hashes:
                transactions.pop(hashes[txid])

        # Remove spent transactions from utxo set
        for txid, vouts in spent.items():
            if utxo_set.get(txid):
                utxo_set[txid] = list(set(utxo_set[txid]) - set(vouts))

        return transactions
