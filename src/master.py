import os
import ssl
import socket
import threading
import json
import time
import sys
import datetime
import psutil
from processor import processar_requisicao_worker, parse_mensagem, FILA_TAREFAS, gerar_request_id, validar_campos_obrigatorios, CAMPOS_OBRIGATORIOS, fila_lock
import config
import processor

WORKERS_ATIVOS = {}            
LENT_WORKERS = {}              
BORROWED_WORKERS = {}          
PENDING_WORKER_COMMANDS = {}   
BORROWED_WORKER_TASKS = {}     

TASKS_COMPLETED = 0
TASKS_FAILED = 0
_tasks_lock = threading.Lock()

_start_time = time.time()
_lock = threading.Lock()

SUPERVISOR_HOST = "nuted-ia.dev"
SUPERVISOR_PORT = 443
SUPERVISOR_INTERVAL = 10  

def log_estado_workers():
    locais = [w for w in WORKERS_ATIVOS if w not in BORROWED_WORKERS and w not in LENT_WORKERS]
    config.logger.info(
        f"[ESTADO] Workers Locais: {len(locais)} | "
        f"Emprestados (de nos): {len(LENT_WORKERS)} | "
        f"Emprestados (para nos): {len(BORROWED_WORKERS)} | "
        f"Total Ativos: {len(WORKERS_ATIVOS)}"
    )

def construir_payload_metricas():
    try:
        uptime_seconds = int(time.time() - psutil.boot_time())
    except Exception:
        uptime_seconds = int(time.time() - _start_time)

    try:
        load1, load5, _ = psutil.getloadavg()
    except Exception:
        load1, load5 = 0.0, 0.0

    try:
        cpu_percent = psutil.cpu_percent(interval=None)
        cpu_logical = psutil.cpu_count(logical=True) or 1
        cpu_physical = psutil.cpu_count(logical=False) or 1
    except Exception:
        cpu_percent, cpu_logical, cpu_physical = 0.0, 1, 1

    try:
        mem = psutil.virtual_memory()
        mem_total_mb    = mem.total    // (1024 * 1024)
        mem_avail_mb    = mem.available // (1024 * 1024)
        mem_percent     = mem.percent
        mem_used_mb     = mem.used     // (1024 * 1024)
    except Exception:
        mem_total_mb, mem_avail_mb, mem_percent, mem_used_mb = 0, 0, 0.0, 0

    try:
        disk = psutil.disk_usage('/')
        disk_total_gb   = round(disk.total / (1024 ** 3), 1)
        disk_free_gb    = round(disk.free  / (1024 ** 3), 1)
        disk_percent    = disk.percent
    except Exception:
        disk_total_gb, disk_free_gb, disk_percent = 0.0, 0.0, 0.0

    with _lock:
        workers_total        = len(WORKERS_ATIVOS)
        workers_borrowed_out = len(LENT_WORKERS)    
        workers_borrowed_in  = len(BORROWED_WORKERS) 
        workers_home         = workers_total - workers_borrowed_in

        borrowed_list = (
            [{"direction": "out", "peer_uuid": peer_id}
             for peer_id in LENT_WORKERS.values()]
            +
            [{"direction": "in",  "peer_uuid": addr.split(":")[0]}
             for addr in BORROWED_WORKERS.values()]
        )

        neighbors_status = [
            {
                "server_uuid": n["id"],
                "status": "available",
                "last_heartbeat": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
            }
            for n in config.NEIGHBORS
        ]

    with fila_lock:
        tasks_pending = len(processor.FILA_TAREFAS)

    with _tasks_lock:
        tasks_completed = TASKS_COMPLETED
        tasks_failed    = TASKS_FAILED

    tasks_running           = min(tasks_pending, max(workers_total, 1))
    workers_idle            = max(0, workers_total - tasks_running)
    workers_available_cap   = workers_idle

    now_iso = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    payload = {
        "server_uuid":     config.SERVER_UUID,
        "hostname":        f"{config.SERVER_UUID}.local",
        "role":            "master",
        "task":            "performance_report",
        "timestamp":       now_iso,
        "message_id":      gerar_request_id(),
        "payload_version": "sprint4-monitor",
        "performance": {
            "system": {
                "uptime_seconds":   uptime_seconds,
                "load_average_1m":  round(load1, 2),
                "load_average_5m":  round(load5, 2),
                "cpu": {
                    "usage_percent":  cpu_percent,
                    "count_logical":  cpu_logical,
                    "count_physical": cpu_physical
                },
                "memory": {
                    "total_mb":     mem_total_mb,
                    "available_mb": mem_avail_mb,
                    "percent_used": mem_percent,
                    "memory_used":  mem_used_mb
                },
                "disk": {
                    "total_gb":    disk_total_gb,
                    "free_gb":     disk_free_gb,
                    "percent_used": disk_percent
                }
            },
            "farm_state": {
                "workers": {
                    "total_registered":           workers_total,
                    "workers_utilization":     tasks_running,
                    "workers_alive":           workers_total,
                    "workers_idle":            workers_idle,
                    "workers_borrowed":        workers_borrowed_out,
                    "workers_received":        workers_borrowed_in,
                    "workers_failed":          0,
                    "workers_home":            workers_home,
                    "workers_available_capacity": workers_available_cap,
                    "borrowed_workers":        borrowed_list
                },
                "tasks": {
                    "tasks_pending":       tasks_pending,
                    "tasks_running":       tasks_running,
                    "tasks_completed":     tasks_completed,
                    "tasks_failed":        tasks_failed,
                    "oldest_task_age_s":   0
                }
            },
            "config_thresholds": {
                "max_task":            config.SATURATION_THRESHOLD,
                "warn_cpu_percent":    85,
                "warn_memory_percent": 85,
                "release_task":        config.RELEASE_THRESHOLD
            },
            "neighbors": neighbors_status
        }
    }
    return payload

