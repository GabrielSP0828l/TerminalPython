# Compatibilidade com o backend atual

Voltar para [o índice](00-index.md).

## Resumo

| Área | Resultado |
|---|---|
| Hierarquia empresa → condomínio → terminal | intenção compatível; DTO local legado |
| Ativação por serial | rota compatível; campos de identidade incompatíveis |
| Produtos | compatível com `/produtos/sync`, `syncAt`, FULL/INCREMENTAL e aviso WebSocket |
| Carrinho | body compatível quando UUIDs locais são válidos |
| Order/cobrança Point | cliente não chama o contrato atual corretamente |
| Mercado Pago | separação de credenciais correta; não há chamada direta no Python |
| Resultado de pagamento | socket existe, mas publicação/status/correlação incompatíveis |
| Estoque | cliente não movimenta estoque, correto; não sincroniza disponibilidade por condomínio |

## Incompatibilidades

### COM-001 — Identidade duplicada e DTO de ativação divergente

**Status após auditoria:** corrigido no cliente, com migração em memória do JSON legado.

- **Terminal atual:** espera `terminalId` numérico e `uuidTerminal`; carrinho/socket de pagamento usam `uuidTerminal`, heartbeat usa `terminalId`.
- **Backend atual:** devolve um único `terminalId` UUID e `condominioId` UUID.
- **Impacto:** instalação nova salva `uuidTerminal=null`; carrinho e socket usam `None`. Instalação antiga pode enviar ID numérico no heartbeat.
- **Correção aplicada:** `Terminal.from_dict` usa `uuidTerminal` legado quando presente ou o `terminalId` atual; os dois atributos locais passam a carregar o mesmo UUID canônico.

### COM-002 — Ativação local baseada só na existência do arquivo

**Status após auditoria:** corrigido no cliente.

- **Terminal atual:** qualquer `db/terminal.json` significa ativado.
- **Backend atual:** possui `ativo/activated/status` e cadastro central.
- **Impacto:** terminal removido/desativado ou arquivo inválido continua sendo tratado como válido.
- **Correção aplicada:** o arquivo é carregado e validado; JSON inválido, identidade ausente ou flags inativas não ativam a operação. A reconciliação periódica após ativação continua futura.

### COM-003 — Sync sem contexto de empresa/terminal

**Status: RESOLVIDO.**

- **Contrato antigo:** `/produtos/sync` dependia de contexto de empresa e o cliente enviava apenas `lastSync`.
- **Contrato atual:** `ProdutoSyncService` recebe `uuidTerminal`, busca o Terminal globalmente e deriva seu condomínio.
- **Solução aplicada:** o Python envia somente UUID persistente e cursor; não inventa empresa/condomínio.

### COM-004 — Sync de catálogo, não disponibilidade do condomínio

**Status: RESOLVIDO.**

- **Contrato antigo:** o catálogo da empresa não representava disponibilidade local.
- **Contrato atual:** `/produtos/sync` consulta `EstoqueCondominio` do condomínio derivado do Terminal e considera produto/vínculo ativos.
- **Solução aplicada:** FULL representa estado completo local; incremental fornece `UPSERT/REMOVE` para o mesmo condomínio.

### COM-005 — IDs de produto incompatíveis com SQLite

**Status: RESOLVIDO.**

- **Terminal antigo:** `produtos.id INTEGER PRIMARY KEY`.
- **Backend atual:** `ProdutoResponse.id` é UUID string.
- **Impacto:** `INSERT OR REPLACE` falha ao sincronizar UUID.
- **Solução:** migration transacional converte a PK para `TEXT`; teste cobre banco legado e UUID.

### COM-006 — Campos de produto divergentes

**Status: RESOLVIDO.**

- **Terminal antigo:** lia `status` e nomes temporais legados.
- **Backend atual:** `ProdutoSyncItem` devolve `ativo`, `quantidade`, `createdAt` e `updatedAt`.
- **Solução:** mapper usa os nomes exatos e o UPSERT atualiza todos os campos retornados.

