import os
import json

# =====================================================================
# CONFIGURAÇÕES DA REDE (MUDE AQUI NA SALA DE AULA)
# =====================================================================
# Quando for testar com os amigos, troque o '127.0.0.1' pelo seu IP (ex: '192.168.1.50')
MEU_IP_NA_REDE = '127.0.0.1'
MINHA_PORTA = 54321

# Para se conectar ao PC do seu amigo, tire o # da linha abaixo e coloque o IP dele:
MEUS_VIZINHOS_FIXOS = [
    # {"id": "Master_Amigo", "host": "192.168.1.75", "port": 54321}
]
# =====================================================================

HOST = os.environ.get("P2P_HOST", MEU_IP_NA_REDE)
PORT = int(os.environ.get("P2P_PORT", MINHA_PORTA))
DELIMITER = '\n'
HEARTBEAT_INTERVAL = int(os.environ.get("P2P_HEARTBEAT_INTERVAL", 5))

SERVER_UUID = os.environ.get("P2P_SERVER_UUID", "Master_Local")
WORKER_UUID = os.environ.get("P2P_WORKER_UUID", "Worker_Local")

CAPACITY = 10
SATURATION_THRESHOLD = 10
RELEASE_THRESHOLD = 4
NEGOTIATION_TIMEOUT = 5
TIMEOUT_NEGOCIACAO = NEGOTIATION_TIMEOUT
LOAD_CHECK_INTERVAL = 3

# Parse NEIGHBORS from environment se fornecido, senão usa a lista fixa acima
neighbors_env = os.environ.get("P2P_NEIGHBORS")
if neighbors_env:
    try:
        NEIGHBORS = json.loads(neighbors_env)
    except Exception:
        NEIGHBORS = MEUS_VIZINHOS_FIXOS
else:
    NEIGHBORS = MEUS_VIZINHOS_FIXOS

MASTERS_VIZINHOS = [(n["host"], n["port"]) for n in NEIGHBORS]

import logging

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("p2p")