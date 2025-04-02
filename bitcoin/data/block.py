"""
This module defines the structure and methods required for a PoW blockchain
block.
"""

import hashlib
import datetime
import json
from dataclasses import asdict, dataclass
from bitcoin.data import crypto


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
        """
        Returns a string representation of this header for hashing.
        """
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
            self.transactions = {crypto.hash_transaction(t): t for t in transactions}
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
        """
        Returns a numeric representation of the mining difficulty for this
        block.
        """
        return int(self.header.target[2:], base=16) * (
            256 ** (int(self.header.target[0:2], base=16) - 3)
        )

    @property
    def outpoints(self):
        """
        Returns a list with all the resulting spendable outpoints for this
        block.
        """
        return {
            txid: list(range(len(t.get("outputs", []))))
            for txid, t in self.transactions.items()
        }

    @classmethod
    def merkle_root(cls, transactions: dict | list) -> str:
        """
        Computes the merkle root hash for the set of transactions in the
        block.

        Args:
            transactions (dict|list): transactions for which the merkle root is
                computed.
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

    def show(self, i: int) -> str:
        """
        Creates a representation of this chain to show on the command line.
        It is expected that the output can show up to 83 characters per row.

        Args:
            i (int): Index of block in the blockchain.

        Returns:
            str: Formatted block representation.
        """
        border = f"#{''.ljust(81,'-')}#\n"

        rep = border + f"|  {f'Blockchain Block {i}'.center(77)}  |\n" + border

        # Block Header
        rep += f"|  {'Header'.center(77)}  |\n" + border
        rep += f"|  {f'Version: {self.header.version}'.ljust(77)}  |\n"
        rep += f"|  {f'Time: {self.header.time}'.ljust(77)}  |\n"
        rep += f"|  {f'Difficulty: {self.header.target}'.ljust(77)}  |\n"
        rep += f"|  {f'Nonce: {self.header.nonce}'.ljust(77)}  |\n"
        rep += f"|  {f'Parent Hash: {self.header.hash_parent}'.ljust(77)}  |\n"
        rep += f"|  {f'Merkle Hash: {self.header.hash_merkle}'.ljust(77)}  |\n"
        rep += f"|  {f'Block  Hash: {self.hash}'.ljust(77)}  |\n"

        # Transactions
        rep += border + f"|  {'Transactions'.center(77)}  |\n" + border
        for val, (txid, t) in enumerate(self.transactions.items()):
            rep += f"|  {f'Hash: {txid}'.ljust(77)}  |\n"

            if t.get("inputs"):
                rep += f"|  {' '.ljust(77)}  |\n"
                rep += f"|  {'Inputs'.ljust(77)}  |\n"
                for i_, inp in enumerate(t["inputs"]):
                    rep += "|      " + f"Index: {i_}".ljust(73) + "  |\n"
                    rep += "|      " + f"TXID: {inp['tx_id']}".ljust(73) + "  |\n"
                    rep += "|      " + f"VOUT: {inp['v_out']}".ljust(73) + "  |\n"
                    rep += (
                        "|      "
                        + f"Owner:     {inp['key'][0:32]}...".ljust(73)
                        + "  |\n"
                    )
                    rep += (
                        "|      "
                        + f"Signature: {inp['signature'][0:32]}...".ljust(73)
                        + "  |\n"
                    )

                    if i_ < len(t["inputs"]) - 1:
                        rep += f"|  {' '.ljust(77)}  |\n"

            if t.get("outputs"):
                rep += f"|  {' '.ljust(77)}  |\n"
                rep += f"|  {'Outputs'.ljust(77)}  |\n"
                for i_, o in enumerate(t["outputs"]):
                    rep += "|      " + f"Index: {i_}".ljust(73) + "  |\n"
                    rep += "|      " + f"Owner: {o['keyhash']}".ljust(73) + "  |\n"
                    rep = (
                        rep + "|      " + f"BTC: {o.get('amount')}".ljust(73) + "  |\n"
                        if o.get("amount")
                        else (
                            rep
                            + "|      "
                            + f"Data: {o['data'][0:32]}...".ljust(73)
                            + "  |\n"
                            if len(o["data"]) > 32
                            else rep
                            + "|      "
                            + f"Data: {o['data']}".ljust(73)
                            + " |\n"
                        )
                    )
                    rep += f"|  {' '.ljust(77)}  |\n"
            if val < len(self.transactions) - 1:
                rep += f"|{''.ljust(81,'~')}|\n"

        rep += border

        return rep
