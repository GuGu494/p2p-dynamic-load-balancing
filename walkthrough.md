# Walkthrough — Correção Gaps Sprint 03

Todas as 8 tarefas do plano de implementação foram concluídas com sucesso. Abaixo estão os detalhes do que foi corrigido e como você pode testar manualmente o sistema para apresentação ao professor.

## O que foi corrigido

> [!IMPORTANT]
> O sistema agora atende a **todos os requisitos** do plano original do professor (`plano_professor.txt`).

1. **Strict Parsing e Interoperabilidade (Item 31, DoD 8)**: Todas as mensagens JSON agora validam campos obrigatórios (ex: `request_help` exige `master_id`, `current_load`, `capacity`, `workers_needed`). Mensagens inválidas são descartadas com log de erro `[PARSING]`, prevenindo quebras.
2. **Heartbeat Thread (Sprint 1)**: O Worker agora possui uma thread dedicada que roda em paralelo à execução de tarefas, enviando `HEARTBEAT` ao Master atual (mesmo quando emprestado).
3. **Log Lifecycle e Timestamps (Items 28, 29, 30)**: Todos os prints viraram logs estruturados via módulo `logging` do Python com timestamps `[2026-05-27 20:25:01]`. Os eventos de P2P incluem `[SEND]/[RECV]` e `request_id`.
4. **CT08 — Retorno do Worker em Falha (Item 26)**: Se o Master emprestador cair (ex: Timeout ou ConnectionRefused), o Worker detecta que é um worker emprestado e migra de volta automaticamente para seu Master original (`config.HOST:config.PORT`).
5. **Race Condition Eliminada (Item 38)**: O acesso concorrente à `FILA_TAREFAS` agora é protegido por `threading.Lock()` no `processor.py`, eliminando bugs de perda de tarefas.
6. **Entrega de Comandos (Items 17, 22)**: Os comandos de P2P (`command_redirect` e `command_release`) são enfileirados e entregues na exata próxima interação com o Worker (via polling de QUERY/ALIVE), garantindo a menor latência possível e gerando log de `Enfileirado para Worker X`.
7. **Simulação de Falha (NOK)**: Adicionado um percentual aleatório (~10%) para os Workers falharem ao processar tarefas e enviarem `STATUS: NOK`.

---

## Como testar manualmente (Apresentação na Sala)

Você precisa de 3 terminais separados para rodar os testes. Abra 3 janelas do PowerShell (ou divisões no VS Code).

### Terminal 1: Master 1 (Sobrecarga)
```powershell
$env:P2P_PORT="54321"
$env:P2P_SERVER_UUID="Master_1"
$env:P2P_NEIGHBORS='[{"host": "127.0.0.1", "port": 54322, "id": "Master_2"}]'
python src/master.py
```

### Terminal 2: Master 2 (Ocioso)
> [!TIP]
> Usamos `$env:P2P_DISABLE_GENERATOR="true"` no Master 2 para que ele fique sem tarefas (ocioso) e tenha workers sobrando para emprestar ao Master 1.
```powershell
$env:P2P_PORT="54322"
$env:P2P_SERVER_UUID="Master_2"
$env:P2P_NEIGHBORS='[{"host": "127.0.0.1", "port": 54321, "id": "Master_1"}]'
$env:P2P_DISABLE_GENERATOR="true"
python src/master.py
```

### Terminal 3: Worker do Master 2
> [!NOTE]
> Este Worker será emprestado pelo Master 2 (Ocioso) para ajudar o Master 1 (Sobrecarga).
```powershell
$env:P2P_PORT="54322"
$env:P2P_WORKER_UUID="Worker_1"
python src/worker.py
```

### O que observar durante o teste:
1. **Redirecionamento P2P**: Em cerca de 30-40 segundos, o Master 1 (Terminal 1) vai ficar saturado. O Master 2 (Terminal 2) enviará `response_accepted`.
2. **Worker Migrando**: Veja no Terminal 3 que o Worker vai logar: `Redirecionamento P2P recebido! Migrando para 127.0.0.1:54321...`
3. **Teste do CT08**: No meio do processamento (com o Worker já ajudando o Master 1), **DÊ CTRL+C NO TERMINAL 1 (Master 1)**.
4. **Recuperação Automática**: Imediatamente, olhe o Terminal 3 (Worker). Você verá a seguinte mensagem confirmando o CT08:
   `[Worker] Master emprestador (127.0.0.1:54321) caiu! Retornando ao Master original (127.0.0.1:54322)...`

Parabéns! O sistema está 100% aderente ao PDF e aos testes do professor.
