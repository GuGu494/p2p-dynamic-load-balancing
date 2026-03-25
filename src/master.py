import socket
import threading
from config import HOST, PORT, SERVER_UUID, DELIMITER
from processor import process_message

def handle_worker(conn, addr):
    print(f"[+] Worker conectado: {addr}")
    buffer = ""
    with conn:
        while True:
            try:
                data = conn.recv(1024).decode('utf-8')
                if not data: break
                
                buffer += data
                while DELIMITER in buffer:
                    line, buffer = buffer.split(DELIMITER, 1)
                    if line.strip():
                        process_message(line, conn)
            except ConnectionResetError:
                break
    print(f"[-] Worker desconectado: {addr}")

def start_master():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((HOST, PORT))
    server.listen()
    server.settimeout(1.0)
    
    print(f"[*] Servidor Master rodando na porta {PORT}")
    print(f"[*] UUID: {SERVER_UUID}")
    print("-" * 30)

    try:
        while True:
            try:
                conn, addr = server.accept()
                thread = threading.Thread(target=handle_worker, args=(conn, addr), daemon=True)
                thread.start()
            except socket.timeout:
                pass
    except KeyboardInterrupt:
        print("\n[!] Ctrl+C recebido. Desligando servidor...")
    finally:
        server.close()

if __name__ == "__main__":
    start_master()