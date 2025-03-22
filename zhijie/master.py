import socket
import threading
import json
import math
from queue import Queue
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # Log to console
        # logging.FileHandler('master_node.log')  # Log to a file
    ]
)

BASE_DIFFICULTY = 2

class MasterNode:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.credentials = {}
        self.slaves = []
        self.lock = threading.Lock()
        self.nonce_queue = Queue()
        self.difficulty = 0

        # Verification tracking
        self.verf_lock = threading.Lock()
        self.verf_progress = False
        self.verf_correct = 0
        self.verf_resp = 0
        self.verf_total = 0

    def handle_slave(self, conn, addr):
        try:
            while True:
                data = conn.recv(1024)
                if not data:
                    break
                try:
                    message = json.loads(data.decode())
                    if message['type'] == 'nonce':
                        self.nonce_queue.put(message['value'])
                    elif message['type'] == 'verification':
                        with self.verf_lock:
                            if self.verf_progress:
                                self.verf_resp += 1
                                if message['result']:
                                    self.verf_correct += 1
                                logging.debug(f"Verification update: {self.verf_correct}/{self.verf_total}")
                                if self.verf_correct >= 0.51 * self.verf_total:
                                    logging.info("\nMAJORITY CONSENSUS REACHED: Valid nonce confirmed by >51% of slaves")
                                    self.verf_progress = False
                except json.JSONDecodeError:
                    continue
        except Exception as e:
            logging.error(f"Connection error with {addr}: {e}")
        finally:
            logging.debug(f"Slave at {addr} disconnected. Total slaves: {len(self.slaves)}")
            with self.lock:
                if conn in self.slaves:
                    self.slaves.remove(conn)
                self.update_difficulty()
            conn.close()

    def update_difficulty(self):
        # Difficulty:
        # - 1  slave:    2+⌊log4 (1+1)⌋    = 2+0 = 2
        # - 10 slaves:   2+⌊log4 (10+1)⌋   = 2+1 = 3
        # - 100 slaves:  2+⌊log4 (100+1)⌋  = 2+3 = 5
        # - 1000 slaves: 2+⌊log4 (1000+1)⌋ = 2+4 = 6
        self.difficulty = BASE_DIFFICULTY + math.floor(math.log(len(self.slaves) + 1, 4))
        logging.debug(f"Difficulty updated to {self.difficulty} zeros.")

    def start_server(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind((self.host, self.port))
        s.listen()
        logging.info(f"Master listening on {self.host}:{self.port}")
        while True:
            conn, addr = s.accept()
            logging.debug(f"New slave connected from {addr}. Total slaves: {len(self.slaves)}")
            with self.lock:
                self.slaves.append(conn)
                self.update_difficulty()
            threading.Thread(target=self.handle_slave, args=(conn, addr)).start()

    def send_to_all(self, message):
        with self.lock:
            for slave in self.slaves:
                try:
                    slave.sendall(json.dumps(message).encode())
                except Exception as e:
                    logging.error(f"Failed to send to slave: {e}")
                    self.slaves.remove(slave)

    def run(self):
        server_thread = threading.Thread(target=self.start_server)
        server_thread.daemon = True
        server_thread.start()

        try:
            while True:
                cmd = input("Enter command (1 or 2): ").strip()
                if cmd == '1':
                    username = input("Enter username: ")
                    password = input("Enter password: ")
                    self.credentials = {'username': username, 'password': password}
                    logging.info("Credentials saved.")
                elif cmd == '2':
                    if not self.credentials:
                        logging.warning("No credentials saved. Use command 1 first.")
                        continue
                    
                    # We declare this var because the difficulty will be change if some node has conneted or has disconned
                    difficulty = self.difficulty
                    message = {
                        'type': 'credentials',
                        'data': self.credentials,
                        'difficulty': difficulty
                    }
                    self.send_to_all(message)
                    logging.info("Sent credentials to slaves. Waiting for nonce...")
                    nonce = self.nonce_queue.get()
                    
                    with self.lock:
                        current_slaves = len(self.slaves)
                    with self.verf_lock:
                        self.verf_total = current_slaves
                        self.verf_resp = 0
                        self.verf_correct = 0
                        self.verf_progress = True

                    logging.info(f"Received nonce: {nonce}. Broadcasting to {current_slaves} slaves.")
                    self.credentials['nonce'] = nonce
                    self.send_to_all({
                        'type': 'verify',
                        'data': self.credentials,
                        'difficulty': difficulty
                    })
                else:
                    logging.warning("Invalid command.")
        except KeyboardInterrupt:
            logging.info("\nShutting down master.")
            self.send_to_all({
                'type': 'close_connection'
            })
            with self.lock:
                for slave in self.slaves:
                    slave.close()
            exit()

if __name__ == "__main__":
    master = MasterNode('localhost', 65432)
    master.run()