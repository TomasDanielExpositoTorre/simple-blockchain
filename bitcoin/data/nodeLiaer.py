"""
This module defines the structure and methods required for a PoW blockchain
node.
"""


import datetime
import logging
import signal
import sys
import time
import memcache
from bitcoin.data import crypto
from bitcoin.data.block import PoWBlock
from bitcoin.data.blockchain import Blockchain
from bitcoin.data.node import PoWNode, Transaction

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(
            f"bitcoin/logs/node-{datetime.datetime.now()}.log", mode="w"
        ),
    ],
)

def handle_sigint(signum, frame):
    logging.debug("Node disconnected.")
    sys.exit(0)

class PoWLiaerNode(PoWNode):
    shared = memcache.Client(['127.0.0.1:11211'], debug=0)

    def __init__(self, pub, priv):
        super().__init__(pub, priv)
        if not self.shared.get('liar'):
            self.shared.set('liar', False)

    def mine_block(self, difficulty: str):
        """
        Applies the proof-of-work operation to all current (valid) transactions,
        and transmits it to other nodes.

        Args:
            difficulty (str): Target for the PoW operation
        """
        found = False
        with self.lock:
            self.shared.set('liar', False)

        # Compute the mining fee and add it as the coinbase transaction
        fee = sum(t.fee for t in self.pool) + Blockchain.reward
        self.pool.append(
            Transaction(
                data={
                    "outputs": [
                        {"amount": fee, "keyhash": crypto.hash_pubkey(self.pub)}
                    ],
                    "coinbase": True,
                    "nonce": time.time_ns(),
                },
                fee=0,
            )
        )

        # Create the block from transaction pool (no sorting or limiting)
        block = PoWBlock(
            transactions=[t.data for t in self.pool],
            parent=self.blockchain.last_hash,
            target=difficulty,
        )
        target = block.target_value

        # Apply the Proof-of-Work
        while not found:
            # Hashcash
            if int(block.hash, base=16) <= target:
                # Send found solution
                self.send({"type": "solution", "block": PoWBlock.dumps(block)})
                logging.debug("Solution found! %s", PoWBlock.dumps(block))
                found = True

            # Halt mining when another node finds the solution
            if not found and self.get_solution():
                logging.debug("Solution found by another node")
                self.mining_signal.wait()
                self.mining_signal.clear()
                found = self.get_solution()

            block.header.nonce += 1

        with self.lock:
            self.shared.set('liar', True)
        logging.debug("Solution confirmed, exiting")
        self.pool.pop()
        sys.exit()

    def validate_block(self, _):
        logging.debug("Vote on sent solution: %s", self.shared.get('liar'))
        self.send({"type": "verify", "vote": self.shared.get('liar')})
    

if __name__ == "__main__":
    signal.signal(signal.SIGINT, handle_sigint)
    privkey, pubkey = crypto.create_keypair()
    node = PoWLiaerNode(pubkey, privkey)
    try:
        node.run()
    except Exception as e:
        logging.error("Error: %s", e)

    node.conn.close()
