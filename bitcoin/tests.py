import unittest
from block import PoWBlock
from node import PoWNode, UTXO
from cryptography.hazmat.primitives.asymmetric import rsa
from crypto import hash_pubkey, sign, dump_pubkey


class PoWBlockTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.transactions = [
            {
                "version": 1,
                "inputs": [
                    {
                        "tx_id": 1,
                        "v_out": 0,
                        "key": "mypublickey",
                        "signature": "mysignature",
                    }
                ],
                "outputs": [
                    {"amount": 10, "keyhash": "pubkey-hash"},
                    {"data": "some-bytes", "keyhash": "pubkey-hash"},
                ],
            }
        ]
        cls.block = PoWBlock(
            transactions=cls.transactions,
            parent="This is a test!",
            target="This is still a test!",
        )

    def test01_merkle_root(self):
        """Test Case 01: Merkle Roots"""
        # Test that the method works as intended
        self.assertEqual(
            PoWBlock.merkle_root(self.transactions),
            self.block.header.hash_merkle,
            msg="Merkle root does not match with header hash!",
        )

        # Test that transactions with odd elements get balanced
        self.assertEqual(
            PoWBlock.merkle_root(self.transactions + self.transactions),
            self.block.header.hash_merkle,
            msg="Merkle root does not match with header hash!",
        )

    def test02_hashing(self):
        """Test Case 01: Block Header Hash"""
        hashval = self.block.hash

        # Test that the hash changes with the nonce
        self.block.header.nonce += 1
        self.assertNotEqual(
            self.block.hash, hashval, "Nonce is not affecting the block hash!"
        )

        # Test the determinism of the hash by reverting the nonce
        self.block.header.nonce -= 1
        self.assertEqual(
            self.block.hash, hashval, "Nonce is not affecting the block hash!"
        )

    def test03_serialization(self):
        """Test Case 01: Block Serialization and De-Serialization"""
        serialized_block = PoWBlock.loads(PoWBlock.dumps(self.block))
        self.assertEqual(
            self.block.header,
            serialized_block.header,
            "Something went wrong during header serialization",
        )
        self.assertEqual(
            self.block.transactions,
            serialized_block.transactions,
            "Something went wrong during transaction serialization",
        )


class PoWNodeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.priv = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )
        cls.pub = cls.priv.public_key()

        cls.transactions = [
            {
                "version": 1,
                "inputs": [
                    {
                        "tx_id": 1,
                        "v_out": 0,
                        "key": "mypublickey",
                        "signature": "mysignature",
                    }
                ],
                "outputs": [
                    {"amount": 10000, "keyhash": hash_pubkey(cls.pub)},
                    {"data": "some-bytes", "keyhash": hash_pubkey(cls.pub)},
                ],
            }
        ]
        cls.block = PoWBlock(
            transactions=cls.transactions,
            parent="This is a test!",
            target="This is still a test!",
        )

        (cls.transactions)

    def test01_valid_transaction(self):
        """Test 01: Transaction with valid input owner and acceptable amount"""
        txid = list(self.block.transactions.keys())[0]
        node = PoWNode(
            blockchain=[self.block],
            utxo={txid: UTXO(v_outs=[0, 1], block_id=0)},
            transactions=[],
        )

        fee, is_valid = node.validate_transaction(
            {
                "version": 1,
                "inputs": [
                    {
                        "tx_id": txid,
                        "v_out": 0,
                        "key": dump_pubkey(self.pub),
                        "signature": sign(self.priv, str(10000)),
                    }
                ],
                "outputs": [
                    {
                        "amount": 1000,
                        "keyhash": hash_pubkey(self.pub),
                    },
                    {
                        "amount": 8999,
                        "keyhash": hash_pubkey(self.pub),
                    },
                ],
            }
        )
        self.assertEqual(fee, 1)
        self.assertTrue(is_valid)


if __name__ == "__main__":
    unittest.main()
