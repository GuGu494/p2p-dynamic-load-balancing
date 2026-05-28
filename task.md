# Log de Execução de Tarefas — Sprint 03

> [!NOTE]  
> Este documento serve como o registro (Changelog) do fluxo de desenvolvimento da Sprint 03. Todas as tarefas planejadas foram concluídas e validadas através de testes automatizados e manuais.

## Status Geral: `CONCLUÍDO` ✅

---

### Tarefa 1: Implementação de Observabilidade (Item 28)
- **Status**: `[x] Concluído`
- **Arquivos modificados**: `config.py`, `master.py`, `processor.py`, `worker.py`
- **Detalhes**: Substituição global de prints no terminal pelo módulo `logging`. Configuração de timestamps globais no formato `[YYYY-MM-DD HH:MM:SS]`. Injeção de tags de rastreabilidade `[SEND]/[RECV]` em todas as mensagens P2P no `master.py`.

### Tarefa 2: Painel de Estado e Lifecycle (Itens 29, 30)
- **Status**: `[x] Concluído`
- **Arquivos modificados**: `master.py`, `processor.py`
- **Detalhes**: Criação da função `log_estado_workers()` que exibe em tempo real o balanço de Workers (Locais, Emprestados, Tomados). Adição de rastreamento do clico de vida (Lifecycle) contando as tarefas de cada worker emprestado antes da devolução.

### Tarefa 3: Validação Estrita de Contratos JSON (DoD 8, Item 31)
- **Status**: `[x] Concluído`
- **Arquivos modificados**: `processor.py`, `master.py`
- **Detalhes**: Criação do dicionário estrutural `CAMPOS_OBRIGATORIOS`. Implementação da função `validar_campos_obrigatorios()` para checar chaves vitais (`capacity`, `request_id`, etc.) antes do processamento, evitando quebras (crashes) na arquitetura Master.

### Tarefa 4: Correção de Concorrência e Race Conditions (Item 38)
- **Status**: `[x] Concluído`
- **Arquivos modificados**: `processor.py`, `master.py`
- **Detalhes**: Inserção de `threading.Lock()` nomeado `fila_lock` protegendo o objeto `FILA_TAREFAS`. Acesso concorrente entre as threads `monitor_carga`, `gerador_tarefas` e `handle_client` foi serializado para proteger o estado do sistema.

### Tarefa 5: Resiliência em Empréstimo P2P — CT08 (Item 26)
- **Status**: `[x] Concluído`
- **Arquivos modificados**: `worker.py`
- **Detalhes**: Adicionado tratamento de queda abrupta de conexão (`ConnectionRefusedError` / `[WinError 10054]`). Worker identifica se foi emprestado (`is_borrowed=True`) e redireciona os sockets automaticamente para o Master Original de sua LAN.

### Tarefa 6: Pulso de Vida (Heartbeat da Sprint 1)
- **Status**: `[x] Concluído`
- **Arquivos modificados**: `worker.py`
- **Detalhes**: Criação de thread paralela (`daemon=True`) rodando a função `heartbeat_loop()`. Garante pulsos P2P a cada `HEARTBEAT_INTERVAL` segundos de forma não-bloqueante para o loop principal de processamento de carga.

### Tarefa 7: Otimização de Fila e Latência (Itens 17, 22)
- **Status**: `[x] Concluído`
- **Arquivos modificados**: `master.py`
- **Detalhes**: Adequação do dicionário `PENDING_WORKER_COMMANDS`. Ordens P2P críticas (`command_redirect` e `command_release`) são agora injetadas nativamente no ciclo de polling `ALIVE` do Worker, garantindo entrega assíncrona imediata e log de `"Enfileirado para Worker X"`.

### Tarefa 8: Simulação Reversa e Ajustes de Carga (Sprint 2)
- **Status**: `[x] Concluído`
- **Arquivos modificados**: `worker.py`, `master.py`
- **Detalhes**: Emulação de falha randômica (~10% de `STATUS: NOK`) implementada via módulo `random` no Worker. Correção da emissão de `capacity` no `request_help` para respeitar o limite arquitetural de hardware. Limpeza periódica (Garbage Collection) de comandos órfãos na memória do Master.

---

## Validação Final
- **Ciclo de Testes Manuais**: `[x] Passou (CT01 a CT09)`
- **Aprovação de Requisitos**: O laboratório atual encontra-se estável e pronto para apresentação do Docente.
