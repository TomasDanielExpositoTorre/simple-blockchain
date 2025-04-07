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
    def validate_block(self, _):
        self.send({"type": "verify", "vote": False})
    

if __name__ == "__main__":
    signal.signal(signal.SIGINT, handle_sigint)
    privkey, pubkey = crypto.create_keypair()
    node = PoWLiaerNode(pubkey, privkey)
    try:
        node.run()
    except Exception as e:
        logging.error("Error: %s", e)

    node.conn.close()
