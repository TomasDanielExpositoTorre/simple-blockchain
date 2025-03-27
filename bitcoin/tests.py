import unittest
from block import PoWBlock
from node import PoWNode, UTXO
from cryptography.hazmat.primitives.asymmetric import rsa
from crypto import hash_pubkey, sign, dump_pubkey, create_keypair


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
        cls.priv, cls.pub = create_keypair()
        cls.otherpriv, cls.otherpub = create_keypair()

        cls.transactions = [
            {
                "version": 1,
                "inputs": [
                    {
                        "tx_id": "1",
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
        cls.txid = list(cls.block.transactions.keys())[0]

        cls.node = PoWNode(pub=cls.pub, priv=cls.priv)
        cls.node.blockchain = [cls.block]
        cls.node.utxo_set = {cls.txid: UTXO(v_outs=[0, 1], block_id=0)}
        cls.node.transactions = []

        cls.coin_transaction = {
                "version": 1,
                "inputs": [
                    {
                        "tx_id": cls.txid,
                        "v_out": 0,
                        "key": dump_pubkey(cls.pub),
                        "signature": sign(cls.priv, str(10000)),
                    }
                ],
                "outputs": [
                    {
                        "amount": 1000,
                        "keyhash": hash_pubkey(cls.otherpub),
                    },
                    {
                        "amount": 8999,
                        "keyhash": hash_pubkey(cls.pub),
                    },
                ],
            }

        cls.data_transaction = {
                    "version": 1,
                    "inputs": [
                        {
                            "tx_id": cls.txid,
                            "v_out": 1,
                            "key": dump_pubkey(cls.pub),
                            "signature": sign(cls.priv, "some-bytes"),
                        },
                    ],
                    "outputs": [
                        {
                            "data": "some-bytes",
                            "keyhash": hash_pubkey(cls.otherpub),
                        },
                        {
                            "data": "some-more-bytes",
                            "keyhash": hash_pubkey(cls.pub),
                        },
                    ],
                }

    def test01_coin_transfer(self):
        """Test 1: Transaction with valid input owner and acceptable amount"""
        fee = self.node.validate_transaction(self.coin_transaction)
        self.assertNotEqual(fee, False)
        self.assertEqual(fee, 1)

    def test02_data_transfer(self):
        """Test 2: Transaction where input data is transfered correctly"""
        fee = self.node.validate_transaction(self.data_transaction)
        self.assertIsNot(fee, False)
        self.assertEqual(fee, 0)


    def test03_invalid_outpoint(self):
        """Test 3: Transaction with invalid outpoint field"""
        txid = self.coin_transaction["inputs"][0]["tx_id"]
        
        self.coin_transaction["inputs"][0]["tx_id"] = "potato"
        self.assertFalse(self.node.validate_transaction(self.coin_transaction))

        self.coin_transaction["inputs"][0]["tx_id"] = txid
        self.coin_transaction["inputs"][0]["v_out"] = "invalid"
        self.assertFalse(self.node.validate_transaction(self.coin_transaction))

    def test04_double_spending(self):
        """Test 4: Transaction with repeated input field"""
        self.coin_transaction["inputs"].append(self.coin_transaction["inputs"][0])
        self.assertFalse(self.node.validate_transaction(self.coin_transaction))
        

    def test05_invalid_pubkey(self):
        """Test 5: Transaction with invalid public key hash"""
        self.coin_transaction["inputs"][0]["key"] = dump_pubkey(self.otherpub)
        self.assertFalse(self.node.validate_transaction(self.coin_transaction))

    def test06_invalid_sign(self):
        """Test 6: Transaction with valid public key but invalid signature"""
        self.coin_transaction["inputs"][0]["signature"] = sign(self.otherpriv, str(10000))
        self.assertFalse(self.node.validate_transaction(self.coin_transaction))

        self.coin_transaction["inputs"][0]["signature"] = sign(self.priv, str(10001))
        self.assertFalse(self.node.validate_transaction(self.coin_transaction))

    def test07_invalid_amount(self):
        """Test 7: Transaction with non-matching input/output amounts"""
        self.coin_transaction["outputs"][1]["amount"] = 9001
        self.assertFalse(self.node.validate_transaction(self.coin_transaction))

    def test08_data_loss(self):
        """Test 8: Transaction where input data is permanently lost"""
        self.data_transaction["outputs"] = []
        self.assertFalse(self.node.validate_transaction(self.data_transaction))


if __name__ == "__main__":
    unittest.main()
