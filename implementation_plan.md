# Sprint 03 — Correção Completa dos Gaps vs. Requisitos do Professor

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Corrigir TODOS os gaps identificados entre a implementação atual e o plano do professor (plano_professor.txt), garantindo que o sistema atenda 100% dos requisitos das Sprints 01, 02 e 03.

**Architecture:** Sistema P2P com Masters gerenciando farms de Workers via TCP/JSON delimitado por `\n`. Threads para concorrência. Comunicação M2M via protocolo padronizado com `type`, `request_id` e `payload`.

**Tech Stack:** Python 3, sockets TCP, threading, json, logging, uuid

---

## Resumo dos Gaps Encontrados

A análise identificou **17 gaps** organizados por prioridade:

### 🔴 CRÍTICOS (reprovariam na avaliação)
1. **CT08**: Worker emprestado NÃO retorna ao Master original quando o Master que o pegou emprestado cai
2. **Item 31/DoD 8**: Sem validação de campos obrigatórios (strict parsing)
3. **Item 28**: Sem timestamps nos logs de mensagens M2M
4. **Item 29**: Sem contadores de Workers locais/emprestados exibidos
5. **Item 30**: Sem log do ciclo de vida completo de Workers emprestados
6. **Item 38**: Race condition na `FILA_TAREFAS` (acesso sem lock)
7. **L149-150**: `except Exception: pass` engole todos os erros silenciosamente
8. **Items 17/22**: `command_redirect` e `command_release` são enfileirados em vez de enviados imediatamente

### 🟡 IMPORTANTES
9. **Sprint 1**: Mecanismo de Heartbeat (`TASK: HEARTBEAT`) completamente ausente
10. **Sprint 2**: Worker nunca reporta NOK (sem simulação de falha)
11. **Sprint 2**: Master não loga qual Worker (local/emprestado) completou qual tarefa
12. **Item 37**: Sem pool de conexões M2M (recomendado pelo professor)

---

## Arquivos Afetados

