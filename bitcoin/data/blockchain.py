"""
This module defines the structure and methods required for a PoW blockchain.
"""

import logging
from dataclasses import dataclass, field
from bitcoin.data import crypto
from bitcoin.data.block import PoWBlock

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
    """
    Dataclass representation for the entire blockchain, with all validated
    blocks, the hashcash problem reward and a set of unspent transactions.
    """

    blocks: list[PoWBlock]
    utxo_set: dict[str, UTXO] = field(default_factory=dict)
    reward: int = 3.125

    def __len__(self) -> int:
        """
        Returns the current length of the chain.
        """
        return len(self.blocks)

    @property
    def last_hash(self) -> str:
        """
        Returns the hash of the last block in the chain.
        """
        return self.blocks[-1].hash if self.blocks else GENESIS_HASH

    def get_input(self, txid, v_out):
        """
        Wrapper function for obtaining an unspent transaction outpoint.

        Args:
            txid (str): Transaction hash value.
            v_out (int): Unspent transaction output index.

        Returns:
            int|str
        """
        if not self.utxo_set.get(txid):
            logging.error("Invalid transaction identifier: %s", txid)
            return None

        utxo = self.utxo_set[txid]
        if v_out not in utxo.v_outs:
            logging.error(
                "Invalid transaction outpoint:\n" + "got: %s\n" + "expected: %s\n",
                v_out,
                utxo.v_outs,
            )
            return None

        txo = self.blocks[utxo.block_id].transactions[txid]["outputs"][v_out]
        return str(txo.get("amount", txo.get("data")))

    def serialize(self) -> list[str]:
        """
        Serializes the blockchain.

        Returns:
            list: Serialized blocks.
        """
        return [PoWBlock.dumps(block) for block in self.blocks]

    def add_block(self, block: PoWBlock, transactions: list[dict]):
        """
        Wrapper method to append a validated block to the chain.

        Args:
            block (PoWBlock): Mined block.
            transactions (list[dict]): transaction pool from the caller.

        Returns:
            dict: New pool without the transactions already included on the
                block.
        """
        self.blocks.append(block)

        hashes = {crypto.hash_transaction(t): i for i, t in enumerate(transactions)}
        spent = {}

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
                    self.utxo_set[txid].v_outs = list(
                        set(self.utxo_set[txid].v_outs) - set(vouts)
                    )
                    if len(self.utxo_set[txid].v_outs):
                        self.utxo_set.pop(txid)

        # Add transaction outputs to the uxto set
        for txid, vouts in block.outpoints.items():
            self.utxo_set[txid] = UTXO(v_outs=vouts, block_id=len(self.blocks) - 1)

        return transactions

    def validate_transaction(self, transaction: dict) -> bool | int:
        """
        Validates the integrity of a transaction, used either when adding
        transactions to the pool, or during the validation step after
        a solution has been received.

        This method should not be called to validate the coinbase transaction
        appended by the winning miner.

        Args:
            transaction (dict): Blockchain transaction following the expected
            format in bitcoin/transaction.json.

        Returns:
            False on an invalid transaction, the resulting fee otherwise.
        """
        total = 0
        data = []
        inpairs = []

        if transaction["version"] != 1:
            logging.debug(
                "Wrong transaction version" + "\n\texpected: 1" + "\n\tgot: %s",
                transaction["version"],
            )
            return False

        for i in transaction.get("inputs"):

            # Extract data from the input
            pub, sig = crypto.load_pubkey(i["key"]), crypto.load_signature(
                i["signature"]
            )
            outpoint = f"{i['tx_id']}:{i['v_out']}"

            # Look up outpoint in unspent set
            if outpoint in inpairs:
                logging.debug("The outpoint %s was spent twice", outpoint)
                return False
            inpairs.append(outpoint)

            utxo = self.utxo_set.get(i["tx_id"], None)
            if not utxo or i["v_out"] not in utxo.v_outs:
                logging.debug("The outpoint %s is invalid", outpoint)
                return False

            tx: dict = self.blocks[utxo.block_id].transactions[i["tx_id"]]["outputs"][i["v_out"]]

            # Compare public keys
            keyhash = crypto.hash_pubkey(pub)
            if keyhash != tx["keyhash"]:
                logging.debug("Invalid public key for outpoint %s", outpoint)
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
                logging.debug("Invalid ownership for outpoint %s", outpoint)
                return False

        # Check resulting fee and ownership transfer
        total -= sum(
            t.get("amount", 0) for t in transaction.get("outputs", [{"amount": 0}])
        )
        outs = [
            t["data"]
            for t in transaction.get("outputs", [{"amount": 0}])
            if t.get("data")
        ]

        if total < 0:
            logging.debug("Invalid transaction fee: %s", total)
            return False

        if len(set(data) - set(outs)) > 0:
            logging.debug(
                "Invalid transaction, some input data is not being transfered as outputs"
            )
            return False

        return total

    def validate_block(self, block: PoWBlock, difficulty: str, last_hash: str):
        """
        Validates a block received from other nodes and appends it to own
        blockchain after consensus has been reached. This method can be called
        for appending a new block to an existing blockchain or for integrity
        validation.

        Args:
            block (PoWBlock): Block data to validate.
            difficulty (str): Difficulty value sent from the main server.
            last_hash (str): parent block hash.

        Returns:
            bool: True if the block information is valid, False otherwise.
        """

        fee, total = 0, 0

        # Validate block header values
        if block.header.hash_parent != last_hash:
            logging.debug(
                "Block parent hash is incorrect" + "\n\texpected:%s" + "\n\tgot: %s",
                last_hash,
                block.header.hash_parent,
            )
            return False

        if block.header.target != difficulty:
            logging.debug(
                "Block difficulty value is incorrect"
                + "\n\texpected:%s"
                + "\n\tgot: %s",
                difficulty,
                block.header.target,
            )
            return False

        # Validate obtained hash
        if block.target_value < int(block.hash, 16):
            logging.debug(
                "Block target was not reached" + "\n\texpected:%s" + "\n\tgot: %s",
                block.target_value,
                int(block.hash, 16),
            )
            return False

        # Validate individual transactions
        for txid, t in block.transactions.items():
            if crypto.hash_transaction(t) != txid:
                logging.debug(
                    "Transaction was tampered" + "\n\texpected hash:%s" + "\n\tgot: %s",
                    txid,
                    crypto.hash_transaction(t),
                )
                return False

            if t.get("coinbase") and (fee or len(t["outputs"]) != 1):
                logging.debug("More than one coinbase transaction present in the block")
                return False
            if t.get("coinbase"):
                fee = t["outputs"][0]["amount"]
                continue

            if (amount := self.validate_transaction(t)) is False:
                return False

            total += amount

        if fee != (total + Blockchain.reward):
            logging.debug(
                "Reward value is incorrect" + "\n\texpected:%s" + "\n\tgot: %s",
                total + Blockchain.reward,
                fee,
            )
            return False

        logging.debug("Block %s is valid!", PoWBlock.dumps(block))
        return True

    def validate_chain(self) -> bool:
        """
        Verifies the integrity of the chain and rewrites the utxo chain.

        Returns:
            bool: True if the chain is valid, False otherwise.
        """

        # An empty chain is always valid
        if not self.blocks:
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

            # Store all spent transactions
            spent = {}
            for t in block.transactions.values():
                for i in t.get("inputs", []):
                    spent.setdefault(i["tx_id"], []).append(i["v_out"])

            # Remove spent transactions inputs from utxo set
            for txid, vouts in spent.items():
                if self.utxo_set.get(txid):
                    self.utxo_set[txid].v_outs = list(
                        set(self.utxo_set[txid].v_outs) - set(vouts)
                    )
                    if len(self.utxo_set[txid].v_outs):
                        self.utxo_set.pop(txid)

            # Add transaction outputs to the uxto set
            for txid, vouts in block.outpoints.items():
                self.utxo_set[txid] = UTXO(v_outs=vouts, block_id=i)

        logging.info("All blockchain transactions are valid!")

        return True

    def __str__(self):
        """
        Returns a string representation for the chain, composed of all
        existing blocks.
        """
        rep = ""
        for i, block in enumerate(self.blocks):
            rep += block.show(i)
            rep += "\n\n"
        return rep
