# Terminal App247 — arquitetura executável auditada

Data da auditoria: 27 de setembro de 2026.

Este documento descreve o *working tree* auditado, não a arquitetura desejada. Foram lidos o código Python, o SQLite local, os testes e os controllers/DTOs/services correspondentes do backend em `../app247`. Documentação e nomes de classes não foram usados como prova de implementação.

Veja também [[terminal-review-2026-09]], [[terminal-pending]], [[arquitetura]], [[fluxo-compra]], [[api-backend]], [[websocket]] e [[sqlite]].

## Atualização executável após hardening P0/P1

O startup vigente executa `FactoryResetService.apply_pending` em modo fail-closed, abre `ActivePaymentStore` com `PRAGMA integrity_check` e só então decide entre modo de recuperação, operação ativada ou ativação. Reset pendente não move o banco se houver linha `active_payment` ou se a integridade não puder ser comprovada.

Se `terminal.json` estiver ausente/inválido e o checkpoint contiver `terminal_id`, `MainWindow` restaura `CompraSession`, abre uma tela exclusiva e usa `ActivePaymentRecoveryWorker`. Estado intermediário/erro mantém bloqueio e retry; resultado terminal ou ausência autoritativa libera somente a reativação, nunca Home diretamente.

Em produção, `TerminalAuth` exige `TERMINAL_INTERNAL_TOKEN`. HTTP operacional e upgrades `/payment-socket/*`/`/terminal-socket` carregam o header, validado pelo backend. O UUID é identificador/correlação, não credencial. A limitação restante é o token compartilhado, sem revogação individual; veja [[terminal-device-security]].

`APP_ENV=production` apresenta `showFullScreen`; development usa janela `1024x600`. A ativação oferece exclusivamente Wi-Fi pré-vínculo. Workers financeiros, Wi-Fi, display, comprovante e app checkout conservam referência, usam correlação/generation e limpam com `deleteLater`.

## 1. Componentes reais

```text
main.py / MainWindow
├── CompraSession                  estado e deadline da compra
│   └── ActivePaymentStore        checkpoint financeiro no SQLite
├── CadastroTerminalScreen        ativação por QR + polling HTTP
├── TelaBemVindos                 home e acesso oculto ao admin
├── TerminalScreen                scanner HID, carrinho e catálogo SQLite
│   ├── DatabaseProdutos          cache de catálogo
│   └── PaymentListener           WS de pagamento/produto/reset
├── ConfirmacaoCompraScreen       resumo antes da cobrança
├── PagamentoScreen               workers Point, polling e cancelamento
├── ConfirmacaoScreen             sucesso e comprovantes
├── AdminAuthScreen               senha local
└── ConfiguracaoScreen
    ├── WifiScreen / WifiService
    └── DisplayScreen / DisplayService

Serviços de processo
├── SyncService                   scheduler + worker Python
├── TerminalSocket                heartbeat WebSocket
├── InternetMonitor               QThread de disponibilidade HTTP
├── TelemetryService              thread daemon de telemetria
├── TerminalLifecycleService      bootstrap/reset remoto
└── FactoryResetService           reset local/remoto adiado por marcador
```

Não há camada formal de controllers/repositories no cliente. `MainWindow` coordena navegação e lifecycle; as telas ainda detêm parte relevante da orquestração.

## 2. Startup real

```text
processo
  -> carrega .env por config.py
  -> FactoryResetService.apply_pending()
  -> cria ActivePaymentStore e CompraSession
  -> cria telas básicas
  -> Terminal.is_activated()
       |
       +-- falso -> CadastroTerminalScreen
       |             -> gera QR local com serial/MAC/IP
       |             -> GET /terminal/serial/{serial} a cada 5 s
       |             -> salva db/terminal.json atomicamente
       |             -> inicia operação
       |
       +-- verdadeiro -> iniciar_operacao_terminal()
                         -> restaura active_payment do SQLite
                         -> cria telas operacionais
                         -> inicia PaymentListener
                         -> agenda recovery HTTP de pagamento
                         -> inicia SyncService
                         -> inicia TerminalSocket/heartbeat
                         -> inicia InternetMonitor
                         -> inicia TelemetryService
                         -> agenda bootstrap de lifecycle
                         -> mostra Home
```

