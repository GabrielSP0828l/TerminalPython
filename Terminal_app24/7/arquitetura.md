# Arquitetura do Terminal

Voltar para [o índice](00-index.md).

Este é o ponto de entrada canônico solicitado para a arquitetura. O inventário histórico completo permanece em [[arquitetura-atual]].

```text
MainWindow (lifecycle da aplicação)
├── Terminal/ativação persistente
├── SyncService (thread)
│   ├── execução imediata + 300 s
│   ├── GET /produtos/sync por UUID + syncAt
│   ├── FULL/INCREMENTAL transacional no SQLite
│   └── lock + sync_in_progress + sync_pending
├── TerminalSocket (thread)
│   ├── heartbeat a cada 10 s
│   └── ACK após persistência de lastPing
├── PaymentListener (QThread)
│   ├── PAYMENT_STATUS → fluxo de pagamento
│   ├── PRODUCT_SYNC_REQUIRED → SyncService
│   └── sync ao conectar/reconectar
└── QStackedWidget / telas
```

Configuração, `.env`, identidade, banco e cursor usam paths derivados da raiz do código, independentemente do diretório de execução. Sync e heartbeat começam somente depois de `Terminal.is_activated()` e continuam durante todas as telas, inclusive pagamento. HTTP/SQLite rodam fora da thread Qt. O scanner consulta SQLite a cada leitura; não existe cache paralelo a invalidar. Itens já presentes no carrinho mantêm o snapshot de produto/preço capturado no scan, enquanto a sync afeta leituras futuras.

O backend continua sendo fonte de verdade para terminal, condomínio, empresa, catálogo, disponibilidade, estoque e status financeiro. Veja [[sincronizacao]], [[heartbeat]], [[sqlite]], [[api-backend]] e [[websocket]].
