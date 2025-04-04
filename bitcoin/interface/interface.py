"""
Main entry script for the application which handles user input.
"""

import threading
import math
import logging
import pydoc
import os
import re
import sys
import time
from bitcoin.data import crypto
from bitcoin.data.block import PoWBlock
from bitcoin.interface.daemon import InterfaceDaemon


class Interface(InterfaceDaemon):
    """
    CLI Interface class.
    """

    @property
    def difficulty(self):
        """
        Adaptive difficulty value depending on the number of nodes present in the chain.
        """
        with self.lock:
            diff = hex(
                32
                - (self.base_difficulty + math.floor(math.log(len(self.nodes) + 1, 4)))
            )
            return f"0{diff[2:]}ffffff" if len(diff) == 3 else f"{diff[2:]}ffffff"

    @property
    def solutions(self):
        """
        Thread-safe wrapper to access the received solution queue.
        """
        with self.lock:
            solution_queue = self.solution_queue
        return solution_queue

    def mine(self):
        """
        Callback function to start the block mining process accross all nodes.
        """
        diff = self.difficulty
        logging.debug("Computed difficulty: %s", diff)
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

            logging.info("Number of nodes in network: %s", len(self.nodes))
            logging.info("Number of accepted votes: %s", sum(self.consensus))

            # Handle consensus response
            if sum(self.consensus) >= 0.51 * len(self.nodes):  # Block accepted
                logging.debug("Solution accepted!")
                self.send_to_all({"type": "veredict", "block": solution})
                with self.lock:
                    self.idle.set()
                    self.voting_started.clear()
                    self.solution_queue = []
                    self.blockchain.add_block(PoWBlock.loads(solution), {})
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
        """
        Callback method to visualize the blockchain in a linux less-like interface.
        """
        if not self.blockchain:
            print("Blockchain is currently empty.")
            return

        # Show the data
        pydoc.pager(str(self.blockchain))

    def integrity(self):
        """
        Callback method to validate the integrity of the chain in the main
        server and all nodes.
        """
        self.blockchain.validate_chain()
        self.send_to_all({"type": "chain", "blockchain": self.blockchain.serialize()})

    def cleanup(self):
        """
        Callback method to exit the application gracefully.
        """
        self.send_to_all({"type": "close_connection"})
        with self.lock:
            for node in self.nodes:
                node.close()
        sys.exit()

    def show_keys(self):
        """
        Callback method to visualize acquired keys in a linux less-like
        interface.
        """
        if not self.keys:
            print("No keys acquired yet.")
            return

        # TUI text formatting
        border = f"#{''.ljust(81,'-')}#\n"
        data = border + f"|  {'Public Key Visualizer'.center(77)}  |\n" + border

        for i, pub in enumerate(self.keys.values()):
            data += f"|  {f'Index: {i}'.ljust(77)}  |\n"
            data += f"|  {f'Keyhash: {crypto.hash_pubkey(crypto.load_pubkey(pub))}'.ljust(77)}  |\n"
            data += border

        # Show the data
        pydoc.pager(data)

    def transaction_creator(self):
        """
        Callback function to create transactions interactively.
        """

        # Load keypairs to use during transactions
        with self.lock:
            keys = list(self.keys.items())

        if not keys:
            print("No keys found, cannot create transactions")
            return

        transaction = {"version": 1}
        done = False
        key = None

        print("\nTransaction Creator")
        print("Available keys")
        for i, (_, pub) in enumerate(keys):
            print(f"{i}: {crypto.hash_pubkey(crypto.load_pubkey(pub))}")

        while not done:
            try:
                cmd = input("[transaction-creator] Enter a command: ").strip().lower()

                match cmd:

                    # Print available commands
                    case 'h' | "help":
                        print(
                            "Available transaction commands:\n\t(i) input\n\t(o) output\n\t(c) chain\n\t(k) keys\n\t(cl)clear\n\t(d) done\n\t(h) help"
                        )

                    # Create an input for the transaction
                    case 'i' | "input":
                        i = int(input("Select an key index: "))
                        if not 0 <= i < len(keys):
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
                                    priv=crypto.load_privkey(key[0]), data=data
                                ),
                                "nonce": time.time_ns(),
                            }
                        )

                    # Create an output for the transaction
                    case 'o' | "output":
                        i = int(input("Select a destination key index: "))
                        if not 0 <= i < len(keys):
                            print("Incorrect key index. Try again.")
                            continue
                        key = keys[i]

                        data = (
                            input("Enter an amount to transfer or data: ").strip().lower()
                        )
                        field = "data"
                        if re.match(r"^\d+$", data):
                            data = int(data)
                            field = "amount"

                        transaction.setdefault("outputs", []).append(
                            {
                                field: data,
                                "keyhash": crypto.hash_pubkey(crypto.load_pubkey(key[1])),
                            }
                        )

                    # Visualize the chain to obtain hashes
                    case 'c' | "chain":
                        self.visualize()

                    # Visualize all available keys
                    case 'k' | "keys":
                        self.show_keys()

                    # Clear the screen
                    case 'cl' | "clear":
                        os.system("cls" if os.name == "nt" else "clear")
        
                    # Exit the transaction menu
                    case 'd' | "done":
                        done = True

                    # Other cases
                    case _:
                        print("Command not recognized, use '(h) help' to view available commands")
            except Exception as e:
                logging.error("Error: %s", e)
                print("Something went wrong, please try again.")

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

        # Currently supported commands
        command_map = {
            self.transaction_creator: ["t", "transaction"],
            self.mine: ["m", "mine"],
            self.visualize: ["c", "chain"],
            self.integrity: ["i", "integrity"],
            self.show_keys: ["k", "keys"],
            self.cleanup: ["e", "exit"],
            lambda: os.system("cls" if os.name == "nt" else "clear"): ["cl", "clear"],
            lambda: print(help_text): ["h", "help"],
        }

        handlers = {
            alias: func
                for func, aliases in command_map.items()
                for alias in aliases
        }

        help_text = "List of available commands:\n\t" + "\n\t".join(f"({aliases[0]}) {aliases[1]}" for aliases in command_map.values())

        print("Simple Blockchain Simulator")
        while True:
            try:
                handlers.get(
                    input("Enter a command: ").strip().lower(),
                    lambda: print(
                        "Command not recognized, use 'help' to view available commands"
                    ),
                )()
            except Exception as e:
                logging.error("Error: %s", e)
                print("Something went wrong, please try again.")


interface = Interface()

try:
    interface.run()
except KeyboardInterrupt:
    logging.info("Shutting down master.")
    interface.cleanup()
