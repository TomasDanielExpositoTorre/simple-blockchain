"""
Module that handles messages received from miner nodes.
"""

import socket
import threading
import json
import logging
from bitcoin.data.blockchain import Blockchain
from bitcoin.data.block import PoWBlock

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("bitcoin/logs/interface-daemon.log", mode="w"),
    ],
)


class InterfaceDaemon:
    """
    Receiver interface class, which runs as a daemon thread from the main interface.
    """

    def __init__(self, host="localhost", port=65432, base=2):
        """
        Constructor method for this class.
        """
        # Network communication parameters
        self.host = host
        self.port = port
        self.base_difficulty = base
        self.bufsize = 1024**2

        # Variables for voting and adding blocks to the chain
        self.solution_queue = []
        self.consensus = []
        self.nodes = []

        # State definition and thread communication
        self.lock = threading.Lock()
        self.idle = threading.Event()
        self.voting_started = threading.Event()
        self.voting_over = threading.Event()

        # Own blockchain
        self.blockchain = Blockchain(blocks=[])

        # Keys for creating transactions
        self.keys = {}

    @property
    def voting_finished(self) -> bool:
        """
        Checks if the voting process for a solution finished.

        Returns:
            bool: Vote status.
        """
        return len(self.consensus) == len(self.nodes) or sum(
            self.consensus
        ) >= 0.51 * len(self.nodes)

    def handle_connection(self, conn, addr):
        """
        Thread callback to manage data transfer with one node.

        Args:
            conn: Connection to the node.
            addr: Connection address
        """
        try:
            # Send a blockchain copy to new nodes
            with self.lock:
                if len(self.blockchain):
                    conn.sendall(
                        json.dumps(
                            {"type": "chain", "blockchain": self.blockchain.serialize()}
                        ).encode()
                    )

            while True:

                # Obtain data from node
                message = json.loads(conn.recv(self.bufsize).decode())

                with self.lock:
                    match message.get("type"):

                        # Handle received solutions before a vote is opened
                        case "solution":
                            if self.idle.is_set() or self.voting_started.is_set():
                                continue

                            # Get the solution
                            self.solution_queue.append(message["block"])
                            self.voting_started.set()

                        # Handle received votes for a solution
                        case "verify":
                            if not self.voting_started.is_set():
                                continue

                            self.consensus.append(int(message["vote"]))

                            if self.voting_finished:
                                self.voting_over.set()

                        # Handle receiving a blockchain from a node
                        case "chain":
                            blockchain = Blockchain(
                                blocks=[
                                    PoWBlock.loads(block)
                                    for block in message["blockchain"]
                                ]
                            )

                            if len(blockchain) > len(self.blockchain):
                                self.blockchain = (
                                    blockchain
                                    if blockchain.validate_chain()
                                    else self.blockchain
                                )

                                self.send_to_all_nonblock(
                                    {
                                        "type": "chain",
                                        "blockchain": self.blockchain.serialize(),
                                    }
                                )
                        # Handle receiving keypairs from a node
                        case "keys":
                            self.keys[message["priv"]] = message["pub"]
                        case "logout":
                            del self.keys[message["priv"]]
                        case _:
                            print("Unsupported message type")
        except Exception as e:
            logging.error("Connection error with %s: %s", addr, e)

        logging.debug("Node at %s disconnected.", addr)

        # Close connection
        with self.lock:
            if conn in self.nodes:
                self.nodes.remove(conn)
        conn.close()

    def daemon(self):
        """
        Background thread callback to accept and handle incoming connections.
        """
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.bind((self.host, self.port))
        server_socket.listen()

        logging.debug("Master receiving data on %s:%s", self.host, self.port)

        while True:
            conn, addr = server_socket.accept()
            logging.debug("New node connected from %s.", addr)
            with self.lock:
                self.nodes.append(conn)
            threading.Thread(target=self.handle_connection, args=(conn, addr)).start()

        logging.debug("Closing reception handler for Master")

    def send_to_all(self, message):
        """
        Sends a message to all connected nodes.

        Args:
            message: Message to send.
        """
        logging.debug("Sending message: %s to all connected nodes", message)
        with self.lock:
            for node in self.nodes:
                try:
                    node.sendall(json.dumps(message).encode())
                except Exception as e:
                    logging.error("Failed to send to node: %s", e)
                    self.nodes.remove(node)

    def send_to_all_nonblock(self, message):
        logging.debug("Sending message: %s to all connected nodes", message)
        for node in self.nodes:
            try:
                node.sendall(json.dumps(message).encode())
            except Exception as e:
                logging.error("Failed to send to node: %s", e)
                self.nodes.remove(node)
