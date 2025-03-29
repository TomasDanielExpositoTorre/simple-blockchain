"""
This module defines the structure and methods required for a PoW blockchain
block.
"""

import hashlib
import datetime
import json
from dataclasses import asdict, dataclass
from crypto import hash_transaction

@dataclass
class BlockHeader:
    """
    Block header dataclass.
    """

    version: int
    hash_parent: str
    hash_merkle: str
    time: int
    target: str
    nonce: int

    def __repr__(self):
        return (
            str(self.version)
            + self.hash_parent
            + self.hash_merkle
            + str(self.time)
            + self.target
            + str(self.nonce)
        )


class PoWBlock:
    """
    Class that defines a how a block is composed in a PoW-based blockchain,
    like bitcoin.
    """

    header: BlockHeader
    transactions: dict[dict]

    def __init__(
        self,
        transactions: list[dict],
        header: dict = None,
        parent: str = None,
        target: str = None,
    ):
        """
        Constructor method for this class.

        Args:
            transactions (list[dict]): Transactions inside this block.
            header (dict): Header data for a solved block. This overrides
                parent and target values, and should be used only to
                initialize a block received from another node.
            parent (str): Hash of the parent block.
            target (str): Hashchash problem target.
        """
        if not header:
            self.header = BlockHeader(
                version=1,
                hash_parent=parent,
                hash_merkle=PoWBlock.merkle_root(transactions),
                time=int(datetime.datetime.now().timestamp()),
                target=target,
                nonce=0,
            )
            self.transactions = {
                hash_transaction(t): t
                for t in transactions
            }
        else:
            self.header = BlockHeader(**header)
            self.transactions = transactions

    @property
    def hash(self) -> str:
        """
        Computes the hash value for this block.

        Returns:
            str: Double SHA256 hash value of the header.
        """
        return hashlib.sha256(
            hashlib.sha256(repr(self.header).encode()).digest()
        ).hexdigest()

    @property
    def target_value(self) -> int:
        return int(self.header.target[2:], base=16) * (
            256 ** (int(self.header.target[0:2], base=16) - 3)
        )

    @classmethod
    def merkle_root(cls, transactions) -> str:
        """
        Computes the merkle root hash for the set of transactions in the
        block.

        Returns:
            str: Double SHA256 hash value at the root of the tree.
        """

        # Handle non-balanced trees without altering the original transactions
        trs = (
            transactions[:]
            if isinstance(transactions, list)
            else list(transactions.values())
        )

        trs = trs + [trs[-1]] if len(trs) % 2 else trs

        # Compute and concatenate hash pairs
        hashlist: list[str] = [
            hashlib.sha256(json.dumps(t).encode()).digest() for t in trs
        ]

        while len(hashlist) > 1:
            hashlist = [
                hashlib.sha256(hashlist[i] + hashlist[i + 1]).digest()
                for i in range(0, len(hashlist), 2)
            ]

        return hashlib.sha256(hashlist[0]).hexdigest()

    @classmethod
    def dumps(cls, block: "PoWBlock") -> str:
        """
        Creates a json representation of a block.

        Args:
            block (PoWBlock): Mined block

        Returns:
            str: json-string with block information.
        """
        return json.dumps({**asdict(block.header), "transactions": block.transactions})

    @classmethod
    def loads(cls, data: str) -> "PoWBlock":
        """
        Creates a block from serialized json data.

        Args:
            data (str): json-string representing a block

        Returns:
            PoWBlock: Received block object.
        """
        header: dict = json.loads(data)
        transactions = header.pop("transactions")
        return PoWBlock(transactions=transactions, header=header)