def enviar_metricas_supervisor():
    try:
        psutil.cpu_percent(interval=None)
    except Exception:
        pass

    config.logger.info(f"[Sprint4] Thread de métricas iniciada. Enviando a cada {SUPERVISOR_INTERVAL}s para {SUPERVISOR_HOST}:{SUPERVISOR_PORT}")

    while True:
        time.sleep(SUPERVISOR_INTERVAL)
        try:
            payload = construir_payload_metricas()
            dados   = (json.dumps(payload) + "\n").encode("utf-8")

            context = ssl.create_default_context()
            with socket.create_connection((SUPERVISOR_HOST, SUPERVISOR_PORT), timeout=8) as raw_sock:
                with context.wrap_socket(raw_sock, server_hostname=SUPERVISOR_HOST) as tls_sock:
                    tls_sock.sendall(dados)

            config.logger.info(
                f"[Sprint4] Métricas enviadas | tasks_pending={payload['performance']['farm_state']['tasks']['tasks_pending']} | "
                f"workers_ativos={payload['performance']['farm_state']['workers']['total_registered']} | "
                f"cpu={payload['performance']['system']['cpu']['usage_percent']}%"
            )

        except ssl.SSLError as e:
            config.logger.warning(f"[Sprint4] Erro TLS ao enviar métricas: {e}")
        except socket.timeout:
            config.logger.warning(f"[Sprint4] Timeout ao conectar no supervisor ({SUPERVISOR_HOST}:{SUPERVISOR_PORT})")
        except ConnectionRefusedError:
            config.logger.warning(f"[Sprint4] Supervisor recusou conexão. Tentará novamente em {SUPERVISOR_INTERVAL}s")
        except Exception as e:
            config.logger.warning(f"[Sprint4] Falha ao enviar métricas: {e}")

