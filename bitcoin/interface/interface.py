import threading
import math
import logging
from bitcoin.interface.daemon import InterfaceDaemon
from bitcoin.data.block import PoWBlock
import bitcoin.data.crypto as crypto
import pydoc
import os
import re


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

    def mine(self):
        diff = self.difficulty
        logging.debug(f"Computed difficulty: {diff}")
        self.idle.clear()

        # Send mining event to all nodes
        self.send_to_all({"type": "mine", "difficulty": diff})

        # Wait for the first solution to arrive
        self.voting_started.wait()
        logging.debug("Solution found! Starting vote...")

        for i, solution in enumerate(self.solutions):
            # Send received solution
            self.send_to_all(
                {
                    "type": "verify",
                    "block": solution,
                    "difficulty": diff,
                }
            )

            # Wait for voting to conclude
            self.voting_over.wait()
            with self.lock:
                self.voting_over.clear()

            logging.info(f"Number of nodes in network: {len(self.nodes)}")
            logging.info(f"Number of accepted votes: {sum(self.consensus)}")

            # Handle consensus response
            if sum(self.consensus) >= 0.51 * len(self.nodes):  # Block accepted
                logging.debug("Solution accepted!")
                self.send_to_all({"type": "veredict", "block": solution})
                with self.lock:
                    self.idle.set()
                    self.voting_started.clear()
                    self.solution_queue = []
                    self.blockchain.add_block(PoWBlock.loads(solution), dict())
                    self.consensus = []
            elif i + 1 == len(self.solutions):  # Block rejected, continue mining
                logging.debug("Last solution rejected")
                self.send_to_all({"type": "veredict", "final": True})
                with self.lock:
                    self.idle.set()
                    self.voting_started.clear()
                    self.solution_queue = []
                    self.consensus = []
            else:  # Block rejected, but solution queue is not empty
                logging.debug("Solution rejected!")
                self.send_to_all({"type": "veredict", "final": False})
                with self.lock:
                    self.consensus = []

    def visualize(self):
        if not len(self.blockchain):
            print("Blockchain is currently empty.")
            return

        pydoc.pager(str(self.blockchain))

    def integrity(self):
        self.blockchain.validate_chain()
        self.send_to_all({"type": "chain", "blockchain": self.blockchain.serialize()})

    def cleanup(self):
        self.send_to_all({"type": "close_connection"})
        with self.lock:
            for node in self.nodes:
                node.close()
        exit()

    def acquire_keys(self):
        self.send_to_all({"type": "keys"})

    def show_keys(self):
        if not len(self.keys):
            print("No keys acquired yet.")
            return

        border = f"#{''.ljust(81,'-')}#\n"
        data = border + f"|  {f'Public Key Visualizer'.center(77)}  |\n" + border

        for i, pub in enumerate(self.keys.values()):
            data += f"|  {f'Index: {i}'.ljust(77)}  |\n"
            data += f"|  {f'Keyhash: {crypto.hash_pubkey(crypto.load_pubkey(pub))}'.ljust(77)}  |\n"
            data += border

        pydoc.pager(data)

    def transaction_creator(self):
        with self.lock:
            keys = [(priv, pub) for priv, pub in self.keys.items()]

        if not len(keys):
            print("No keys found, cannot create transactions")
            return

        transaction = {"version": 1}
        done = False
        key = None
        print("Transaction Creator")
        print("Available keys")
        for i, (priv, pub) in enumerate(keys):
            print(f"{i}: {crypto.hash_pubkey(crypto.load_pubkey(pub))}")

        while not done:
            cmd = input("[trc] Enter a command: ").strip().lower()

            match cmd:
                case "help":
                    print(
                        "Available transaction commands:\n\tinput.\n\toutput.\n\tchain.\n\tkeys."
                    )
                case "input":
                    i = int(input("Select an origin key index: "))
                    if not (0 <= i < len(keys)):
                        print("Incorrect key index. Try again.")
                        continue
                    key = keys[i]

                    txid = input("Enter a transaction id: ").strip().lower()
                    vout = int(input("Enter an output index: ").strip())

                    if not (data := self.blockchain.get_input(txid, vout)):
                        print("Invalid input. Try again.")
                        continue

                    transaction.setdefault("inputs", []).append(
                        {
                            "tx_id": txid,
                            "v_out": vout,
                            "key": key[1],
                            "signature": crypto.sign(
                                priv=crypto.load_privkey(key[0]), data=str(data)
                            ),
                        }
                    )
                case "output":
                    i = int(input("Select a destination key index: "))
                    if not (0 <= i < len(keys)):
                        print("Incorrect key index. Try again.")
                        continue
                    key = keys[i]

                    data = (
                        input("Enter an amount to transfer or data: ").strip().lower()
                    )
                    field = "data"
                    if re.match(r"^\d+(\.\d+)?$", data):
                        data = float(data) if "." in data else int(data)
                        field = "amount"

                    transaction.setdefault("outputs", []).append(
                        {
                            field: data,
                            "keyhash": crypto.hash_pubkey(crypto.load_pubkey(key[1])),
                        }
                    )

                case "chain":
                    self.visualize()
                case "keys":
                    self.show_keys()
                case "done":
                    done = True

        if transaction.get("inputs") or transaction.get("outputs"):
            self.send_to_all({"type": "transaction", "transaction": transaction})

    def run(self):
        """
        Main callback for this class, which processes user input to send
        directives to all nodes.
        """

        # Start the connection handing daemons
        server_thread = threading.Thread(target=self.daemon)
        server_thread.daemon = True
        server_thread.start()

        self.idle.set()
        handlers = {
            "transaction": self.transaction_creator,
            "mine": self.mine,
            "visualize chain": self.visualize,
            "integrity": self.integrity,
            "acquire keys": self.acquire_keys,
            "visualize keys": self.show_keys,
            "exit": self.cleanup,
            "clear": lambda: os.system("cls" if os.name == "nt" else "clear"),
        }
        commands = "List of available commands:\n\t" + "\n\t".join(k for k in handlers)

        handlers["help"] = lambda: print(commands)

        print("Simple Blockchain Simulator")

        while True:
            handlers.get(
                input("Enter a command: ").strip().lower(),
                lambda: print(
                    "Command not recognized, use 'help' to view available commands"
                ),
            )()


interface = Interface()

try:
    interface.run()
except KeyboardInterrupt:
    logging.info("Shutting down master.")
    interface.cleanup()
