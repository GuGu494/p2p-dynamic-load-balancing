import os
import socket
import threading
import json
import time
import sys
from processor import processar_requisicao_worker, parse_mensagem, FILA_TAREFAS, gerar_request_id, validar_campos_obrigatorios, CAMPOS_OBRIGATORIOS, fila_lock
import config
import processor

# State tracking (thread-safe)
WORKERS_ATIVOS = {}            # maps worker_id -> addr (connection client address)
LENT_WORKERS = {}              # maps worker_id -> borrower_master_id
BORROWED_WORKERS = {}          # maps worker_id -> original_master_address
PENDING_WORKER_COMMANDS = {}   # maps worker_id -> pending command dict

BORROWED_WORKER_TASKS = {}     # tracks tasks executed per borrowed worker

_lock = threading.Lock()

def log_estado_workers():
    """Exibe contadores de workers a cada mudanca de estado."""
    locais = [w for w in WORKERS_ATIVOS if w not in BORROWED_WORKERS and w not in LENT_WORKERS]
    config.logger.info(
        f"[ESTADO] Workers Locais: {len(locais)} | "
        f"Emprestados (de nos): {len(LENT_WORKERS)} | "
        f"Emprestados (para nos): {len(BORROWED_WORKERS)} | "
        f"Total Ativos: {len(WORKERS_ATIVOS)}"
    )

