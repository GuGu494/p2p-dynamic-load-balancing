import socket
import json
import time
import random
import uuid
import sys
import threading
import config

current_master_addr = (config.HOST, config.PORT)

def heartbeat_loop():
    """Thread separada que envia HEARTBEAT periodicamente para o Master atual."""
    global current_master_addr
    while True:
        try:
            host, port = current_master_addr
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(5.0)
                s.connect((host, port))
                hb = {"SERVER_UUID": config.SERVER_UUID, "TASK": "HEARTBEAT"}
                s.sendall((json.dumps(hb) + config.DELIMITER).encode())
                
                data = ""
                while config.DELIMITER not in data:
                    chunk = s.recv(1024).decode()
                    if not chunk: break
                    data += chunk
                    
                if data:
                    try:
                        resp = json.loads(data.split(config.DELIMITER)[0])
                        if resp.get("RESPONSE") == "ALIVE":
                            config.logger.info(f"[Worker] Heartbeat OK - Master {resp.get('SERVER_UUID')} esta ALIVE")
                    except json.JSONDecodeError:
                        pass
        except Exception as e:
            config.logger.warning(f"[Worker] Heartbeat falhou: {e}")
            
        time.sleep(config.HEARTBEAT_INTERVAL)

def start_worker():
    global current_master_addr
    host_atual = config.HOST
    porta_atual = config.PORT
    master_original = f"{config.HOST}:{config.PORT}"
    is_borrowed = False

    config.logger.info(f"[Worker] Iniciando Worker {config.WORKER_UUID}...")
    threading.Thread(target=heartbeat_loop, daemon=True).start()
    config.logger.info(f"[Worker] Conectando ao Master em {config.HOST}:{config.PORT}")
    config.logger.info(f"[Worker] Pressione Ctrl+C para encerrar.")

    try:
        while True:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(5.0)
                    s.connect((host_atual, porta_atual))
                    
                    if is_borrowed:
                        req_temp = {
                            "type": "register_temporary_worker",
                            "request_id": str(uuid.uuid4()),
                            "payload": {"worker_id": config.WORKER_UUID, "original_master_address": master_original}
                        }
                        s.sendall((json.dumps(req_temp) + config.DELIMITER).encode())
                    
                    req = {"WORKER": "ALIVE", "WORKER_UUID": config.WORKER_UUID}
                    if is_borrowed:
                        req["SERVER_UUID"] = master_original
                        
                    s.sendall((json.dumps(req) + config.DELIMITER).encode())
                    
                    data = ""
                    while config.DELIMITER not in data:
                        chunk = s.recv(1024).decode()
                        if not chunk: break
                        data += chunk
                    
                    if data:
                        try:
                            resposta = json.loads(data.split(config.DELIMITER)[0])
                        except json.JSONDecodeError:
                            config.logger.error("[Worker] Erro ao decodificar resposta JSON do Master. Ignorando.")
                            continue
                            
                        if not isinstance(resposta, dict):
                            config.logger.error("[Worker] Resposta inválida (não é um dicionário). Ignorando.")
                            continue
                        
                        if resposta.get("type") == "command_redirect":
                            novo_endereco = resposta["payload"]["new_master_address"].split(":")
                            host_atual = novo_endereco[0]
                            porta_atual = int(novo_endereco[1]) if len(novo_endereco) > 1 else config.PORT
                            current_master_addr = (host_atual, porta_atual)
                            is_borrowed = True
                            config.logger.info(f"[Worker] Redirecionamento P2P recebido! Migrando para {host_atual}:{porta_atual}...")
                            continue
                            
                        elif resposta.get("type") == "command_release":
                            host_atual = config.HOST
                            porta_atual = config.PORT
                            current_master_addr = (host_atual, porta_atual)
                            is_borrowed = False
                            config.logger.info("[Worker] Fim do empréstimo. Retornando ao Master original.")
                            continue
                        
                        if resposta.get("TASK") == "QUERY":
                            config.logger.info(f"[Worker] Processando tarefa: {resposta.get('USER')}...")
                            time.sleep(random.randint(1, 3))
                            # Simular falha aleatoria (~10% chance)
                            status = "NOK" if random.random() < 0.1 else "OK"
                            ack_req = {"STATUS": status, "TASK": "QUERY", "WORKER_UUID": config.WORKER_UUID}
                            s.sendall((json.dumps(ack_req) + config.DELIMITER).encode())
                            config.logger.info(f"[Worker] Tarefa concluida com status: {status}")
                            
                            # Wait for ACK response from Master
                            ack_data = ""
                            while config.DELIMITER not in ack_data:
                                chunk = s.recv(1024).decode()
                                if not chunk: break
                                ack_data += chunk
                        elif resposta.get("TASK") == "NO_TASK":
                            time.sleep(config.HEARTBEAT_INTERVAL)

            except (socket.timeout, ConnectionRefusedError, ConnectionResetError, OSError) as e:
                config.logger.warning(f"[Worker] Erro de conexao ({e}).")
                if is_borrowed:
                    config.logger.info(
                        f"[Worker] Master emprestador ({host_atual}:{porta_atual}) caiu! "
                        f"Retornando ao Master original ({config.HOST}:{config.PORT})..."
                    )
                    host_atual = config.HOST
                    porta_atual = config.PORT
                    current_master_addr = (host_atual, porta_atual)
                    is_borrowed = False
                    time.sleep(2)
                else:
                    config.logger.info(f"[Worker] Aguardando reconexao em 5s...")
                    time.sleep(5)

    except KeyboardInterrupt:
        config.logger.info(f"[Worker] Encerrando Worker {config.WORKER_UUID}...")
        config.logger.info(f"[Worker] OFFLINE.")
        sys.exit(0)

if __name__ == "__main__":
    start_worker()