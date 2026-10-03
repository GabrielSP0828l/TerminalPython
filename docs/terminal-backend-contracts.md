# Matriz Terminal <-> Backend

Detalhes em [backend-contracts.md](backend-contracts.md).

| Fluxo | Terminal chama | Backend real | Auth | Request | Response | Status |
|---|---|---|---|---|---|---|
| Ativação | `GET /terminal/serial/{serial}` | TerminalController | pública, descoberta | serial path | TerminalActivationResponse | compatível |
| Device credential | `POST /terminal/{id}/credential/migrate` | TerminalController | legado explícito | header + id | credential uma vez | compatível/testado |
| Sync catálogo | `GET /produtos/sync` | ProdutoController | individual | id/cursor | full/incremental | compatível/testado |
| Heartbeat | `WS /terminal-socket` | TerminalWebSocketHandler | individual | id/status | HEARTBEAT_ACK | compatível/testado |
| Telemetria | `POST /terminal/telemetry` | TerminalTelemetryController | individual | DTO aninhado | 202 | compatível/testado |
| Lifecycle | bootstrap/reset | TerminalController | individual | mesmo id | estado/ACK | compatível/testado |
| WebSocket pagamento | `WS /payment-socket/{id}` | PaymentWebSocketHandler | individual | path próprio | eventos | compatível por contrato |
| STOMP | não utilizado | `/ws` server-push | individual | SUBSCRIBE próprio | tópico próprio | backend testado; N/A cliente |
| Carrinho/Order | `POST /carrinho` | Carrinho/Pagamento | individual | produtos/quantidade | preço backend | compatível/testado |
| Pagamento | `POST /pagamento/terminal/{cart}` | PagamentoController | individual | sem total | Order + attempt | compatível/testado |
| Status/reconciliation | ativo/status | Pagamento/Order | individual | ids correlacionados | PaymentStatusResponse | compatível/testado |
| Cancelamento | endpoint por Order | PagamentoController | individual | Order + terminal próprio | estado reconciliado | compatível/testado |
| Recovery/restart | tentativa ativa/status | backend persistente | individual | checkpoint SQLite | estado autoritativo | compatível/testado isoladamente |
| Comprovante | `POST /comprovante` | ComprovanteController | individual | destino mínimo | ENVIADO/JA_ENVIADO | compatível/testado |
| Reset | lifecycle started/completed | TerminalController | individual | marcador local | ACK | compatível/testado |

“Testado” nesta matriz significa suíte do respectivo projeto. Um ensaio com os
dois processos reais, MySQL/Redis e provider Point stubado continua requisito
separado antes do rollout.