def handle_client(conn, addr):
    with conn:
        try:
            data = ""
            while True:
                chunk = conn.recv(1024).decode()
                if not chunk: break
                data += chunk
                
                if config.DELIMITER in data:
                    keep_open = False
                    mensagens = data.split(config.DELIMITER)
                    for msg_str in mensagens[:-1]:
                        msg = parse_mensagem(msg_str)
                        if not msg: continue
                        
                        # 1. request_help message handling (neighbor requests workers from us)
                        if msg.get("type") == "request_help":
                            payload = msg.get("payload", {})
                            if not validar_campos_obrigatorios(payload, CAMPOS_OBRIGATORIOS["request_help"], "request_help"):
                                continue
                            master_solicitante_id = payload['master_id']
                            workers_needed = payload.get('workers_needed', 1)
                            request_id = msg.get("request_id")
                            
                            config.logger.info(f"[P2P][RECV] type=request_help | request_id={request_id} | De {master_solicitante_id} (precisa de {workers_needed} workers)")
                            
                            with _lock:
                                # Determine available local workers (not lent, not borrowed)
                                workers_disponiveis = [
                                    wid for wid in WORKERS_ATIVOS 
                                    if wid not in LENT_WORKERS and wid not in BORROWED_WORKERS
                                ]
                                with fila_lock:
                                    carga_local = len(FILA_TAREFAS)
                                
                                # Hysteresis logic for rejection
                                if carga_local >= config.SATURATION_THRESHOLD:
                                    reason = "high_load"
                                elif not workers_disponiveis:
                                    reason = "no_workers_available"
                                else:
                                    reason = None
                                
                                if reason:
                                    resposta = {
                                        "type": "response_rejected",
                                        "request_id": request_id,
                                        "payload": {"reason": reason}
                                    }
                                    config.logger.info(f"[P2P][SEND] type=response_rejected | request_id={request_id} | Recusamos o pedido de {master_solicitante_id}. Motivo: {reason}")
                                    conn.sendall((json.dumps(resposta) + config.DELIMITER).encode())
                                else:
                                    # Lend workers
                                    workers_a_emprestar = workers_disponiveis[:min(workers_needed, len(workers_disponiveis))]
                                    
                                    # Lookup master address in config.NEIGHBORS
                                    master_solicitante_address = None
                                    for neighbor in config.NEIGHBORS:
                                        if neighbor.get("id") == master_solicitante_id:
                                            master_solicitante_address = f"{neighbor['host']}:{neighbor['port']}"
                                            break
                                    if not master_solicitante_address:
                                        master_solicitante_address = f"{addr[0]}:{config.PORT}"
                                        
                                    resposta = {
                                        "type": "response_accepted",
                                        "request_id": request_id,
                                        "payload": {
                                            "workers_offered": len(workers_a_emprestar),
                                            "worker_details": [{"id": wid, "address": f"{config.HOST}:{config.PORT}"} for wid in workers_a_emprestar]
                                        }
                                    }
                                    config.logger.info(f"[P2P][SEND] type=response_accepted | request_id={request_id} | Emprestando {workers_a_emprestar}")
                                    conn.sendall((json.dumps(resposta) + config.DELIMITER).encode())
                                    
                                    # Queue redirect commands
                                    for wid in workers_a_emprestar:
                                        LENT_WORKERS[wid] = master_solicitante_id
                                        req_id_redir = gerar_request_id()
                                        PENDING_WORKER_COMMANDS[wid] = {
                                            "type": "command_redirect",
                                            "request_id": req_id_redir,
                                            "payload": {"new_master_address": master_solicitante_address}
                                        }
                                        config.logger.info(f"[P2P][SEND] type=command_redirect | request_id={req_id_redir} | Enfileirado para Worker {wid}")
                                    log_estado_workers()
                            continue
                            
                        # 2. register_temporary_worker message handling
                        if msg.get("type") == "register_temporary_worker":
                            payload = msg.get("payload", {})
                            if not validar_campos_obrigatorios(payload, CAMPOS_OBRIGATORIOS["register_temporary_worker"], "register_temporary_worker"):
                                continue
                            worker_id_temp = payload['worker_id']
                            master_origem = payload['original_master_address']
                            with _lock:
                                BORROWED_WORKERS[worker_id_temp] = master_origem
                                WORKERS_ATIVOS[worker_id_temp] = addr
                                log_estado_workers()
                            config.logger.info(f"[P2P][RECV] type=register_temporary_worker | request_id={msg.get('request_id')} | Worker emprestado registrado: {worker_id_temp} (origem: {master_origem})")
                            keep_open = True
                            continue
                            
                        # 3. notify_worker_returned message handling
                        if msg.get("type") == "notify_worker_returned":
                            payload = msg.get("payload", {})
                            if not validar_campos_obrigatorios(payload, CAMPOS_OBRIGATORIOS["notify_worker_returned"], "notify_worker_returned"):
                                continue
                            worker_devolvido = payload['worker_id']
                            with _lock:
                                LENT_WORKERS.pop(worker_devolvido, None)
                                log_estado_workers()
                            config.logger.info(f"[P2P][RECV] type=notify_worker_returned | request_id={msg.get('request_id')} | Worker {worker_devolvido} devolvido pelo vizinho e reintegrado à farm.")
                            continue
                            
                        # 4. Standard worker handling
                        # Validate worker messages
                        if "WORKER" in msg:
                            if not validar_campos_obrigatorios(msg, ["WORKER", "WORKER_UUID"], "worker_alive"):
                                continue
                        elif "STATUS" in msg:
                            if not validar_campos_obrigatorios(msg, ["STATUS", "TASK", "WORKER_UUID"], "worker_status"):
                                continue

                        worker_id = msg.get("WORKER_UUID", "Desconhecido")
                        with _lock:
                            WORKERS_ATIVOS[worker_id] = addr
                            if msg.get("WORKER") == "ALIVE" and worker_id not in BORROWED_WORKERS and worker_id not in LENT_WORKERS:
                                log_estado_workers()
                            
                        if msg.get("SERVER_UUID"):
                            config.logger.info(f"[Master] Worker EMPRESTADO {worker_id} (origem: {msg['SERVER_UUID']}) se reportou.")
                            
                        # If worker sends ALIVE, check if there is a pending command
                        if msg.get("WORKER") == "ALIVE":
                            command = None
                            with _lock:
                                if worker_id in PENDING_WORKER_COMMANDS:
                                    command = PENDING_WORKER_COMMANDS.pop(worker_id)
                            if command:
                                config.logger.info(f"[Master] Enviando comando pendente ({command['type']}) para Worker {worker_id}")
                                conn.sendall((json.dumps(command) + config.DELIMITER).encode())
                                continue
                                
                        is_borrowed = worker_id in BORROWED_WORKERS
                        if is_borrowed and msg.get("WORKER") == "ALIVE":
                            BORROWED_WORKER_TASKS[worker_id] = BORROWED_WORKER_TASKS.get(worker_id, 0) + 1
                        resposta = processar_requisicao_worker(msg, worker_id, is_borrowed=is_borrowed)
                        if resposta:
                            conn.sendall((json.dumps(resposta) + config.DELIMITER).encode())
                            if resposta.get("TASK") == "QUERY":
                                keep_open = True
                            else:
                                keep_open = False
                                
                    data = mensagens[-1]
                    if not keep_open:
                        break
        except Exception as e:
            config.logger.error(f"[Master] Erro no handler do cliente {addr}: {e}")

