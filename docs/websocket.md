# WebSocket atual

Voltar para [o índice](00-index.md). Heartbeat detalhado em [[heartbeat]].

## Heartbeat

`TerminalSocket`, pertencente ao lifecycle de `MainWindow`, conecta em `{WS_URL}/terminal-socket`. A cada 10 segundos envia:

```json
{"terminalId":"uuid","status":"ONLINE"}
```

O backend localiza o terminal por UUID, atualiza `status`, `update_at` e `lastPing`, força `saveAndFlush` e só então responde:

```json
{
  "type":"HEARTBEAT_ACK",
  "terminalId":"uuid",
  "status":"ONLINE",
  "lastPing":"2026-08-24T13:35:29.763624625"
}
```

O Python só registra sucesso após validar tipo, UUID e presença de `lastPing`. Falha de conexão, timeout ou ACK inválido fecha o socket e tenta novamente após 5 segundos, sem popup e sem encerrar a compra. O serviço não inicia batimentos para instalação inativa e continua independente da tela aberta.

## Pagamentos

`PaymentListener(QThread)` conecta em `{WS_URL}/payment-socket/{terminalId}`. O socket possui timeout de leitura, fechamento cooperativo e reconexão a cada cinco segundos. Sinais chegam à UI por queued connection.

O backend publica `PaymentEvent` pós-commit. Ao conectar/reconectar com compra ativa, `PagamentoScreen` mostra “Verificando pagamento” e consulta `GET /order/{orderId}/status?terminalId=...`; estados não definitivos são reconciliados pelo backend. Durante a espera existe polling HTTP de 10 segundos. Apenas `APPROVED` correlacionado libera sucesso.

## Notificação de catálogo

O mesmo canal `/payment-socket/{terminalId}` também transporta:

```json
{
  "type": "PRODUCT_SYNC_REQUIRED",
  "reason": "PRODUCT_UPDATED",
  "productId": "uuid"
}
```

`PaymentListener.route_message` separa explicitamente `PAYMENT_STATUS` de `PRODUCT_SYNC_REQUIRED`. O segundo é apenas aviso e solicita `SyncService.request_sync("WEBSOCKET_EVENT")`; nenhum produto é lido do evento. Toda conexão bem-sucedida solicita sync, usando `WEBSOCKET_CONNECTED` na primeira e `WEBSOCKET_RECONNECT` nas seguintes, para recuperar avisos perdidos enquanto offline.

Se uma sync já estiver ativa, o aviso define `sync_pending=true`. Vários avisos rápidos são coalescidos em, no máximo, uma nova execução sequencial. O canal de heartbeat permanece separado e independente.

O reparo de cache vazio não altera este roteamento: `PAYMENT_STATUS` continua exclusivo do pagamento, `PRODUCT_SYNC_REQUIRED` continua sendo apenas invalidação e conexão/reconexão continuam solicitando HTTP sync pelo coordenador serial.

## Limites restantes

Os handshakes continuam sem autenticação criptográfica e as sessões ficam na memória de uma instância do backend. Autenticação de provisionamento e operação multi-instância permanecem pendências.
