import json
import uuid
import threading

import os
import config

if os.environ.get("P2P_EMPTY_TASKS") == "true":
    FILA_TAREFAS = []
else:
    num_tasks = int(os.environ.get("P2P_NUM_TASKS", 10))
    FILA_TAREFAS = ([
        "Compilar_Kernel", "Processar_Pagamentos", "Otimizar_Rotas",
        "Analisar_Vulnerabilidades", "Treinar_Rede_Neural", "Sincronizar_Bancos"
    ] * 5)[:num_tasks] 

_tarefas_concluidas_avisado = False

fila_lock = threading.Lock()

def gerar_request_id():
    return str(uuid.uuid4())

TIPOS_MENSAGEM_VALIDOS = {
    "request_help", "response_accepted", "response_rejected",
    "command_redirect", "register_temporary_worker", "command_release",
    "notify_worker_returned"
}

CAMPOS_OBRIGATORIOS = {
    "request_help": ["master_id", "current_load", "capacity", "workers_needed"],
    "response_accepted": ["workers_offered", "worker_details"],
    "response_rejected": ["reason"],
    "command_redirect": ["new_master_address"],
    "register_temporary_worker": ["worker_id", "original_master_address"],
    "command_release": ["original_master_address"],
    "notify_worker_returned": ["worker_id"],
}

def validar_campos_obrigatorios(msg, campos_obrigatorios, contexto=""):
    """Verifica se todos os campos obrigatorios estao presentes.
    Retorna True se valido, False se invalido (com log)."""
    faltando = [c for c in campos_obrigatorios if c not in msg]
    if faltando:
        config.logger.error(
            f"[PARSING] Campos obrigatorios ausentes em {contexto}: {faltando}. "
            f"Mensagem ignorada."
        )
        return False
    return True

def parse_mensagem(msg_str):
    try:
        msg = json.loads(msg_str)
        if not isinstance(msg, dict):
            return None
        if "type" in msg:
            tipo = str(msg["type"]).lower()
            msg["type"] = tipo
            if tipo not in TIPOS_MENSAGEM_VALIDOS:
                config.logger.warning(f"[LOG] Tipo de mensagem desconhecido ignorado: {tipo}")
                return None
        return msg
    except json.JSONDecodeError:
        config.logger.error("[LOG] Erro ao decodificar JSON da mensagem.")
        return None
    except Exception as e:
        config.logger.error(f"[LOG] Erro inesperado ao processar mensagem: {e}")
        return None

def processar_requisicao_worker(msg, worker_id, is_borrowed=False):
    response = {}
    if msg.get("TASK") == "HEARTBEAT":
        response = {
            "SERVER_UUID": config.SERVER_UUID,
            "TASK": "HEARTBEAT",
            "RESPONSE": "ALIVE"
        }
        config.logger.info(f"[Master] Heartbeat recebido -> Respondendo ALIVE")
    elif msg.get("WORKER") == "ALIVE":
        with fila_lock:
            if FILA_TAREFAS:
                tarefa = FILA_TAREFAS.pop(0)
                response = {"TASK": "QUERY", "USER": tarefa}
                if is_borrowed:
                    config.logger.info(f"[Master] Enviando '{tarefa}' para Worker EMPRESTADO {worker_id}")
                else:
                    config.logger.info(f"[Master] Enviando '{tarefa}' para Worker LOCAL {worker_id}")
            else:
                global _tarefas_concluidas_avisado
                if not _tarefas_concluidas_avisado:
                    config.logger.info(f"[Master] Todas as tarefas foram concluidas!")
                    _tarefas_concluidas_avisado = True
                response = {"TASK": "NO_TASK"}
    elif msg.get("STATUS") in ["OK", "NOK"]:
        status = msg.get("STATUS")
        if is_borrowed:
            config.logger.info(f"[Master] Worker EMPRESTADO {worker_id} reportou {status}")
        else:
            config.logger.info(f"[Master] Worker LOCAL {worker_id} reportou {status}")
        response = {"STATUS": "ACK", "WORKER_UUID": worker_id}
    return response