def handle_client(conn, addr):
    with conn:
        try:
            data = ""
            while True:
                chunk = conn.recv(1024).decode()
                if not chunk:
                    break
                data += chunk

                if config.DELIMITER in data:
                    keep_open = False
                    mensagens = data.split(config.DELIMITER)
                    for msg_str in mensagens[:-1]:
                        msg = parse_mensagem(msg_str)
                        if not msg:
                            continue

                        if msg.get("type") == "request_help":
                            payload = msg.get("payload", {})
                            if not validar_campos_obrigatorios(payload, CAMPOS_OBRIGATORIOS["request_help"], "request_help"):
                                continue
                            master_solicitante_id = payload['master_id']
                            workers_needed        = payload.get('workers_needed', 1)
                            request_id            = msg.get("request_id")

                            config.logger.info(
                                f"[P2P][RECV] type=request_help | request_id={request_id} | "
                                f"De {master_solicitante_id} (precisa de {workers_needed} workers)"
                            )

                            with _lock:
                                workers_disponiveis = [
                                    wid for wid in WORKERS_ATIVOS
                                    if wid not in LENT_WORKERS and wid not in BORROWED_WORKERS
                                ]
                                with fila_lock:
                                    carga_local = len(FILA_TAREFAS)

                            if carga_local >= config.SATURATION_THRESHOLD:
                                reason = "high_load"
                            elif not workers_disponiveis:
                                reason = "no_workers_available"
                            else:
                                reason = None

                            if reason:
                                resposta = {
                                    "type":       "response_rejected",
                                    "request_id": request_id,
                                    "payload":    {"reason": reason}
                                }
                                config.logger.info(
                                    f"[P2P][SEND] type=response_rejected | request_id={request_id} | "
                                    f"Recusamos o pedido de {master_solicitante_id}. Motivo: {reason}"
                                )
                                conn.sendall((json.dumps(resposta) + config.DELIMITER).encode())
                            else:
                                workers_a_emprestar = workers_disponiveis[:min(workers_needed, len(workers_disponiveis))]

                                master_solicitante_address = None
                                for neighbor in config.NEIGHBORS:
                                    if neighbor.get("id") == master_solicitante_id:
                                        master_solicitante_address = f"{neighbor['host']}:{neighbor['port']}"
                                        break
                                if not master_solicitante_address:
                                    master_solicitante_address = f"{addr[0]}:{config.PORT}"

                                resposta = {
                                    "type":       "response_accepted",
                                    "request_id": request_id,
                                    "payload": {
                                        "workers_offered": len(workers_a_emprestar),
                                        "worker_details": [
                                            {"id": wid, "address": f"{config.HOST}:{config.PORT}"}
                                            for wid in workers_a_emprestar
                                        ]
                                    }
                                }
                                config.logger.info(
                                    f"[P2P][SEND] type=response_accepted | request_id={request_id} | "
                                    f"Emprestando {workers_a_emprestar}"
                                )
                                conn.sendall((json.dumps(resposta) + config.DELIMITER).encode())

                                for wid in workers_a_emprestar:
                                    LENT_WORKERS[wid] = master_solicitante_id
                                    req_id_redir = gerar_request_id()
                                    PENDING_WORKER_COMMANDS[wid] = {
                                        "type":       "command_redirect",
                                        "request_id": req_id_redir,
                                        "payload":    {"new_master_address": master_solicitante_address}
                                    }
                                    config.logger.info(
                                        f"[P2P][SEND] type=command_redirect | request_id={req_id_redir} | "
                                        f"Enfileirado para Worker {wid}"
                                    )
                                log_estado_workers()
                            continue

                        if msg.get("type") == "register_temporary_worker":
                            payload = msg.get("payload", {})
                            if not validar_campos_obrigatorios(payload, CAMPOS_OBRIGATORIOS["register_temporary_worker"], "register_temporary_worker"):
                                continue
                            worker_id_temp = payload['worker_id']
                            master_origem  = payload['original_master_address']
                            with _lock:
                                BORROWED_WORKERS[worker_id_temp] = master_origem
                                WORKERS_ATIVOS[worker_id_temp]   = addr
                                log_estado_workers()
                            config.logger.info(
                                f"[P2P][RECV] type=register_temporary_worker | request_id={msg.get('request_id')} | "
                                f"Worker emprestado registrado: {worker_id_temp} (origem: {master_origem})"
                            )
                            keep_open = True
                            continue

                        if msg.get("type") == "notify_worker_returned":
                            payload = msg.get("payload", {})
                            if not validar_campos_obrigatorios(payload, CAMPOS_OBRIGATORIOS["notify_worker_returned"], "notify_worker_returned"):
                                continue
                            worker_devolvido = payload['worker_id']
                            with _lock:
                                LENT_WORKERS.pop(worker_devolvido, None)
                                log_estado_workers()
                            config.logger.info(
                                f"[P2P][RECV] type=notify_worker_returned | request_id={msg.get('request_id')} | "
                                f"Worker {worker_devolvido} devolvido pelo vizinho e reintegrado à farm."
                            )
                            continue

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
                            config.logger.info(
                                f"[Master] Worker EMPRESTADO {worker_id} "
                                f"(origem: {msg['SERVER_UUID']}) se reportou."
                            )

                        if msg.get("WORKER") == "ALIVE":
                            command = None
                            with _lock:
                                if worker_id in PENDING_WORKER_COMMANDS:
                                    command = PENDING_WORKER_COMMANDS.pop(worker_id)
                            if command:
                                config.logger.info(
                                    f"[Master] Enviando comando pendente ({command['type']}) "
                                    f"para Worker {worker_id}"
                                )
                                conn.sendall((json.dumps(command) + config.DELIMITER).encode())
                                continue

                        is_borrowed = worker_id in BORROWED_WORKERS
                        if is_borrowed and msg.get("WORKER") == "ALIVE":
                            BORROWED_WORKER_TASKS[worker_id] = BORROWED_WORKER_TASKS.get(worker_id, 0) + 1

                        if msg.get("STATUS") in ("OK", "NOK"):
                            with _tasks_lock:
                                if msg["STATUS"] == "OK":
                                    global TASKS_COMPLETED
                                    TASKS_COMPLETED += 1
                                else:
                                    global TASKS_FAILED
                                    TASKS_FAILED += 1

                        resposta = processar_requisicao_worker(msg, worker_id, is_borrowed=is_borrowed)
                        if resposta:
                            conn.sendall((json.dumps(resposta) + config.DELIMITER).encode())
                            keep_open = resposta.get("TASK") == "QUERY"

                    data = mensagens[-1]
                    if not keep_open:
                        break

        except Exception as e:
            config.logger.error(f"[Master] Erro no handler do cliente {addr}: {e}")