### Estados de falha observados

| Condição | Comportamento executável |
|---|---|
| `API_URL` ausente | ativação exibe servidor não configurado; serviços ativados falham de modo controlado |
| backend offline, Terminal ativado | cache e UI abrem; sync/heartbeat/telemetria/recovery tentam novamente |
| backend offline, Terminal não ativado | ativação continua tentando, mas não há acesso visível ao Wi-Fi/admin nessa tela |
| `terminal.json` ausente/inválido | é tratado como não ativado |
| SQLite ausente | tabelas são criadas automaticamente |
| SQLite corrompido/incompatível | `sqlite3.DatabaseError` pode abortar o startup; não há quarentena/repair |
| variáveis numéricas inválidas | conversão em `config.py` pode abortar o import |

## 3. Ativação e identidade

O QR de ativação contém JSON com `serialNumber`, `macAddress` e `ipAddress`. A tela não chama endpoint de criação: o painel/backend cadastra/libera o equipamento e o Terminal apenas consulta `GET /terminal/serial/{serial}`.

`Terminal.from_dict` adota `terminalId`/`uuidTerminal` como identidade canônica, persiste `condominioId` e nome recebidos, mas nunca escolhe Empresa ou Condomínio. A gravação usa arquivo temporário + rename.

O backend real devolve `TerminalActivationResponse` compatível. Não existe retry exponencial, botão de reset/reprovisionamento nessa tela ou credencial criptográfica de dispositivo.

## 4. Catálogo e sincronização

```text
STARTUP / PERIODIC / WS / RECONNECT / PRICE_CHANGED
  -> SyncService.request_sync(origin)
  -> lock: no máximo um worker; eventos extras viram sync_pending
  -> valida Terminal ativado e cache local
  -> GET /produtos/sync?uuidTerminal=...&lastSync=...
  -> valida todo o envelope e cada change
  -> uma transação SQLite:
       FULL: desativa catálogo e substitui barcodes
       INCREMENTAL: UPSERT/REMOVE pontuais
       atualiza catalog_sync_state.last_sync_at
  -> commit
  -> espelha cursor em database/last_sync.txt
```

Tabelas verificadas no SQLite real:

- `schema_version` (catálogo v2);
- `produtos`;
- `produto_codigo_barras`;
- `catalog_sync_state`;
- `active_payment`.

O `PRAGMA integrity_check` do arquivo auditado retornou `ok`. Havia um produto ativo, catálogo inicializado e nenhum pagamento ativo no momento da inspeção.

`catalog_sync_state.initialized`, `expected_active_count` e `last_sync_at` participam do commit. Cache não inicializado ou com contagem divergente omite `lastSync` e exige FULL. Um FULL vazio válido é aceito.

Quantidade negativa não remove o produto. O backend gera UPSERT quando `EstoqueCondominio.ativo` e `Produto.status` são verdadeiros, independentemente da quantidade; o Terminal filtra somente `produto.ativo` e barcode ativo.

## 5. Scanner e carrinho

O scanner é tratado como teclado USB/HID que preenche um `QLineEdit` e envia Enter. Não há driver serial/GPIO, health check, framing próprio ou parser central.

```text
texto + Enter
  -> trim
  -> DatabaseProdutos.buscar_por_codigo
  -> JOIN barcode/produto, ambos ativos
  -> produto inexistente: QMessageBox
  -> produto já no carrinho: quantidade += 1
  -> novo produto: Item + ProductCard
```

Somente EAN/código de produto é reconhecido. `APP247:LINK:*` e `APP247:COUPON:*` não são classificados.

`Carrinho` é memória de processo. Ele soma preços com `Decimal`, envia `productId`, `quantity`, `receivedWeight`, `expectedUnitPrice` e `codigoBarras`. Aumento de preço devolvido pelo backend (`409 PRICE_CHANGED`) atualiza os snapshots locais e exige nova confirmação. Promoção não é recalculada no Python.

Incremento é feito por nova leitura. A UI remove a linha inteira; não há decremento unitário. Produtos pesáveis não possuem aquisição real de peso e `peso_total_venda` permanece um `float` visual em zero.

## 6. Compra e pagamento

