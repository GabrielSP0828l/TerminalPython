# Contratos Terminal -> Backend

Atualizado em 28 de setembro de 2026. A fonte normativa HTTP é o OpenAPI do
backend; este documento registra como o cliente Python o consome.

## Identidade do equipamento

Operação diária usa exclusivamente:

```http
X-Terminal-Token: <device credential individual>
X-Terminal-Id: <terminalId>
```

`X-Terminal-Id` só é enviado onde o contrato o requer. A credential é lida de
`APP247_DEVICE_CREDENTIAL_PATH`, instalado atomicamente e com modo `0600`. Ela não
fica no SQLite, `terminal.json`, logs ou Git.

`TERMINAL_INTERNAL_TOKEN` existe somente para
`POST /terminal/{terminalId}/credential/migrate`, quando
`LEGACY_TERMINAL_AUTH_ENABLED=true`. Não há fallback operacional.

- 401: credential ausente, inválida, rotacionada ou revogada; bloquear novas
  vendas e exigir reprovisionamento.
- 403: identidade válida, mas equipamento/tenant/operação não autorizados; não
  apagar a credential e bloquear operação.
- Após reprovisionamento administrativo, reiniciar o processo do Terminal.

## Ativação e provisionamento

1. `GET /terminal/serial/{serial}` é descoberta pública e nunca retorna segredo.
2. O administrador provisiona/rotaciona uma credential e a instala no caminho
   local, ou a migração explicitamente habilitada troca o segredo legado uma vez.
3. Somente depois da persistência local bem-sucedida o Terminal inicia workers.

A resposta de migração contém `terminalId`, `credential`, `version` e
`createdAt`; o campo `credential` é aceito somente se o `terminalId`
coincidir e é persistido antes de ativar a operação.

## HTTP

| Fluxo | Método/path | Identidade/payload | Resposta consumida |
|---|---|---|---|
| Sync | `GET /produtos/sync` | query `uuidTerminal,lastSync?` | `syncAt,fullSync,changes` |
| Telemetria | `POST /terminal/telemetry` | `terminalUuid,capturedAt,system,network,application,display` | 200/202/204 |
| Lifecycle | `GET /terminal/{id}/bootstrap` | credential + mesmo id | estado conhecido |
| Carrinho | `POST /carrinho` | `terminalId,items,cpf?` | carrinho precificado |
| Pagamento | `POST /pagamento/terminal/{cartId}` | credential + `X-Terminal-Id` | `PointPaymentResponse` |
| Ativo | `GET /pagamento/terminal/{id}/ativo` | credential do mesmo id | status ou 204 |
| Status | `GET /order/{orderId}/status?terminalId=...` | ownership do Terminal | `PaymentStatusResponse` |
| Cancelar | `POST /pagamento/terminal/order/{orderId}/cancelamento` | query `terminalId` | status reconciliado |
| Comprovante | `POST /comprovante` | terminal/order/canal/destino | ENVIADO/JA_ENVIADO |

O cliente não envia empresa, condomínio, total autoritativo ou usuário. Valores
visuais não substituem o snapshot financeiro do backend.

## Sync

`syncAt` é Instant UTC ISO-8601 com offset/`Z`. FULL sem produtos é
`200 {fullSync:true,changes:[]}` e limpa o catálogo antigo na mesma transação.
Incrementais substituem todos os barcodes do UPSERT. JSON adicional é tolerado;
ausência/tipo incorreto dos campos obrigatórios reprova a resposta sem avançar o
cursor.

`PRODUCT_SYNC_REQUIRED` recebido no socket de pagamento chama
`request_sync`; o lock coalesce eventos concorrentes em um único ciclo pendente.

## WebSocket e STOMP

- `/terminal-socket`: header `X-Terminal-Token`; payload heartbeat mantém o
  próprio `terminalId`; ACK exige tipo, mesmo id e `lastPing`.
- `/payment-socket/{terminalId}`: mesma credential; recebe
  `PAYMENT_STATUS`, `PRODUCT_SYNC_REQUIRED` e hint de factory reset.
- O cliente Python suprime `Origin`, pois não é browser. A autenticação continua
  obrigatória. 401 encerra reconnect e entra em `AUTH_REQUIRED`.
- O backend oferece STOMP em `/ws` e somente subscription
  `/topic/payment/{terminalId próprio}`; SEND é negado. O Terminal atual não usa
  STOMP, portanto não mantém uma segunda pilha/identidade.

## Pagamento e recovery

`orderId`, `cartId`, `paymentAttemptId`, status e intenção de cancelamento
são persistidos no SQLite. `WAITING_PAYMENT`, `ACTION_REQUIRED`,
`PROCESSING`, `PENDING`, `UNKNOWN` e `CANCELLING` bloqueiam nova cobrança.
Timeout não significa falha: o Terminal consulta tentativa ativa/status.

`ACTIVE_PAYMENT_ATTEMPT_EXISTS` e `PAYMENT_ALREADY_ACTIVE` retomam/reconciliam
a tentativa existente. Somente resultado terminal confirmado limpa o checkpoint.
Campos JSON novos são ignorados.

## Reset e rotação

Instalação/rotação local usa substituição atômica: a credential anterior só deixa
de existir após a nova ter sido sincronizada no disco. Reset de catálogo preserva
a credential. Factory reset local remove-a; factory reset remoto conserva-a até
o ACK autenticado de `factory-reset/completed` e então a remove.
