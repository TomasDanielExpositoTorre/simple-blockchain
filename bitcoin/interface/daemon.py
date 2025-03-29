import socket
import threading
import json
import logging


# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("./logs/interface-daemon.log", mode="w"),],
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
                        case _:
                            print(f"Unsupported message type: {_}")
        except Exception as e:
            logging.error(f"Connection error with {addr}: {e}")

        logging.debug(f"Node at {addr} disconnected.")

        with self.lock:
            if conn in self.nodes:
                self.nodes.remove(conn)
        conn.close()

    def connection_daemon(self):
        """
        Background thread callback to accept and handle incoming connections.
        """
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.bind((self.host, self.port))
        server_socket.listen()

        logging.debug(f"Master listening on {self.host}:{self.port}")

        while True:
            conn, addr = server_socket.accept()
            logging.debug(f"New node connected from {addr}.")
            with self.lock:
                self.nodes.append(conn)
            threading.Thread(target=self.handle_connection, args=(conn, addr)).start()
        
        logging.debug(f"Closing connection handler for Master")

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
                    self.node.remove(node)
