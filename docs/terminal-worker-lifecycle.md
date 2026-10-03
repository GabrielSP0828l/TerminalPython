# Lifecycle de workers

Atualizado em 27 de setembro de 2026. Relacionados: [[arquitetura]], [[fluxo-compra]] e [[websocket]].

## Inventário

| Área | Implementação |
|---|---|
| ativação | `ActivationCheckThread` reutilizado e referenciado pela tela |
| Point | `PointCheckoutWorker` |
| status/recovery/resume/cancelamento | quatro `QThread` financeiros correlacionados |
| comprovante/app checkout | `ReceiptSendWorker`, `AppCheckoutWorker` |
| Wi-Fi/display | `WifiWorker`, `DisplayWorker` |
| lifecycle remoto | `TerminalLifecycleCheckThread` |
| conectividade | `InternetMonitor` |
| payment WebSocket | `PaymentListener` |
| sync/heartbeat/telemetria | threads Python com stop event/lock |

## Padrão adotado

Workers Qt ficam em atributo do dono, nunca apenas em variável local. `finished` limpa a referência somente se ela ainda aponta para aquele worker e chama `deleteLater`. Wi-Fi/display usam token de geração; pagamento usa tentativa, Order e PaymentAttempt. Callbacks antigos não alteram sessão nova.

Single-flight continua aplicado a pagar, status, recovery, cancelamento, comprovante, Wi-Fi, display, lifecycle e sync. Botões são desabilitados antes do início quando aplicável.

No shutdown, timers param primeiro; workers recebem `requestInterruption` e a espera acompanha o maior timeout de rede relevante. Isso não cancela `requests` já em kernel, mas evita destruir `QThread` enquanto a chamada limitada ainda executa. Threads Python usam event/join limitado.

Nenhum `requests.get/post` lento foi introduzido na main thread. O acesso SQLite do scanner concorrente ao sync ainda merece evolução específica (WAL/cache/worker) e permanece no backlog.
