import hashlib
import datetime
import json
from dataclasses import asdict, dataclass, field
import bitcoin.data.crypto as crypto
from bitcoin.data.block import PoWBlock
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

    def __len__(self) -> int:
        return len(self.blocks)

    @property
    def last_hash(self) -> str:
        """
        Returns the hash of the last block in the chain
        """
        return self.blocks[-1].hash if len(self.blocks) else GENESIS_HASH

    def get_input(self, txid, v_out):
        if not self.utxo_set.get(txid):
            logging.error(f"Invalid transaction identifier: {txid}")
            return None

        utxo = self.utxo_set[txid]
        if v_out not in utxo.v_outs:
            logging.error(
                f"Invalid transaction outpoint:\n"
                + f"got: {v_out}\n"
                + f"expected: {utxo.v_outs}\n"
            )
            return None

        txo = self.blocks[utxo.block_id].transactions[txid]["outputs"][v_out]
        return txo.get("amount", txo.get("data"))

    def serialize(self) -> list[str]:
        return [PoWBlock.dumps(block) for block in self.blocks]

    def add_block(self, block: PoWBlock, transactions: list[dict]):
        """
        Add a block to the chain updating all required fees

        Args:
            block (PoWBlock): Mined block.
        """
        self.blocks.append(block)

        hashes = {crypto.hash_transaction(t): i for i, t in enumerate(transactions)}
        spent = dict()

        for txid, t in block.transactions.items():
            # Coinbase transaction, not in the pool and has no inputs
            if t.get("coinbase"):
                continue

            # Store all spent transactions
            for i in t.get("inputs"):
                spent.setdefault(i["tx_id"], []).append(i["v_out"])

            # Remove the transaction from the pool
            if txid in hashes:
                transactions.pop(hashes[txid])

            # Remove spent transactions inputs from utxo set
            for txid, vouts in spent.items():
                if self.utxo_set.get(txid):
                    self.utxo_set[txid].v_outs = list(set(self.utxo_set[txid].v_outs) - set(vouts))
                    if len(self.utxo_set[txid].v_outs):
                        self.utxo_set.pop(txid)

        # Add transaction outputs to the uxto set
        for txid, vouts in block.outpoints.items():
            self.utxo_set[txid] = UTXO(v_outs=vouts, block_id=len(self.blocks)-1)

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

        if not transaction.get("inputs"):
            logging.debug(
                "Transaction must have inputs"
                + f"\n\texpected: 1"
                + f"\n\tgot: {transaction['version']}"
            )

        for i in transaction["inputs"]:

            # Extract data from the input
            txid, out = i["tx_id"], i["v_out"]
            pub, sig = crypto.load_pubkey(i["key"]), crypto.load_signature(
                i["signature"]
            )
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
            keyhash = crypto.hash_pubkey(pub)
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
            if not crypto.verify(pub=pub, signature=sig, data=d):
                logging.debug(f"Invalid ownership for outpoint {outpoint}")
                return False

        # Check resulting fee and p ownership transfer
        total -= sum([t.get("amount", 0) for t in transaction.get("outputs", [{"amount": 0}])])
        outs = [t["data"] for t in transaction.get("outputs", [{"amount": 0}]) if t.get("data")]

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
            if crypto.hash_transaction(t) != txid:
                logging.debug(
                    "Transaction was tampered"
                    + f"\n\texpected hash:{txid}"
                    + f"\n\tgot: {crypto.hash_transaction(t)}"
                )
                return False

            if t.get("coinbase") and (fee or len(t["outputs"]) != 1):
                logging.debug("More than one coinbase transaction present in the block")
                return False
            elif t.get("coinbase"):
                fee = t["outputs"][0]["amount"]
                continue

            if (amount := self.validate_transaction(t)) is False:
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

    def validate_chain(self) -> bool:
        """
        Verifies the integrity of the chain and rewrites the utxo chain.
        """

        if not len(self.blocks):
            return True

        # Genesis block validation
        self.validate_block(
            block=self.blocks[0],
            difficulty=self.blocks[0].header.target,
            last_hash=GENESIS_HASH,
        )
        for txid, vouts in self.blocks[0].outpoints.items():
            self.utxo_set[txid] = UTXO(v_outs=vouts, block_id=0)

        # Individual block validation
        for i, block in enumerate(self.blocks[1:], start=1):
            if not self.validate_block(
                block=block,
                difficulty=block.header.target,
                last_hash=self.blocks[i - 1].hash,
            ):
                return False

            spent = {}
            for t in block.transactions.values():
                for i in t.get("inputs", []):
                    spent.setdefault(i["tx_id"], []).append(i["v_out"])

            # Remove spent transactions inputs from utxo set
            for txid, vouts in spent.items():
                if self.utxo_set.get(txid):
                    self.utxo_set[txid].v_outs = list(set(self.utxo_set[txid].v_outs) - set(vouts))
                    if len(self.utxo_set[txid].v_outs):
                        self.utxo_set.pop(txid)

            # Add transaction outputs to the uxto set
            for txid, vouts in block.outpoints.items():
                self.utxo_set[txid] = UTXO(v_outs=vouts, block_id=i)


        logging.info("All blockchain transactions are valid!")

        return True

    def __str__(self):
        rep = ""
        for i, block in enumerate(self.blocks):
            rep += block.show(i)
            rep += "\n\n"
        return rep
