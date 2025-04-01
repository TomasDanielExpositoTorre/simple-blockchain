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

    @property
    def voting_finished(self) -> bool:
        """
        Checks if voting is currently finished.
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
            with self.lock:
                if len(self.blockchain):
                    conn.sendall(json.dumps({"type": "chain", "blockchain": self.blockchain.serialize()}).encode())

            while True:

                # Obtain data from node
                message = json.loads(conn.recv(self.bufsize).decode())

                with self.lock:
                    match message.get("type"):

                        # Handle received solutions when expecting to vote
                        case "solution":
                            if self.idle.is_set() or self.voting_started.is_set():
                                continue

                            # Start voting
                            self.solution_queue.append(message["block"])
                            self.voting_started.set()

                        # Handle received votes
                        case "verify":
                            if not self.voting_started.is_set():
                                continue

                            self.consensus.append(int(message["vote"]))

                            if self.voting_finished:
                                self.voting_over.set()
                        case "chain":
                            blockchain = Blockchain(
                                blocks=[
                                    PoWBlock.loads(block)
                                    for block in message["blockchain"]
                                ]
                            )

                            if len(blockchain) > len(self.blockchain):
                                self.lock.acquire()
                                self.blockchain = (
                                    blockchain
                                    if blockchain.validate_chain()
                                    else self.blockchain
                                )
                                self.lock.release()

                        case _:
                            print(f"Unsupported message type: {_}")
        except Exception as e:
            logging.error(f"Connection error with {addr}: {e}")

        logging.debug(f"Node at {addr} disconnected.")

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

        logging.debug(f"Master receiving data on {self.host}:{self.port}")

        while True:
            conn, addr = server_socket.accept()
            logging.debug(f"New node connected from {addr}.")
            with self.lock:
                self.nodes.append(conn)
            threading.Thread(target=self.handle_connection, args=(conn, addr)).start()

        logging.debug(f"Closing reception handler for Master")

    def send_to_all(self, message):
        """
        Sends a message to all connected nodes.

        Args:
            message: Message to send.
        """
        logging.debug(f"Sending message: {message} to all connected nodes")
        with self.lock:
            for node in self.nodes:
                try:
                    node.sendall(json.dumps(message).encode())
                except Exception as e:
                    logging.error(f"Failed to send to node: {e}")
                    self.nodes.remove(node)
