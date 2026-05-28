# Relatório Técnico: Balanceamento de Carga P2P (Sprint 03)

> [!IMPORTANT]  
> Este documento comprova o atendimento integral aos requisitos estabelecidos no documento `plano_professor.txt`, detalhando as soluções arquiteturais, tratamento de falhas e os fluxos de teste para a Sprint 03.

---

## 1. Visão Geral da Arquitetura

O sistema adota uma **Arquitetura Híbrida**:
- **Cliente-Servidor (Master-Worker):** Os Workers atuam como nós de processamento "burros" que consultam incessantemente o Master em busca de tarefas.
- **Ponto-a-Ponto (P2P entre Masters):** Os Masters formam uma rede overlay. Quando um Master atinge o limiar de saturação (`SATURATION_THRESHOLD`), ele negocia ativamente com os nós vizinhos (previamente mapeados) o empréstimo temporário de Workers.

```mermaid
graph TD
    subgraph Master 1 (Saturado)
        M1[Master A] -->|1. request_help| M2
        W1[Worker 1] -.->|Processa Tarefas| M1
    end

    subgraph Master 2 (Ocioso)
        M2[Master B] -->|2. response_accepted| M1
        W2[Worker 2] -.->|Originalmente reporta ao| M2
    end

    M1 -.->|3. command_redirect enfileirado| W2
    W2 ===>|4. Migração e Processamento| M1
```

---

## 2. Mapeamento de Requisitos (Gap Analysis)

Durante a Sprint 03, foram sanados todos os gaps técnicos. Abaixo, o relatório de conformidade:

| Ref. PDF | Requisito | Status | Implementação |
| :--- | :--- | :---: | :--- |
| **CT08** | Retorno Seguro de Worker (Item 26) | ✅ | Se um Master que tomou Workers emprestados falhar repentinamente (`ConnectionRefusedError`), o Worker captura a exceção, identifica a flag `is_borrowed=True`, e retorna automaticamente ao `config.HOST` original (Master de origem). |
| **T07** | Observabilidade e Logs (Itens 28-30) | ✅ | Adição do módulo `logging`. Formato padronizado de timestamps `[YYYY-MM-DD HH:MM:SS]`. Mensagens P2P contêm tags `[SEND]/[RECV]`, `type`, e `request_id`. |
| **Nota 31** | Strict Parsing (DoD 8) | ✅ | Função `validar_campos_obrigatorios()`. Se uma mensagem P2P chega faltando dados (ex: `capacity`), o Master gera um log de erro e a descarta de forma segura sem crash do socket. |
| **Nota 38** | Thread Safety em Filas concorrentes | ✅ | Instanciado `threading.Lock()` nomeado `fila_lock` em `processor.py` para operações na `FILA_TAREFAS`, eliminando Race Conditions. |
| **S1** | Heartbeat de Workers | ✅ | Uma thread daemon foi adicionada ao `worker.py` (`heartbeat_loop`), que envia pings de vida independentemente do tempo de processamento das tarefas. |
| **S2** | Falha no Processamento de Tarefas | ✅ | Emulação probabilística (~10%) injetada em `worker.py` para devolver `STATUS: NOK`. |

---

## 3. Dinâmica de Empréstimo e Liberação

A gestão de conexões resolve o problema clássico de *Connection Hanging* sem violar a regra de vazamento de threads (DoD 9):

1. **Solicitação:** A thread `monitor_carga()` do Master detecta fila > 10. Emite `request_help`.
2. **Redirecionamento (Item 17):** Para que o redirecionamento seja imediato sem exigir conexão persistente, o Master enfileira a ordem no dicionário `PENDING_WORKER_COMMANDS`. Quando o Worker emite seu próximo pulso `ALIVE`, a ordem de redirecionamento é despachada.
3. **Liberação (Item 22):** Quando a carga do tomador (Master A) normaliza (cai para o `RELEASE_THRESHOLD`), a thread `monitor_carga()` executa o caminho reverso. Ela devolve o Worker (`command_release`) e avisa o Master Original (`notify_worker_returned`).

> [!TIP]  
> A rastreabilidade do ciclo de vida é exposta no console em tempo real. Exemplo do painel mantido no console:  
> `[ESTADO] Workers Locais: 2 | Emprestados (de nos): 1 | Emprestados (para nos): 0 | Total Ativos: 3`

---

## 4. Guia de Teste (Apresentação Prática)

Para comprovar a eficácia durante a avaliação, o laboratório pode ser simulado em três terminais locais ou em máquinas distribuídas na LAN.

### Configuração para um único PC (Via PowerShell)

**Terminal 1 (Master 1 - Sobrecarga):**
```powershell
$env:P2P_PORT="54321"
$env:P2P_SERVER_UUID="Master_1"
$env:P2P_NEIGHBORS='[{"host": "127.0.0.1", "port": 54322, "id": "Master_2"}]'
python src/master.py
```

**Terminal 2 (Master 2 - Ocioso):**
```powershell
$env:P2P_PORT="54322"
$env:P2P_SERVER_UUID="Master_2"
$env:P2P_NEIGHBORS='[{"host": "127.0.0.1", "port": 54321, "id": "Master_1"}]'
$env:P2P_DISABLE_GENERATOR="true"
python src/master.py
```

**Terminal 3 (Worker do Master 2):**
```powershell
$env:P2P_PORT="54322"
$env:P2P_WORKER_UUID="Worker_1"
python src/worker.py
```

### Configuração para Rede Local (Testando com outro grupo)

Se o professor pedir para integrar seu código com o de outra equipe na sala:
1. Abra o arquivo `src/config.py`.
2. Altere `MEU_IP_NA_REDE` para o seu IP (ex: `192.168.0.15`).
3. Altere a variável `MEUS_VIZINHOS_FIXOS` inserindo o IP do computador do outro grupo.
4. Rode `python src/master.py` normalmente!

> [!CAUTION]
> **Teste do CT08 ao Vivo:** Com o Worker já redirecionado e ajudando o Master 1, dê um **CTRL+C** agressivo no Terminal 1. No mesmo instante, o Terminal 3 do Worker deverá emitir o log vermelho atestando: *"Master emprestador caiu! Retornando ao Master original"*, provando a estabilidade do sistema sob estresse.
