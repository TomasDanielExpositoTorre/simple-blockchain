import socket
import threading
import json
import math
from queue import Queue
import logging


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)

BASE_DIFFICULTY = 2


class MainNode:
    def __init__(self, host="localhost", port=65432):
        """
        Constructor method for this class.
        """
        # Network communication parameters
        self.host = host
        self.port = port
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
    def difficulty(self):
        """
        Adaptive difficulty value depending on the number of nodes present in the chain
        """
        diff = BASE_DIFFICULTY + math.floor(math.log(len(self.nodes) + 1, 4))
        logging.debug(f"Difficulty updated to {diff} zeros.")
        return "1EFFFFFF"
        # return '0' + (hex(diff) + 'ffff')[2:] if len(hex(diff)) == 3 else (hex(diff) + 'ffffff')[2:] 

    @property
    def voting_finished(self) -> bool:
        """
        Checks if voting is currently finished.
        """
        return len(self.consensus)+1 == len(self.nodes) or sum(
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
                            if self.idle.is_set():
                                break
                            self.solution_queue.append((message["block"], conn))
                            self.voting_started.set()

                        # Handle received votes
                        case "verify":
                            if not self.voting_started.is_set():
                                break

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

    def send_to_all(self, message, exceptfor=None):
        """
        Sends a message to all connected nodes.

        Args:
            message: Message to send.
            exceptfor: Node connection to ignore when sending the message. Defaults
                to None.
        """
        with self.lock:
            for node in self.nodes:
                if node != exceptfor:
                    try:
                        node.sendall(json.dumps(message).encode())
                    except Exception as e:
                        logging.error(f"Failed to send to node: {e}")
                        self.node.remove(node)

    def run(self):
        """
        Main callback for this class, which processes user input to send
        directives to all nodes.
        """
        # Start the connection handing daemon
        server_thread = threading.Thread(target=self.connection_daemon)
        server_thread.daemon = True
        server_thread.start()

        print("Simple Blockchain Simulator")
        try:
            while True:
                cmd = input("Enter a command: ").strip()

                match cmd.lower():
                    case "help":
                        print("List of available commands:")
                        print("\tTransaction.")
                        print("\tMine.")
                        print("\tVisualize.")
                        print("\tIntegrity.")
                    case "transaction":
                        pass
                    case "mine":
                        # Set mining event and await for the first solution
                        self.send_to_all({"type": "mine", "difficulty": self.difficulty})
                        self.voting_started.wait()

                        with self.lock:
                            solution_queue = self.solution_queue

                        for i, (solution, conn) in enumerate(solution_queue):
                            # Send first received solution                            
                            self.send_to_all({"type": "verify", "block": solution}, exceptfor=conn)

                            # Wait for voting to conclude
                            self.voting_over.wait()

                            # Handle consensus response
                            with self.lock:
                                if sum(self.consensus) >= 0.51 * len(self.nodes): # Block accepted
                                    self.send_to_all({"type": "veredict", "block": solution})
                                elif i + 1 == len(solution_queue): # Block rejected, continue mining
                                    self.send_to_all({"type": "veredict", "final": True})
                                else: # Block rejected, but solution queue is not empty
                                    self.send_to_all({"type": "veredict", "consensus": False})

                    case "visualize":
                        pass
                    case "integrity":
                        pass
                    case _:
                        print(
                            "Command not recognized, use 'help' to view available commands"
                        )

        except KeyboardInterrupt:
            logging.info("\nShutting down master.")
            self.send_to_all({"type": "close_connection"})
            with self.lock:
                for node in self.nodes:
                    node.close()
            exit()

interface = MainNode()
interface.run()