```text
Home
  -> TerminalScreen
  -> scanner/carrinho
  -> FINALIZAR
  -> ConfirmacaoCompraScreen (nenhuma chamada remota)
  -> CONFIRMAR E PAGAR
  -> CompraSession.begin_payment + checkpoint SQLite
  -> PointCheckoutWorker
       POST /carrinho
       checkpoint cartId
       POST /pagamento/terminal/{cartId}
  -> resposta remota aceita
  -> tela laranja imediatamente
  -> WS + polling GET /order/{orderId}/status
       APPROVED -> tela verde
       REJECTED/FAILED/... -> tela vermelha e retry
       intermediário -> permanece laranja
```

O loading cobre apenas a criação/envio da cobrança. Não espera botão verde, cartão, senha ou aprovação. A tela laranja explica que cancelar apenas Débito/Crédito permite escolher novamente, e oferece `CANCELAR COMPRA` para cancelamento integral.

`CompraSession` mantém `generation`, tentativa local, `cartId`, `orderId`, `paymentId`, `paymentAttemptId`, intenção de cancelamento, último status e `payment_in_flight`. Status e callbacks divergentes são ignorados.

### Ciclo de `payment_in_flight`

| Mudança | Pontos reais |
|---|---|
| vira `True` | `begin_payment`, `restore_pending_payment`, `adopt_backend_payment` e status intermediário em `apply_status` |
| permanece `True` | timeout ambíguo, reconnect, polling degradado e cancelamento não confirmado |
| vira `False` | status aprovado ou falha terminal confirmada, `prepare_retry` e reset/finalização |
| persistência | `_persist_payment` grava `active_payment`; resultado terminal limpa o checkpoint |

Não há uma segunda flag global `payment_active`. As guardas consultam `CompraSession.payment_in_flight` e, em pontos operacionais, também IDs/estado. O log anteriormente ambíguo está separado no código atual: pagamento ativo registra IDs/status; carrinho vazio possui mensagem própria.

### Cancelamento integral

`POST /pagamento/terminal/order/{orderId}/cancelamento?terminalId=...` é chamado em worker. O Terminal só limpa após status terminal confirmado. Timeout/erro mantém `CANCELLING`, tela laranja e polling. O backend real persiste a intenção, reconcilia e não inventa cancelamento.

### Recovery

- checkpoint `active_payment` é gravado antes do worker financeiro;
- `cartId` é persistido antes do POST de pagamento;
- startup restaura checkpoint e consulta o backend;
- sem checkpoint, startup ainda consulta pagamento ativo por Terminal;
- reconnect WebSocket sempre dispara consulta HTTP;
- tentativa conhecida usa status por Order; tentativa desconhecida usa descoberta por Terminal;
- depois de falhas repetidas, polling passa de 10 s para 30 s e não libera nova compra.

### Timers

| Timer | Duração | Dono | Efeito |
|---|---:|---|---|
| sessão global | 10 min | `CompraSession` | expira compra; com pagamento tenta cancelamento/reconciliação |
| polling | 10/30 s | `PagamentoScreen` | consulta status |
| operação | 30 s | `PagamentoScreen` | abandona loading, não inventa resultado |
| recheck laranja | 90 s | `PagamentoScreen` | reforça instrução e reconcilia |
| graça final | 30 s | `PagamentoScreen` | mantém recovery conservador |
| retorno de falha | 8 s | `PagamentoScreen` | volta ao carrinho após falha definitiva |
| pós-compra | 120 s | `ConfirmacaoScreen` | finaliza experiência aprovada quando ociosa |

O timer global para em aprovação. Aprovação durante timeout/cancelamento vence e entra uma única vez na tela verde.

## 7. Pós-compra

Após aprovação, `ConfirmacaoScreen` conserva `orderId` em `post_purchase_order_id` e oferece:

- `FINALIZAR` — implementado;
- `ENVIAR POR E-MAIL` — implementado;
- `ENVIAR POR WHATSAPP` — implementado;
- `ADICIONAR CPF` — visível e desabilitado.

E-mail e WhatsApp usam teclados touch, worker e somente `POST /comprovante` no Spring. O Terminal não conhece FastAPI/n8n. Destino é mascarado no log. Erro de comprovante mantém `SUCCESS`/aprovação e permite voltar.