def enviar_notify_worker_returned(original_master_address, worker_id):
    try:
        host, port = original_master_address.split(":")
        port = int(port)
        config.logger.info(
            f"[P2P][SEND] type=notify_worker_returned | "
            f"Conectando a original Master {original_master_address} para notificar retorno de {worker_id}..."
        )
        with socket.create_connection((host, port), timeout=config.NEGOTIATION_TIMEOUT) as s:
            notif = {
                "type":       "notify_worker_returned",
                "request_id": gerar_request_id(),
                "payload":    {"worker_id": worker_id}
            }
            s.sendall((json.dumps(notif) + config.DELIMITER).encode())
            config.logger.info(
                f"[P2P][SEND] type=notify_worker_returned | request_id={notif['request_id']} | "
                f"Enviado com sucesso para {worker_id}"
            )
    except Exception as e:
        config.logger.error(f"[P2P] Falha ao enviar notify_worker_returned para {original_master_address}: {e}")

def solicitar_ajuda_vizinhos(workers_needed):
    for neighbor in config.NEIGHBORS:
        if workers_needed <= 0:
            break
        try:
            config.logger.info(
                f"[P2P] Tentando conectar ao Master Vizinho {neighbor['id']} "
                f"({neighbor['host']}:{neighbor['port']})..."
            )
            with socket.create_connection((neighbor["host"], neighbor["port"]), timeout=config.NEGOTIATION_TIMEOUT) as s:
                pedido = {
                    "type":       "request_help",
                    "request_id": gerar_request_id(),
                    "payload": {
                        "master_id":      config.SERVER_UUID,
                        "current_load":   len(FILA_TAREFAS),
                        "capacity":       config.CAPACITY,
                        "workers_needed": workers_needed
                    }
                }
                s.sendall((json.dumps(pedido) + config.DELIMITER).encode())
                config.logger.info(
                    f"[P2P][SEND] type=request_help | request_id={pedido['request_id']} | "
                    f"Para {neighbor['id']}"
                )

                data = ""
                while config.DELIMITER not in data:
                    chunk = s.recv(1024).decode()
                    if not chunk:
                        break
                    data += chunk

                if data:
                    resposta = parse_mensagem(data.split(config.DELIMITER)[0])
                    if resposta and resposta.get("type") == "response_accepted":
                        offered = resposta["payload"].get("workers_offered", 0)
                        details = resposta["payload"].get("worker_details", [])
                        config.logger.info(
                            f"[P2P][RECV] type=response_accepted | request_id={resposta.get('request_id')} | "
                            f"Ofereceu {offered} workers. Detalhes: {details}"
                        )
                        with _lock:
                            for worker in details:
                                wid = worker["id"]
                                BORROWED_WORKERS[wid] = f"{neighbor['host']}:{neighbor['port']}"
                        log_estado_workers()
                        workers_needed -= offered
                    elif resposta and resposta.get("type") == "response_rejected":
                        config.logger.info(
                            f"[P2P][RECV] type=response_rejected | request_id={resposta.get('request_id')} | "
                            f"Vizinho recusou. Motivo: {resposta.get('payload', {}).get('reason')}"
                        )
        except Exception:
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
                        req_id_rel = gerar_request_id()
                        PENDING_WORKER_COMMANDS[wid] = {
                            "type":       "command_release",
                            "request_id": req_id_rel,
                            "payload":    {"original_master_address": original_master}
                        }
                        config.logger.info(
                            f"[P2P][SEND] type=command_release | request_id={req_id_rel} | "
                            f"Enfileirado para Worker {wid}"
                        )
                        BORROWED_WORKERS.pop(wid, None)
                        log_estado_workers()
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
    time.sleep(5)
    while True:
        time.sleep(8)
        with _lock:
            with fila_lock:
                if len(processor.FILA_TAREFAS) < 15:
                    novas = [random.choice(tarefas_exemplos) for _ in range(random.randint(1, 3))]
                    processor.FILA_TAREFAS.extend(novas)
                    config.logger.info(
                        f"[Gerador] Injetadas {len(novas)} novas tarefas. "
                        f"Fila total: {len(processor.FILA_TAREFAS)}"
                    )

def start_master():
    threading.Thread(target=monitor_carga,            daemon=True).start()
    threading.Thread(target=gerador_tarefas,            daemon=True).start()
    threading.Thread(target=enviar_metricas_supervisor, daemon=True).start()  

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