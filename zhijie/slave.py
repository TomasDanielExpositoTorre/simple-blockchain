import socket
import json
import hashlib
import random
import threading
import logging
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # Log to console
        # logging.FileHandler('slave_node.log')  # Log to a file
    ]
)

class SlaveNode:
    def __init__(self, master_host, master_port):
        self.master_host = master_host
        self.master_port = master_port
        self.conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.stop_event = threading.Event()
        self.pause_event = threading.Event()
        self.current_job = None

    def connect_to_master(self):
        try:
            self.conn.connect((self.master_host, self.master_port))
            logging.info("Connected to master.")
        except Exception as e:
            logging.error(f"Connection failed: {e}")
            exit()

    def calculate_nonce(self, data, difficulty):
        self.stop_event.clear()
        target = '0' * difficulty
        logging.debug(f"Received data: {data}")
        logging.debug(f"Calculating nonce with difficulty {difficulty}...")
        while not self.stop_event.is_set():
            if self.pause_event.is_set():
                time.sleep(0.1)
                continue

            nonce = str(random.randint(0, 1000000000))
            data['nonce'] = nonce
            hash_str = hashlib.sha256(
                json.dumps(data, sort_keys=True).encode()
            ).hexdigest()
            logging.debug(f"Nonce: {nonce}, Hash: {hash_str}")
            if hash_str.startswith(target):
                message = {'type': 'nonce', 'value': nonce}
                try:
                    logging.info(f"Nonce founded. Sending to master: Nonce: {nonce}, Hash: {hash_str}.")
                    self.conn.sendall(json.dumps(message).encode())
                except Exception as e:
                    logging.error(f"Failed to send nonce: {e}")
                self.stop_event.set()
                return

    def handle_messages(self):
        while True:
            try:
                data = self.conn.recv(1024)
                if not data:
                    break
                try:
                    message = json.loads(data.decode())
                except json.JSONDecodeError:
                    logging.warning("Received invalid JSON data.")
                    continue

                if message['type'] == 'credentials':
                    if self.current_job and self.current_job.is_alive():
                        logging.debug("Stopping current job to start a new one.")
                        self.stop_event.set()
                        self.current_job.join()
                    
                    logging.debug(f"Received data: {message['data']}, difficulty: {message['difficulty']}.")
                    self.current_job = threading.Thread(
                        target=self.calculate_nonce,
                        args=(message['data'], message['difficulty'],)
                    )
                    self.current_job.start()

                elif message['type'] == 'verify':
                    if self.current_job and self.current_job.is_alive():
                        logging.debug("Stopping current job for verification.")
                        self.pause_event.set()
                    
                    logging.debug(f"Verify data: {message['data']}, difficulty: {message['difficulty']}.")
                    hash_str = hashlib.sha256(
                        json.dumps(message['data'], sort_keys=True).encode()
                    ).hexdigest()

                    result = hash_str.startswith('0' * message['difficulty'])
                    response = {
                        'type': 'verification',
                        'result': result
                    }
                    try:
                        self.conn.sendall(json.dumps(response).encode())
                    except Exception as e:
                        logging.error(f"Failed to send verification: {e}")
                    
                    # if the job was working, we need continue the job
                    self.pause_event.clear()
                elif message['type'] == 'close_connection':
                    logging.debug("Received close connection command from master.")
                    self.stop_event.set()
                    if self.current_job and self.current_job.is_alive():
                        logging.debug("Stopping current job.")
                        self.current_job.join()
                    self.conn.close()
                    return

            except Exception as e:
                logging.error(f"Error receiving data: {e}")
                break

    def run(self):
        self.connect_to_master()
        self.handle_messages()
        self.conn.close()

if __name__ == "__main__":
    slave = SlaveNode('localhost', 65432)
    try:
        slave.run()
    except KeyboardInterrupt:
        logging.info("Slave shutting down.")
        slave.conn.close()