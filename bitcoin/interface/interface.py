import threading
import math
import logging
from bitcoin.interface.daemon import InterfaceDaemon
from bitcoin.data.block import PoWBlock


class Interface(InterfaceDaemon):
    def __init__(self, host="localhost", port=65432, base=2):
        """
        Constructor method for this class.
        """
        super().__init__(host, port, base)

    @property
    def difficulty(self):
        """
        Adaptive difficulty value depending on the number of nodes present in the chain
        """
        with self.lock:
            diff = hex(
                32
                - (self.base_difficulty + math.floor(math.log(len(self.nodes) + 1, 4)))
            )
            return f"0{diff[2:]}ffffff" if len(diff) == 3 else f"{diff[2:]}ffffff"

    @property
    def solutions(self):
        self.lock.acquire()
        solution_queue = self.solution_queue
        self.lock.release()
        return solution_queue

    def run(self):
        """
        Main callback for this class, which processes user input to send
        directives to all nodes.
        """
        disconnected = False
        # Start the connection handing daemons
        server_thread = threading.Thread(target=self.daemon)
        server_thread.daemon = True
        server_thread.start()

        self.idle.set()

        print("Simple Blockchain Simulator")
        while not disconnected:
            cmd = input("Enter a command: ").strip()

            match cmd.lower():
                case "help":
                    print(
                        "List of available commands:"
                        + "\n\tTransaction."
                        + "\n\tMine"
                        + "\n\tVisualize"
                        + "\n\tIntegrity"
                    )
                case "transaction":
                    pass
                case "mine":
                    # Send mining event to all nodes
                    diff = self.difficulty
                    logging.debug(f"Computed difficulty: {diff}")
                    self.idle.clear()
                    self.send_to_all({"type": "mine", "difficulty": diff})

                    # Wait for the first solution to arrive
                    self.voting_started.wait()
                    logging.debug("Solution found! Starting vote...")

                    for i, solution in enumerate(self.solutions):
                        # Send first received solution
                        self.send_to_all(
                            {
                                "type": "verify",
                                "block": solution,
                                "difficulty": diff,
                            }
                        )

                        # Wait for voting to conclude
                        self.voting_over.wait()
                        self.voting_over.clear()

                        logging.info(f"Number of nodes in network: {len(self.nodes)}")
                        logging.info(f"Number of accepted votes: {sum(self.consensus)}")
                        # Handle consensus response
                        if sum(self.consensus) >= 0.51 * len(
                            self.nodes
                        ):  # Block accepted
                            logging.debug("Solution accepted!")
                            self.send_to_all({"type": "veredict", "block": solution})
                            with self.lock:
                                self.idle.set()
                                self.voting_started.clear()
                                self.solution_queue = []
                                self.blockchain.blocks.append(PoWBlock.loads(solution))
                        elif i + 1 == len(
                            self.solutions
                        ):  # Block rejected, continue mining
                            logging.debug("Last solution rejected")
                            self.send_to_all({"type": "veredict", "final": True})
                            with self.lock:
                                self.idle.set()
                                self.voting_started.clear()
                                self.solution_queue = []
                        else:  # Block rejected, but solution queue is not empty
                            logging.debug("Solution rejected!")
                            self.send_to_all({"type": "veredict", "consensus": False})
                        self.consensus = []

                case "visualize":
                    pass
                case "integrity":
                    self.blockchain.validate_chain()
                    self.send_to_all(
                        {"type": "chain", "blockchain": self.blockchain.serialize()}
                    )
                case "exit":
                    disconnected = True
                case _:
                    print(
                        "Command not recognized, use 'help' to view available commands"
                    )

    def cleanup(self):
        self.send_to_all({"type": "close_connection"})
        with self.lock:
            for node in self.nodes:
                node.close()
        exit()


interface = Interface()

try:
    interface.run()
except KeyboardInterrupt:
    logging.info("Shutting down master.")

interface.cleanup()