Não existe fluxo “Deseja salvar no histórico?”, QR do app ou CPF de histórico. O `TecladoScreen` de nome/CPF é legado, não possui integração e contém navegação quebrada para uma tela de login não adicionada ao stack.

## 8. HTTP e WebSocket

### Chamadas reais do Terminal

| Terminal chama | Backend existe | Método | Contrato no código | Situação |
|---|---:|---|---|---|
| `/terminal/serial/{serial}` | sim | GET | `TerminalActivationResponse` | compatível |
| `/terminal/{id}/bootstrap` | sim | GET | `TerminalBootstrapResponse` | compatível |
| `/terminal/{id}/factory-reset/started` | sim | POST | 204 | compatível |
| `/terminal/{id}/factory-reset/completed` | sim | POST | 204 | compatível |
| `/produtos/sync` | sim | GET | `uuidTerminal`, `lastSync` -> `ProdutoSyncResponse` | compatível |
| `/carrinho` | sim | POST | `CarrinhoRequest` | compatível |
| `/pagamento/terminal/{cartId}` | sim | POST | `PointPaymentResponse` | compatível |
| `/pagamento/terminal/{terminalId}/ativo` | sim | GET | `PaymentStatusResponse` ou 204 | compatível |
| `/pagamento/terminal/order/{orderId}/cancelamento` | sim | POST | `terminalId` -> `PaymentStatusResponse` | compatível |
| `/order/{orderId}/status` | sim | GET | `terminalId` -> `PaymentStatusResponse` | compatível |
| `/comprovante` | sim | POST | `ComprovanteRequest` -> `ComprovanteEnvioResponse` | compatível |
| `/checkout/carrinho` e `/checkout/qrcode` | sim | GET | checkout app legado | existe, sem entrada ativa |
| `/terminal/health` | sim | GET | health/latência | compatível |
| `/terminal/telemetry` | sim | POST | `TerminalTelemetryRequest` | compatível |
| `/usuarios/anonimo` | não | POST | tela de login legada | incompatível, não navegável |
| `/terminal/customer-link/consume` | sim | POST | token opaco + `cartId`; device credential define o Terminal | compatível/testado |
| `/terminal/coupons/apply` | sim | POST | token + Terminal/Order | Terminal não chama |

### WebSocket

- `/payment-socket/{terminalId}`: recebe `PAYMENT_STATUS`, `PRODUCT_SYNC_REQUIRED` e reset; reconecta a cada 5 s.
- `/terminal-socket`: heartbeat independente, espera `HEARTBEAT_ACK` correlacionado.

Os dois sockets têm finalidades distintas. O WebSocket de pagamento é acelerador; polling/recovery HTTP é a fonte de reconciliação.

O contrato atual é inseguro: canais e a maioria dos endpoints operacionais não autenticam o dispositivo. O backend permite origem `*`; uma nova sessão com o mesmo terminal sobrescreve a anterior no mapa do handler.

## 9. Threads, timers e estado

### Fora da thread da UI

- ativação (`QThread`);
- Point/status/recovery/cancelamento/comprovante/checkout app (`QThread`);
- sync (threads Python scheduler + worker);
- heartbeat (thread Python);
- monitor de internet (`QThread`);
- telemetria (thread Python);
- Wi-Fi e display (`QThread`).

Não foram encontrados `requests.*` lentos no fluxo ativo da thread Qt. As chamadas diretas remanescentes estão dentro de workers ou em telas legadas não navegáveis.

Todos os requests encontrados têm timeout: ativação/lifecycle 5 s, sync e catálogo legado 10 s, monitor de internet/rede 3 s, pagamento `(connect=5 s, read=20 s)`, comprovante `(5 s, 45 s)`, telemetria 5 s e login legado 2 s. WebSockets também configuram timeout de ACK/receive. Não há separação connect/read em ativação, sync, lifecycle e telemetria.

### Estado compartilhado

- `MainWindow.compra_session`: estado canônico da sessão/pagamento;
- `TerminalScreen.carrinho`: itens visuais em memória;
- `PagamentoScreen`: workers/timers da UI financeira;
- `SyncService`: flags protegidas por lock;
- SQLite: catálogo e checkpoint financeiro;
- `terminal.json`: identidade de instalação.