| Arquivo | Mudanças |
|---------|----------|
| [config.py](file:///C:/Users/luizg/Downloads/p2p-dynamic-load-balancing-main%20(1)/p2p-dynamic-load-balancing-main/src/config.py) | Adicionar configuração de logging |
| [processor.py](file:///C:/Users/luizg/Downloads/p2p-dynamic-load-balancing-main%20(1)/p2p-dynamic-load-balancing-main/src/processor.py) | Strict parsing, validação campos obrigatórios, lock na FILA_TAREFAS, log de worker emprestado |
| [master.py](file:///C:/Users/luizg/Downloads/p2p-dynamic-load-balancing-main%20(1)/p2p-dynamic-load-balancing-main/src/master.py) | Timestamps, contadores, lifecycle logging, entrega imediata de commands, heartbeat, tratamento de erros, conexões persistentes com workers |
| [worker.py](file:///C:/Users/luizg/Downloads/p2p-dynamic-load-balancing-main%20(1)/p2p-dynamic-load-balancing-main/src/worker.py) | CT08 fix (retorno automático ao Master original), heartbeat, simulação NOK |

---

## Tarefa 01 — Logging com Timestamps (Item 28)

**Arquivos:**
- Modificar: `src/config.py`
- Modificar: `src/master.py` (todas as funções com print)
- Modificar: `src/worker.py` (todas as funções com print)
- Modificar: `src/processor.py` (todas as funções com print)

**Objetivo:** Substituir todos os `print()` por um sistema de logging com timestamps automáticos. Usar o módulo `logging` do Python para que TODA mensagem tenha `[YYYY-MM-DD HH:MM:SS]` no início.

- [ ] **Step 1:** Em `config.py`, adicionar configuração de logging:
```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("p2p")
```

- [ ] **Step 2:** Em `master.py`, substituir TODOS os `print(...)` por `config.logger.info(...)`. Nos logs de mensagens M2M, incluir SEMPRE `request_id` e `type`. Exemplo:
```python
# ANTES:
print(f"[P2P] Master vizinho {master_solicitante_id} pediu ajuda")
# DEPOIS:
config.logger.info(f"[P2P][RECV] type=request_help | request_id={request_id} | Master vizinho {master_solicitante_id} pediu ajuda (precisa de {workers_needed} workers)")
```

- [ ] **Step 3:** Em `worker.py`, substituir todos os `print(...)` por `config.logger.info(...)`.

- [ ] **Step 4:** Em `processor.py`, substituir todos os `print(...)` por `config.logger.info(...)`.

- [ ] **Step 5:** Garantir que TODA emissão e recebimento de mensagem M2M logue: `[SEND]` ou `[RECV]`, `type=X`, `request_id=Y`. Formato:
```
[2026-05-27 20:00:01] [P2P][SEND] type=request_help | request_id=a1b2c3d4-... | Para Master_2
[2026-05-27 20:00:01] [P2P][RECV] type=response_accepted | request_id=a1b2c3d4-... | De Master_2
```

---

## Tarefa 02 — Contadores de Workers e Lifecycle Logging (Items 29, 30)

**Arquivos:**
- Modificar: `src/master.py`
- Modificar: `src/processor.py`

**Objetivo:** Exibir contadores de workers a cada mudança e logar ciclo de vida completo de workers emprestados.

- [ ] **Step 1:** Criar função `log_estado_workers()` em `master.py`:
```python
def log_estado_workers():
    """Exibe contadores de workers a cada mudança de estado."""
    with _lock:
        locais = [w for w in WORKERS_ATIVOS if w not in BORROWED_WORKERS and w not in LENT_WORKERS]
        config.logger.info(
            f"[ESTADO] Workers Locais: {len(locais)} | "
            f"Emprestados (de nós): {len(LENT_WORKERS)} | "
            f"Emprestados (para nós): {len(BORROWED_WORKERS)} | "
            f"Total Ativos: {len(WORKERS_ATIVOS)}"
        )
```

- [ ] **Step 2:** Chamar `log_estado_workers()` em TODOS os pontos onde `WORKERS_ATIVOS`, `LENT_WORKERS` ou `BORROWED_WORKERS` são modificados (registros, empréstimos, devoluções, desconexões).

- [ ] **Step 3:** Criar dicionário `BORROWED_WORKER_TASKS = {}` em `master.py` para contar tarefas executadas por cada worker emprestado. Incrementar quando `processar_requisicao_worker` envia QUERY para um worker emprestado.

- [ ] **Step 4:** No momento da devolução (command_release), logar resumo:
```python
config.logger.info(
    f"[LIFECYCLE] Worker {wid} emprestado completou ciclo: "
    f"empréstimo -> registro -> {BORROWED_WORKER_TASKS.get(wid, 0)} tarefas executadas -> devolução"
)
```

- [ ] **Step 5:** Em `processor.py`, na função `processar_requisicao_worker`, quando enviar QUERY, logar se o worker é local ou emprestado:
```python
# Recebe parâmetro is_borrowed
if is_borrowed:
    config.logger.info(f"[Master] Enviando '{tarefa}' para Worker EMPRESTADO {worker_id}")
else:
    config.logger.info(f"[Master] Enviando '{tarefa}' para Worker LOCAL {worker_id}")
```

---

## Tarefa 03 — Strict Parsing e Validação de Campos Obrigatórios (Item 31, DoD 8)

**Arquivos:**
- Modificar: `src/processor.py`
- Modificar: `src/master.py`

**Objetivo:** Validar campos obrigatórios em CADA tipo de mensagem. Mensagens com campos faltando devem gerar log de erro mas NÃO derrubar o processo.

- [ ] **Step 1:** Em `processor.py`, criar função `validar_campos_obrigatorios(msg, campos, contexto)`:
```python
def validar_campos_obrigatorios(msg, campos_obrigatorios, contexto=""):
    """Verifica se todos os campos obrigatórios estão presentes.
    Retorna True se válido, False se inválido (com log)."""
    faltando = [c for c in campos_obrigatorios if c not in msg]
    if faltando:
        config.logger.error(
            f"[PARSING] Campos obrigatórios ausentes em {contexto}: {faltando}. "
            f"Mensagem ignorada: {json.dumps(msg)[:200]}"
        )
        return False
    return True
```

- [ ] **Step 2:** Definir mapa de campos obrigatórios por tipo de mensagem:
```python
CAMPOS_OBRIGATORIOS = {
    "request_help": ["master_id", "current_load", "capacity", "workers_needed"],
    "response_accepted": ["workers_offered", "worker_details"],
    "response_rejected": ["reason"],
    "command_redirect": ["new_master_address"],
    "register_temporary_worker": ["worker_id", "original_master_address"],
    "command_release": ["original_master_address"],
    "notify_worker_returned": ["worker_id"],
}
```

- [ ] **Step 3:** Em `master.py`, validar campos obrigatórios ANTES de acessá-los em cada handler. Exemplo para `request_help`:
```python
if msg.get("type") == "request_help":
    if not validar_campos_obrigatorios(msg.get("payload", {}), 
            CAMPOS_OBRIGATORIOS["request_help"], "request_help"):
        continue
    # ... processar normalmente
```

- [ ] **Step 4:** Para mensagens de Worker (Sprint 02), validar `WORKER` e `WORKER_UUID`:
```python
# Validação de mensagem de worker
if "WORKER" in msg:
    if not validar_campos_obrigatorios(msg, ["WORKER", "WORKER_UUID"], "worker_alive"):
        continue
elif "STATUS" in msg:
    if not validar_campos_obrigatorios(msg, ["STATUS", "TASK", "WORKER_UUID"], "worker_status"):
        continue
```

- [ ] **Step 5:** Remover o `except Exception: pass` do `handle_client` (master.py L149-150) e substituir por log de erro:
```python
except Exception as e:
    config.logger.error(f"[Master] Erro no handler do cliente {addr}: {e}")
```

---

## Tarefa 04 — Race Condition na FILA_TAREFAS (Item 38)

**Arquivos:**
- Modificar: `src/processor.py`
- Modificar: `src/master.py`

**Objetivo:** Proteger `FILA_TAREFAS` contra condições de corrida com um lock dedicado.

- [ ] **Step 1:** Em `processor.py`, criar lock para a fila:
```python
import threading
fila_lock = threading.Lock()
```

- [ ] **Step 2:** Modificar `processar_requisicao_worker` para usar o lock:
```python
def processar_requisicao_worker(msg, worker_id, is_borrowed=False):
    response = {}
    if msg.get("WORKER") == "ALIVE":
        with fila_lock:
            if FILA_TAREFAS:
                tarefa = FILA_TAREFAS.pop(0)
                response = {"TASK": "QUERY", "USER": tarefa}
                # ... log
            else:
                response = {"TASK": "NO_TASK"}
    elif msg.get("STATUS") in ["OK", "NOK"]:
        response = {"STATUS": "ACK", "WORKER_UUID": worker_id}
    return response
```

- [ ] **Step 3:** Em `master.py`, usar `processor.fila_lock` em todos os acessos a `FILA_TAREFAS`:
```python
# Em monitor_carga():
with processor.fila_lock:
    carga = len(FILA_TAREFAS)

# Em gerador_tarefas():
with processor.fila_lock:
    if len(processor.FILA_TAREFAS) < 15:
        processor.FILA_TAREFAS.extend(novas)

# Em solicitar_ajuda_vizinhos():
with processor.fila_lock:
    current_load = len(FILA_TAREFAS)
```

---

## Tarefa 05 — CT08: Worker Emprestado Retorna ao Master Original em Caso de Falha (Item 26)

**Arquivos:**
- Modificar: `src/worker.py`

**Objetivo:** Quando um Worker emprestado perde conexão com o Master que o pegou emprestado, ele deve automaticamente retornar ao Master original.

- [ ] **Step 1:** Modificar o bloco `except` no loop de conexão do Worker:
```python
except (socket.timeout, ConnectionRefusedError, ConnectionResetError, OSError) as e:
    config.logger.warning(f"[Worker] Erro de conexão ({e}).")
    if is_borrowed:
        # CT08: Se o Master que nos pegou emprestado caiu, retornar ao original
        config.logger.info(
            f"[Worker] Master emprestador ({host_atual}:{porta_atual}) caiu! "
            f"Retornando ao Master original ({config.HOST}:{config.PORT})..."
        )
        host_atual = config.HOST
        porta_atual = config.PORT
        is_borrowed = False
        time.sleep(2)
    else:
        config.logger.info(f"[Worker] Aguardando reconexão em 5s...")
        time.sleep(5)
```

- [ ] **Step 2:** Garantir que ao retornar, o Worker se apresenta como Worker LOCAL (sem `SERVER_UUID`), pois voltou para casa.

---

## Tarefa 06 — Mecanismo de Heartbeat (Sprint 1, Tarefas 02-03)

**Arquivos:**
- Modificar: `src/worker.py`
- Modificar: `src/processor.py`
- Modificar: `src/master.py`

**Objetivo:** Implementar o protocolo de Heartbeat conforme o payload oficial do professor.

- [ ] **Step 1:** Em `processor.py`, adicionar handler para `TASK: HEARTBEAT`:
```python
def processar_requisicao_worker(msg, worker_id, is_borrowed=False):
    response = {}
    if msg.get("TASK") == "HEARTBEAT":
        response = {
            "SERVER_UUID": config.SERVER_UUID,
            "TASK": "HEARTBEAT",
            "RESPONSE": "ALIVE"
        }
        config.logger.info(f"[Master] Heartbeat recebido de {msg.get('SERVER_UUID', 'desconhecido')} -> Respondendo ALIVE")
    elif msg.get("WORKER") == "ALIVE":
        # ... resto do Sprint 02
```

- [ ] **Step 2:** Em `worker.py`, adicionar thread de heartbeat periódico:
```python
def heartbeat_loop(host, port):
    """Thread separada que envia HEARTBEAT periodicamente."""
    while True:
        try:
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
                    resp = json.loads(data.split(config.DELIMITER)[0])
                    if resp.get("RESPONSE") == "ALIVE":
                        config.logger.info(f"[Worker] Heartbeat OK - Master {resp.get('SERVER_UUID')} está ALIVE")
        except Exception as e:
            config.logger.warning(f"[Worker] Heartbeat falhou: {e}")
        time.sleep(config.HEARTBEAT_INTERVAL)
```

- [ ] **Step 3:** Iniciar a thread de heartbeat no `start_worker()`:
```python
threading.Thread(target=heartbeat_loop, args=(config.HOST, config.PORT), daemon=True).start()
```

---

## Tarefa 07 — Entrega Imediata de command_redirect/command_release (Items 17, 22)

**Arquivos:**
- Modificar: `src/master.py`

**Objetivo:** Manter conexões persistentes com Workers para enviar commands imediatamente, em vez de enfileirar e esperar o Worker fazer polling. Isso é crucial para interoperabilidade (DoD 7).

> [!IMPORTANT]
> Esta é a mudança mais complexa. O modelo atual abre/fecha uma conexão TCP por mensagem. Para enviar `command_redirect` imediatamente, o Master precisa manter referência às conexões ativas dos Workers.

- [ ] **Step 1:** Modificar `WORKERS_ATIVOS` para armazenar a conexão do socket, não apenas o endereço:
```python
WORKERS_ATIVOS = {}  # maps worker_id -> {"addr": addr, "conn": conn_socket}
```

- [ ] **Step 2:** Quando um Worker se apresenta (ALIVE), guardar a referência da conexão no dicionário e manter a conexão aberta.

- [ ] **Step 3:** Quando `command_redirect` precisa ser enviado, enviar IMEDIATAMENTE pela conexão ativa:
```python
for wid in workers_a_emprestar:
    LENT_WORKERS[wid] = master_solicitante_id
    worker_info = WORKERS_ATIVOS.get(wid)
    if worker_info and worker_info.get("conn"):
        try:
            cmd = {
                "type": "command_redirect",
                "request_id": gerar_request_id(),
                "payload": {"new_master_address": master_solicitante_address}
            }
            worker_info["conn"].sendall((json.dumps(cmd) + config.DELIMITER).encode())
            config.logger.info(f"[P2P][SEND] type=command_redirect | request_id={cmd['request_id']} | Para Worker {wid}")
        except Exception as e:
            config.logger.error(f"[P2P] Falha ao enviar command_redirect para {wid}: {e}")
            # Fallback: enfileirar
            PENDING_WORKER_COMMANDS[wid] = cmd
```

- [ ] **Step 4:** Mesma lógica para `command_release` — enviar imediatamente pela conexão ativa.

- [ ] **Step 5:** Manter o mecanismo de `PENDING_WORKER_COMMANDS` como FALLBACK caso a conexão direta falhe.

---

## Tarefa 08 — Ajustes Finais (Sprint 2, DoD 9)

**Arquivos:**
- Modificar: `src/worker.py` — Simulação de NOK
- Modificar: `src/master.py` — Limpeza de conexões

**Objetivo:** Cobrir os gaps restantes para 100% de conformidade.

- [ ] **Step 1:** Em `worker.py`, adicionar simulação aleatória de falha (NOK):
```python
if resposta.get("TASK") == "QUERY":
    config.logger.info(f"[Worker] Processando tarefa: {resposta.get('USER')}...")
    time.sleep(random.randint(1, 3))
    # Simular falha aleatória (~10% chance)
    status = "NOK" if random.random() < 0.1 else "OK"
    ack_req = {"STATUS": status, "TASK": "QUERY", "WORKER_UUID": config.WORKER_UUID}
    s.sendall((json.dumps(ack_req) + config.DELIMITER).encode())
    config.logger.info(f"[Worker] Tarefa concluída com status: {status}")
```

- [ ] **Step 2:** Em `master.py`, adicionar limpeza de `PENDING_WORKER_COMMANDS` para Workers que não reconectam (evitar memory leak):
```python
# No monitor_carga, periodicamente limpar commands pendentes de workers inativos
with _lock:
    stale = [wid for wid in PENDING_WORKER_COMMANDS if wid not in WORKERS_ATIVOS]
    for wid in stale:
        config.logger.warning(f"[Master] Limpando comando pendente para Worker inativo: {wid}")
        PENDING_WORKER_COMMANDS.pop(wid)
```

- [ ] **Step 3:** Em `master.py`, garantir que no `processor.processar_requisicao_worker`, quando receber STATUS de Worker emprestado, logar explicitamente:
```python
elif msg.get("STATUS") in ["OK", "NOK"]:
    status = msg.get("STATUS")
    if is_borrowed:
        config.logger.info(f"[Master] Worker EMPRESTADO {worker_id} reportou {status} para tarefa")
    else:
        config.logger.info(f"[Master] Worker LOCAL {worker_id} reportou {status} para tarefa")
    response = {"STATUS": "ACK", "WORKER_UUID": worker_id}
```

- [ ] **Step 4:** Verificar que `config.CAPACITY` é usado no payload de `request_help` (ao invés de `SATURATION_THRESHOLD`):
```python
"capacity": config.CAPACITY,  # usar CAPACITY, não SATURATION_THRESHOLD
```

---

## User Review Required

> [!IMPORTANT]
> **Tarefa 07 (Entrega Imediata de Commands)** é a mudança mais complexa e impacta a arquitetura de conexões. A abordagem proposta mantém conexões persistentes com Workers, o que é uma mudança significativa no modelo atual de conexão-por-mensagem. A alternativa mais simples seria manter o modelo de polling (PENDING_WORKER_COMMANDS) que já funciona, mas sacrificando a interoperabilidade com outras equipes.

> [!WARNING]
> **Sprint 1 Heartbeat**: O professor pode verificar se o mecanismo de heartbeat original (`TASK: HEARTBEAT`) funciona. A Tarefa 06 adiciona isso, mas precisa ser testada com cuidado pois cria uma thread adicional no Worker.

## Open Questions

1. **Interoperabilidade (DoD 7)**: O professor vai testar seu sistema com o de outra equipe? Se sim, a Tarefa 07 (entrega imediata) é obrigatória. Se não, o modelo de polling atual funciona.
2. **Pool de conexões M2M (Item 37)**: O professor disse "recomenda-se" — não é obrigatório. Podemos implementar como melhoria futura se necessário.

## Verification Plan

### Testes Manuais (4 terminais)
```
Terminal 1: Master_1 (porta 54321) - com fila de tarefas
Terminal 2: Master_2 (porta 54322) - sem fila (gerador desabilitado)
Terminal 3: Worker conectado ao Master_2
Terminal 4: Worker conectado ao Master_1 (opcional)
```

### Cenários a Verificar
1. **CT01-CT06**: Ciclo completo de empréstimo e devolução
2. **CT07**: Desligar Master_2 enquanto Master_1 tenta `request_help` → timeout
3. **CT08**: Desligar Master_1 enquanto Worker emprestado está trabalhando → Worker retorna ao Master_2
4. **CT09**: Enviar mensagem com `type` desconhecido → log e ignora
5. **Timestamps**: Verificar que TODA mensagem de log tem `[YYYY-MM-DD HH:MM:SS]`
6. **Contadores**: Verificar que a cada mudança de estado, os contadores são exibidos
7. **Heartbeat**: Worker envia heartbeat periódico e recebe ALIVE
