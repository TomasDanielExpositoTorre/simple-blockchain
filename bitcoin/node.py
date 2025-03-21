import hashlib
from block import PoWBlock
from dataclasses import dataclass
from cryptography.exceptions import InvalidSignature
from crypto import load_pubkey, load_signature, hash_pubkey, verify


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
class PoWNode:
    """
    Class representing a node in the blockchain, which can both apply the
    proof-of-work operation and validate mined blocks.
    """

    blockchain: list[PoWBlock]
    utxo: dict[str, UTXO]
    transactions: list[dict]

    def mine_block(self):
        pass

    def add_transaction(self, transaction: dict):
        """
        Appends a transaction to the current transaction pool.

        Args:
            transaction (dict): Blockchain transaction following the expected
            format.
        """
        message, is_valid = self.validate_transaction(transaction)

        if not is_valid:
            print(message)
            return

        transaction["fee"] = message
        self.transactions.append(transaction)

    def validate_transaction(self, transaction: dict):
        """
        Validates the integrity of a transaction.

        Args:
            transaction (dict): Blockchain transaction following the expected
            format.

        Returns:
            tuple: On failure, an error message is returned and the transaction
            validity is set to false. On success, the validity is set to true
            and the transaction mining fee is returned in place of the message
        """
        amount = 0
        if transaction["version"] != 1:
            return "Wrong transaction version", False

        for i in transaction["inputs"]:

            # Extract data from the input
            txid, out = i["tx_id"], i["v_out"]
            key = load_pubkey(i["key"])
            signature = load_signature(i["signature"])

            # Look up output in unspent list
            utx = self.utxo.get(txid, None)
            if not utx or out not in utx.v_outs:
                return (
                    f"The outpoint {txid}:{out} is not valid",
                    False,
                )
            itx: dict = self.blockchain[utx.block_id].transactions[txid]["outputs"][out]

            # Compare public keys
            keyhash = hash_pubkey(key)
            if keyhash != itx["keyhash"]:
                return (
                    f"Invalid public key on transaction {txid} output {out}",
                    False,
                )

            # Compare signature for ownership
            k = "amount" if "amount" in itx.keys() else "data"
            amount += itx.get("amount", 0)

            if not verify(pub=key, signature=signature, data=str(itx[k])):
                return (
                    f"Invalid ownership for transaction {txid} output {out}",
                    False,
                )

        for i in transaction["outputs"]:
            amount -= i.get("amount", 0)

        if amount < 0:
            return "Transaction output cannot be greater than input", False

        return amount, True