### COM-007 — Endpoint de cobrança Point usado com URL errada

**Status: RESOLVIDO.**

- **Terminal atual:** `GET /pagamento/terminal?carrinho_id=...`.
- **Backend atual:** `GET /pagamento/terminal/{carrinho_id}`.
- **Impacto:** 404/405; Order e cobrança não são iniciadas.
- **Solução:** cliente usa `POST /pagamento/terminal/{carrinhoId}` em worker Qt.

### COM-008 — Resposta de cobrança esperada é de fluxo legado

**Status: RESOLVIDO.**

- **Terminal atual:** espera `valor`, `qrCode`, `qrCodeBase64` e abre PIX.
- **Backend atual:** retorna booleano após iniciar cobrança Point na maquininha.
- **Impacto:** mesmo com URL corrigida, parsing falha; interface descreve PIX quando o backend iniciou Point.
- **Solução:** adotado `PointPaymentResponse` com `orderId`, `terminalId` e status interno; PIX presencial legado foi removido.

### COM-009 — Crédito e débito não usam backend

**Status: RESOLVIDO.**

- **Terminal atual:** ambos chamam apenas reset visual.
- **Backend atual:** suporta cobrança Point sem o cliente escolher credenciais/terminal externo.
- **Impacto:** falsa conclusão local sem venda ou pagamento persistidos.
- **Solução:** `PAGAR AGORA` inicia Point diretamente; a maquininha determina o meio e o terminal aguarda backend.

### COM-010 — Backend não publica resultado no socket ativo

**Status: RESOLVIDO no worktree backend atual.**

- **Terminal atual:** depende de `/payment-socket/{terminal}`.
- **Backend atual:** handler escuta `PaymentEvent`, mas webhook publica apenas eventos de Order/estoque.
- **Impacto:** pagamento pode ser aprovado no backend e terminal permanecer esperando/sem reação.
- **Solução:** `PagamentoService` publica `PaymentEvent(PointPaymentResponse)` e handlers entregam pós-commit; estado também é consultável.

### COM-011 — Estados de pagamento incompatíveis

**Status: RESOLVIDO.**

- **Terminal atual:** não interpreta status; qualquer JSON equivale a aprovação.
- **Backend atual:** estados Point são `CREATED`, `AT_TERMINAL`, `PROCESSED`, `FAILED`, `CANCELED`, `EXPIRED`, `REFUNDED`, `ACTION_REQUIRED`; evento legado possui campo textual `paid`.
- **Impacto:** recusa/cancelamento pode exibir sucesso; estados intermediários não são representados.
- **Solução:** cliente usa `WAITING_PAYMENT`, `ACTION_REQUIRED`, `APPROVED`, `REJECTED`, `CANCELLED`, `EXPIRED` e `REFUNDED`; mapeamento MP permanece backend.

### COM-012 — Ausência de correlação com Order

**Status: RESOLVIDO.**

- **Terminal atual:** não guarda nem compara `orderId`.
- **Backend atual:** evento inclui `orderId`, e Order é a unidade do pagamento.
- **Impacto:** evento antigo/de outra compra pode liberar a compra atual.
- **Solução:** `CompraSession` guarda Order ativa; evento exige terminal e Order correspondentes.

### COM-013 — Sem recuperação após reconexão

**Status: PARCIALMENTE RESOLVIDO.**

- **Terminal atual:** apenas reconecta o socket.
- **Backend atual:** mantém estado final no banco, mas não há endpoint terminal-oriented usado para consulta.
- **Impacto:** evento perdido deixa UI divergente do financeiro.
- **Solução:** reconnect consulta `GET /order/{orderId}/status?terminalId=...`. Persistência para recuperar após reinício físico continua pendente.

### COM-014 — Cancelamento/timeout apenas local

**Status: PARCIALMENTE RESOLVIDO; expiração local central corrigida em 28 de agosto de 2026.**

