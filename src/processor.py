import json
from config import SERVER_UUID, DELIMITER

def process_message(message_str, conn):
    try:
        msg = json.loads(message_str)
        if msg.get("TASK") == "HEARTBEAT":
            response = {
                "SERVER_UUID": SERVER_UUID,
                "TASK": "HEARTBEAT",
                "RESPONSE": "ALIVE"
            }
            resp_str = json.dumps(response) + DELIMITER
            conn.sendall(resp_str.encode('utf-8'))
            print(">> [HEARTBEAT] Ping recebido -> Resposta: ALIVE")
    except json.JSONDecodeError:
        print("[-] Erro ao ler JSON.")