Fragilidades: workers financeiros concluídos não são removidos com `deleteLater`; referências são substituídas ao longo da operação. Shutdown aguarda apenas 500 ms por requests com timeout de até 45 s. A conexão SQLite usada pelo scanner fica na UI enquanto o sync escreve por outra conexão, sem WAL; um lock pode bloquear a leitura da UI pelo timeout padrão.

## 10. Kiosk, display e Raspberry

O código consome `ESC`, rejeita `closeEvent` não autorizado, oculta o cursor e oferece saída apenas após autenticação admin. `Alt+F4` chega ao `closeEvent` e é recusado.

Entretanto o entry point executa `setFixedSize(1024, 600)` + `show()`. `showFullScreen()` está comentado. O smoke confirmou `fullscreen=False`, em divergência direta com a documentação.

Display usa `wlr-randr` em Wayland/wlroots e `xrandr` em X11, detecta output e aplica timeout. `start.sh` reaplica orientação salva, mas o repositório não contém unit systemd, autostart labwc, instalador de dependências do SO, regras udev, watchdog ou política de log/rotação.

Wi-Fi usa `nmcli` sem shell, passa senha por stdin e sanitiza erros. Acesso fica atrás do menu admin, que por sua vez só é alcançável pelo logo da Home. Primeira ativação offline não oferece caminho para Wi-Fi.

## 11. Telemetria e logging

Telemetria coleta em background:

- CPU, temperatura, RAM, disco, load e uptime;
- subtensão, throttling, frequency cap e limite térmico via `vcgencmd`;
- interface, SSID, IP, sinal, alcance e latência da API;
- versão, uptime, WebSocket, sync, compra e pagamento;
- resolução e orientação.

Sensor/comando ausente vira `null`. A thread não bloqueia a UI e descarta falhas até o ciclo seguinte.

Logging usa `logging.basicConfig` em stdout, sem arquivo rotativo ou formato estruturado. IDs de Terminal/Order/tentativa/status aparecem, como necessário para correlação. Destinos de comprovante são mascarados e senha Wi-Fi/admin não é logada. Ainda existem `print` no bootstrap e helpers legados.

Handlers silenciosos encontrados:

- `PaymentListener.stop`: ignora erro ao fechar socket durante shutdown;
- `SystemMetricsCollector`: ignora falhas esperadas de sensores/procfs e devolve `null`;
- `NetworkMetricsCollector`: ignora falha de nmcli/backend e devolve estado indisponível;
- `TerminalInfo`: ignora falhas nos fallbacks de serial e devolve `UNKNOWN`/`0.0.0.0`;
- `PagamentoScreen._disconnect_worker_callbacks`: ignora sinal já desconectado/destruído;
- `LoginScreen`: possui `except:` nu em fluxo legado não navegável.

Nos fluxos ativos de sync, pagamento, persistência e UI, exceções relevantes são registradas ou propagadas; não foi encontrado `except Exception: pass` escondendo falha financeira ativa.

## 12. Artefatos legados

- `LoginScreen`: não entra no stack; endpoint `/usuarios/anonimo` não existe; contém `except:` nu.
- `TecladoScreen`: é adicionado ao stack, mas não tem entrada ativa nem integração; cancelamento referencia `parent.login`, não criado.
- `AppPaymentScreen`: checkout por QR existe, mas não há botão/rota ativa no carrinho.
- `Produtos.get_produtos_api`: helper paginado direto, não usado pelo sync atual e ainda usa `print`.

Esses artefatos não são features implementadas.

## 13. Evidência de validação

- `PRAGMA integrity_check`: `ok`.
- `.venv/bin/python -m compileall -q .`: sucesso.
- `.venv/bin/python -m unittest discover -s tests -q`: 184 testes, todos aprovados.
- smoke Qt offscreen development: `1024x600`, `fullscreen=False`.
- smoke Qt offscreen production: `fullscreen=True`; o plugin offscreen expõe tela virtual `800x600`, portanto a confirmação física `1024x600` permanece no roteiro Raspberry.
- `./mvnw -q test` no backend: aprovado, inclusive handshake autenticado.
- nenhuma cobrança real, alteração de rede, rotação física ou chamada FastAPI/n8n foi executada.
