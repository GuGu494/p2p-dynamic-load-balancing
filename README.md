# P2P Dynamic Load Balancing

Este projeto é uma implementação de um sistema de Balanceamento de Carga Dinâmico utilizando uma arquitetura híbrida Peer-to-Peer (P2P) e Master-Worker. O objetivo do sistema é distribuir tarefas computacionais entre diferentes nós da rede, garantindo que nenhum nó fique sobrecarregado enquanto outros permanecem ociosos.

## 🚀 Funcionalidades

- **Arquitetura Master-Worker**: Workers consultam os Masters em busca de tarefas.
- **Rede P2P entre Masters**: Masters se comunicam entre si. Quando um Master fica sobrecarregado, ele pode "pegar emprestado" Workers de um Master ocioso.
- **Resiliência a Falhas**: Tratamento de queda de conexão. Se um Master falhar, os Workers emprestados retornam automaticamente ao seu Master original.
- **Observabilidade**: Sistema de logs estruturado, rastreabilidade de mensagens P2P e painel de estado em tempo real.
- **Validação de Mensagens**: Parsing rigoroso para evitar falhas com mensagens malformadas.

## 🛠️ Como Executar

Você pode testar a aplicação em um único computador usando diferentes terminais:

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

Para mais detalhes da implementação técnica, consulte os arquivos [task.md](task.md) e [walkthrough.md](walkthrough.md).

## 👥 Integrantes

Este projeto foi desenvolvido pelos seguintes membros:

- **Luiz Gustavo Silva dos Anjos** - [https://github.com/GuGu494](https://github.com/GuGu494)
- **Matheus Campos** - [https://github.com/matheusccrr05](https://github.com/matheusccrr05)
- **Sarah Costa dos Santos Fernandes** - [https://github.com/sarahcosta-ops](https://github.com/sarahcosta-ops)

---
> [!NOTE]
> Este projeto foi desenvolvido como parte dos estudos de Sistemas Distribuídos e Redes P2P.