def enviar_notify_worker_returned(original_master_address, worker_id):
    try:
        host, port = original_master_address.split(":")
        port = int(port)
        config.logger.info(f"[P2P][SEND] type=notify_worker_returned | Conectando a original Master {original_master_address} para notificar retorno de {worker_id}...")
        with socket.create_connection((host, port), timeout=config.NEGOTIATION_TIMEOUT) as s:
            notif = {
                "type": "notify_worker_returned",
                "request_id": gerar_request_id(),
                "payload": {"worker_id": worker_id}
            }
            s.sendall((json.dumps(notif) + config.DELIMITER).encode())
            config.logger.info(f"[P2P][SEND] type=notify_worker_returned | request_id={notif['request_id']} | Enviado com sucesso para {worker_id}")
    except Exception as e:
        config.logger.error(f"[P2P] Falha ao enviar notify_worker_returned para {original_master_address}: {e}")

def solicitar_ajuda_vizinhos(workers_needed):
    for neighbor in config.NEIGHBORS:
        if workers_needed <= 0:
            break
        try:
            config.logger.info(f"[P2P] Tentando conectar ao Master Vizinho {neighbor['id']} ({neighbor['host']}:{neighbor['port']})...")
            with socket.create_connection((neighbor["host"], neighbor["port"]), timeout=config.NEGOTIATION_TIMEOUT) as s:
                pedido = {
                    "type": "request_help",
                    "request_id": gerar_request_id(),
                    "payload": {
                        "master_id": config.SERVER_UUID,
                        "current_load": len(FILA_TAREFAS),
                        "capacity": config.CAPACITY,
                        "workers_needed": workers_needed
                    }
                }
                s.sendall((json.dumps(pedido) + config.DELIMITER).encode())
                config.logger.info(f"[P2P][SEND] type=request_help | request_id={pedido['request_id']} | Para {neighbor['id']}")
                
                # Receive response
                data = ""
                while config.DELIMITER not in data:
                    chunk = s.recv(1024).decode()
                    if not chunk: break
                    data += chunk
                    
                if data:
                    resposta = parse_mensagem(data.split(config.DELIMITER)[0])
                    if resposta and resposta.get("type") == "response_accepted":
                        offered = resposta["payload"].get("workers_offered", 0)
                        details = resposta["payload"].get("worker_details", [])
                        config.logger.info(f"[P2P][RECV] type=response_accepted | request_id={resposta.get('request_id')} | Ofereceu {offered} workers. Detalhes: {details}")
                        with _lock:
                            for worker in details:
                                wid = worker["id"]
                                BORROWED_WORKERS[wid] = f"{neighbor['host']}:{neighbor['port']}"
                            log_estado_workers()
                        workers_needed -= offered
                    elif resposta and resposta.get("type") == "response_rejected":
                        config.logger.info(f"[P2P][RECV] type=response_rejected | request_id={resposta.get('request_id')} | Vizinho recusou. Motivo: {resposta.get('payload', {}).get('reason')}")
        except Exception as e:
            config.logger.error(f"[P2P] Falha ao contatar vizinho {neighbor['id']}: Timeout/Offline")

