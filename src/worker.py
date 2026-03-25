import socket
import time
import json
from config import HOST, PORT, SERVER_UUID, HEARTBEAT_INTERVAL, DELIMITER

def start_worker():
    while True:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((HOST, PORT))
                buffer = ""
                print(f" Conectado ao Master ({HOST}:{PORT})")

                while True:
                    payload = {
                        "SERVER_UUID": SERVER_UUID,
                        "TASK": "HEARTBEAT"
                    }
                    
                    msg_str = json.dumps(payload) + DELIMITER
                    s.sendall(msg_str.encode('utf-8'))

                    data = s.recv(1024).decode('utf-8')
                    if not data:
                        raise ConnectionResetError
                    
                    buffer += data

                    while DELIMITER in buffer:
                        line, buffer = buffer.split(DELIMITER, 1)
                        if line.strip():
                            resp = json.loads(line)
                            if resp.get("RESPONSE") == "ALIVE":
                                print("[STATUS] ALIVE")

                    time.sleep(HEARTBEAT_INTERVAL)

        except (ConnectionRefusedError, ConnectionResetError, BrokenPipeError):
            print("[STATUS] OFFLINE - Aguardando reconexao...")
            time.sleep(5)

if __name__ == "__main__":
    start_worker()