- **Terminal atual:** timers voltam de tela; cancelar não notifica backend.
- **Backend atual:** estoque/reserva e estados pertencem ao backend.
- **Impacto:** sessão/carrinho/Order podem continuar ativos após abandono local.
- **Solução:** `CompraSession.expired` agora chega ao controlador central exatamente uma vez; lista/confirmação executam reset seguro e pagamento consulta/reconcilia sem presumir falha. Não existe endpoint operacional de cancelamento; a nova compra permanece bloqueada se o estado continuar incerto.

### COM-015 — Quantidade/peso calculados de modos distintos

**Status: RESOLVIDO para produtos sem balança; pesáveis continuam pendentes.**

- **Terminal atual:** mostra `Item.subtotal` por peso quando `received_weight` é truthy, mas total e payload financeiro usam quantidade; todo item recebe peso `1.0`.
- **Backend atual:** subtotal do carrinho multiplica preço por quantidade e recebe peso como snapshot auxiliar.
- **Impacto:** linha e total podem divergir para itens pesáveis; balança não está integrada.
- **Solução:** scans controlam `quantity` e `receivedWeight` fica `null`; linha e total usam quantidade. Integração real de balança exige etapa própria.

## Compatibilidades que devem ser preservadas

- O Python não contém access token, refresh token ou client secret Mercado Pago.
- A cobrança externa é responsabilidade exclusiva do backend.
- `CarrinhoRequest` não envia empresa/condomínio; o backend deriva empresa do terminal.
- O backend recalcula subtotal a partir do produto persistido.
- O Python não movimenta estoque oficial.
- A ativação parte da identidade física/serial, sem seleção arbitrária de tenant.
- Scanner e cache permitem resposta imediata da UI.

### COM-016 — Catálogo local não atualizava durante execução

**Status: RESOLVIDO em 24 de agosto de 2026.**

O endpoint correto já era um snapshot por terminal, porém o cliente o chamava somente no startup e os paths dependiam do diretório corrente. O serviço agora usa paths canônicos, executa imediatamente e a cada 300 segundos, aplica snapshot transacional e mantém cache/cursor em qualquer falha.

### COM-017 — Heartbeat sem confirmação de `lastPing`

**Status: RESOLVIDO em 24 de agosto de 2026.**

O envio WebSocket atualizava o banco, mas o backend não respondia e o cliente não distinguia persistência de um simples envio ao socket. `/terminal-socket` agora responde `HEARTBEAT_ACK` somente após `saveAndFlush`; o cliente valida UUID e `lastPing` antes de registrar sucesso.

### COM-018 — Migração para o novo contrato de sincronização

**Status: RESOLVIDO em 24 de agosto de 2026.**

| Aspecto | Contrato anterior do Terminal | Contrato atual |
|---|---|---|
| Endpoint | `GET /terminais/{terminalId}/produtos-disponiveis` (snapshot) | `GET /produtos/sync?uuidTerminal={uuid}&lastSync={opcional}` |
| Resposta | lista JSON direta de produtos | `{syncAt, fullSync, changes[]}` |
| Cursor | data artificial/`datetime.now()` local | `syncAt` exato gerado pelo backend |
| Alterações | substituição integral periódica | `UPSERT` e `REMOVE`; FULL distinto de INCREMENTAL |
| Tempo real | inexistente | `PRODUCT_SYNC_REQUIRED` em `/payment-socket/{terminalId}` |

O cliente valida o lote inteiro, aplica todas as operações numa transação e só então persiste `syncAt`. Cursor legado inválido provoca FULL SYNC. Conexão/reconexão solicita recuperação incremental. `sync_in_progress + sync_pending`, protegidos por lock, impedem concorrência sem perder notificações.

### COM-019 — Cursor válido com cache local não inicializado

**Status: RESOLVIDO em 24 de agosto de 2026.**

O cliente podia manter `last_sync.txt` após perda/recriação do SQLite e aceitar incrementais vazios indefinidamente. A tabela `catalog_sync_state` agora registra FULL confirmado e contagem ativa esperada. Ausência do marcador ou divergência local omite `lastSync` e exige `fullSync=true`; FULL legitimamente vazio passa a ser um cache inicializado de zero produtos.