def monitor_carga():
    while True:
        time.sleep(config.LOAD_CHECK_INTERVAL)
        
        with _lock:
            stale = [wid for wid in PENDING_WORKER_COMMANDS if wid not in WORKERS_ATIVOS]
            for wid in stale:
                config.logger.warning(f"[Master] Limpando comando pendente para Worker inativo: {wid}")
                PENDING_WORKER_COMMANDS.pop(wid)
                
        with fila_lock:
            carga = len(FILA_TAREFAS)
            
        if carga > config.SATURATION_THRESHOLD:
            config.logger.info(f"[ALERTA] Saturação Crítica ({carga} tarefas)!")
            with _lock:
                # Ask for workers to bring load down to SATURATION_THRESHOLD
                with fila_lock:
                    workers_needed = len(FILA_TAREFAS) - config.SATURATION_THRESHOLD
            if workers_needed > 0:
                solicitar_ajuda_vizinhos(workers_needed)
                
        elif carga < config.RELEASE_THRESHOLD:
            with _lock:
                borrowed_list = list(BORROWED_WORKERS.items())
                
            if borrowed_list:
                config.logger.info(f"[P2P] Carga normalizada ({carga} tarefas). Devolvendo workers...")
                for wid, original_master in borrowed_list:
                    config.logger.info(
                        f"[LIFECYCLE] Worker {wid}: emprestimo -> registro -> "
                        f"{BORROWED_WORKER_TASKS.get(wid, 0)} tarefas executadas -> devolucao"
                    )
                    BORROWED_WORKER_TASKS.pop(wid, None)
                    with _lock:
                        # Queue command_release for worker
                        req_id_rel = gerar_request_id()
                        PENDING_WORKER_COMMANDS[wid] = {
                            "type": "command_release",
                            "request_id": req_id_rel,
                            "payload": {"original_master_address": original_master}
                        }
                        config.logger.info(f"[P2P][SEND] type=command_release | request_id={req_id_rel} | Enfileirado para Worker {wid}")
                        BORROWED_WORKERS.pop(wid, None)
                        log_estado_workers()
                    # Notify lender
                    enviar_notify_worker_returned(original_master, wid)

def gerador_tarefas():
    if os.environ.get("P2P_DISABLE_GENERATOR") == "true":
        config.logger.info("[Gerador] Desabilitado via variável de ambiente.")
        return
    import random
    tarefas_exemplos = [
        "Compilar_Kernel", "Processar_Pagamentos", "Otimizar_Rotas",
        "Analisar_Vulnerabilidades", "Treinar_Rede_Neural", "Sincronizar_Bancos"
    ]
    # Wait initially before injecting tasks
    time.sleep(5)
    while True:
        time.sleep(8)
        with _lock:
            with fila_lock:
                # Only generate tasks if we are below saturation to avoid infinite task accumulation
                if len(processor.FILA_TAREFAS) < 15:
                    novas = [random.choice(tarefas_exemplos) for _ in range(random.randint(1, 3))]
                    processor.FILA_TAREFAS.extend(novas)
                    config.logger.info(f"[Gerador] Injetadas {len(novas)} novas tarefas. Fila total: {len(processor.FILA_TAREFAS)}")

def start_master():
    threading.Thread(target=monitor_carga, daemon=True).start()
    threading.Thread(target=gerador_tarefas, daemon=True).start()
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(('0.0.0.0', config.PORT))
        s.listen()
        config.logger.info(f"=== Master Server na porta {config.PORT} (Limite: {config.SATURATION_THRESHOLD}) ===")
        config.logger.info(f"[Master] OK - ONLINE | Aguardando conexões em 0.0.0.0:{config.PORT}")
        config.logger.info(f"[Master] Pressione Ctrl+C para encerrar.")
        try:
            while True:
                conn, addr = s.accept()
                threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()
        except KeyboardInterrupt:
            config.logger.info(f"[Master] Encerrando servidor...")
            config.logger.info(f"[Master] OFFLINE.")
            sys.exit(0)

if __name__ == "__main__":
    start_master()