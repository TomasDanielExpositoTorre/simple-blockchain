"""
This module defines the structure and methods required for a PoW blockchain
node.
"""

import datetime
import logging
import signal
import sys
from bitcoin.data import crypto
from bitcoin.data.block import PoWBlock
from bitcoin.data.blockchain import Blockchain
from bitcoin.data.node import PoWNode, Transaction

def handle_sigint(signum, frame):
    logging.debug("Node disconnected.")
    sys.exit(0)


class PoWSelfishNode(PoWNode):
    def validate_block(self, _):
        self.send({"type": "verify", "vote": False})


if __name__ == "__main__":
    signal.signal(signal.SIGINT, handle_sigint)
    privkey, pubkey = crypto.create_keypair()
    node = PoWSelfishNode(pubkey, privkey)
    try:
        node.run()
    except Exception as e:
        logging.error("Error: %s", e)

    node.conn.close()
