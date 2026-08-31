# Arquitetura do Terminal

Voltar para [o índice](00-index.md).

Este é o ponto de entrada canônico solicitado para a arquitetura. O inventário histórico completo permanece em [[arquitetura-atual]].

```text
MainWindow (lifecycle da aplicação)
├── expiração central de CompraSession / reset ou reconciliação
├── Terminal/ativação persistente
├── SyncService (thread)
│   ├── execução imediata + 300 s
│   ├── GET /produtos/sync por UUID + syncAt
│   ├── FULL/INCREMENTAL transacional no SQLite
│   └── lock + sync_in_progress + sync_pending
├── TerminalSocket (thread)
│   ├── heartbeat a cada 10 s
│   └── ACK após persistência de lastPing
├── TelemetryService (thread daemon, padrão 60 s)
│   ├── SystemMetricsCollector ── /proc, /sys, vcgencmd
│   ├── NetworkMetricsCollector ── nmcli + health HTTP
│   ├── ApplicationMetricsCollector ── sync/compra/socket
│   └── DisplayMetricsCollector ── geometria Qt
├── PaymentListener (QThread)
│   ├── PAYMENT_STATUS → fluxo de pagamento
│   ├── PRODUCT_SYNC_REQUIRED → SyncService
│   └── sync ao conectar/reconectar
└── QStackedWidget / telas
    ├── TerminalScreen / Carrinho único
    ├── AdminAuthScreen / senha efêmera antes da administração
    ├── ConfirmacaoCompraScreen / view do mesmo Carrinho
    ├── PagamentoScreen / workers Point
    └── ConfirmacaoScreen / resultado, ações pós-compra e reset explícito
```

O ramo administrativo reutiliza a mesma `ConfiguracaoScreen`: `WifiScreen -> WifiWorker -> WifiService -> nmcli` e `DisplayScreen -> DisplayWorker -> DisplayService -> wlr-randr/xrandr`. Subprocessos recebem argv, não shell, e timeouts; callbacks carregam token de operação para serem ignorados depois de sair da página. Veja [[menu-administrativo]], [[wifi]] e [[display]].

Configuração, `.env`, identidade, banco e cursor usam paths derivados da raiz do código, independentemente do diretório de execução. Sync e heartbeat começam somente depois de `Terminal.is_activated()` e continuam durante todas as telas, inclusive pagamento. HTTP/SQLite rodam fora da thread Qt. O scanner consulta SQLite a cada leitura; não existe cache paralelo a invalidar. Itens já presentes no carrinho mantêm o snapshot de produto/preço capturado no scan, enquanto a sync afeta leituras futuras.

O backend continua sendo fonte de verdade para terminal, condomínio, empresa, catálogo, disponibilidade, estoque e status financeiro. Veja [[sincronizacao]], [[heartbeat]], [[sqlite]], [[api-backend]] e [[websocket]].

A telemetria é secundária, não participa do checkout e não observa hardware da Point. Falha de coleta ou POST não atravessa a thread do serviço nem altera a UI. Veja [[telemetria]].

O design visual está centralizado em `styles/tokens.py` e `styles/theme.py`. A UI é portrait-first (`768x1360`), mas continua expansível em landscape. A rotação real é responsabilidade do compositor; `start.sh` reaplica a orientação salva pelo `DisplayService`, sem hardcode de saída, e não impede o startup se a ferramenta faltar.

`InternetMonitor` volta a fazer parte do lifecycle pós-ativação e consulta `API_URL`; o `OfflineOverlay` pode abrir o acesso administrativo de Wi-Fi. Conexão nova não cria outro WebSocket, sync ou heartbeat: os serviços já existentes retomam ao detectar o backend.

Os estados Point usam `PaymentStateWidget` fullscreen. `styles/svg_icons.py` resolve `icon/` pela raiz e recolore os SVGs em memória com `QSvgRenderer`, preservando os assets pretos. `CompraSession` guarda o último status interno para a mensagem humana e trata `APPROVED` duplicado de forma idempotente. O reset aprovado é exclusivamente disparado por `FINALIZAR`.

O `QTimer` global pertence a `CompraSession` e não conhece widgets. Seu sinal `expired(generation)` é conectado a `MainWindow._checkout_session_expired`, que bloqueia todas as ações da compra e decide entre `reset_compra` e a reconciliação já existente em `PagamentoScreen`. A geração, a tentativa capturada e o `orderId` esperado invalidam signals/workers tardios; ao encerrar uma tentativa, as conexões locais desses workers também são removidas sem abortar uma requisição financeira incerta.

O toque longo no logotipo continua sendo o acesso administrativo, agora roteado por `AdminAuthScreen`. `TERMINAL_ADMIN_PASSWORD` vem apenas do ambiente; autorização termina ao sair da `ConfiguracaoScreen`. O shutdown administrativo é centralizado em `MainWindow`, para timers, workers, sockets, sync e heartbeat, e não altera/cancela estado financeiro remoto.
