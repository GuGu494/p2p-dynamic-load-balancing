import os
import json


MEU_IP_NA_REDE = '127.0.0.1'
MINHA_PORTA = 8000


MEUS_VIZINHOS_FIXOS = [
    {"id": "Grupo_B_Teste", "host": "127.0.0.1", "port": 8000}
]


HOST = os.environ.get("P2P_HOST", MEU_IP_NA_REDE)
PORT = int(os.environ.get("P2P_PORT", MINHA_PORTA))
DELIMITER = '\n'
HEARTBEAT_INTERVAL = int(os.environ.get("P2P_HEARTBEAT_INTERVAL", 5))


SERVER_UUID = os.environ.get("P2P_SERVER_UUID", "Master_5.A")
WORKER_UUID = os.environ.get("P2P_WORKER_UUID", "Worker_Local")

CAPACITY = 10
SATURATION_THRESHOLD = 10
RELEASE_THRESHOLD = 4
NEGOTIATION_TIMEOUT = 5
TIMEOUT_NEGOCIACAO = NEGOTIATION_TIMEOUT
LOAD_CHECK_INTERVAL = 3


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