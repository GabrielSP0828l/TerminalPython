# APIs usadas pelo terminal

Voltar para [o índice](00-index.md).

Todas as rotas operacionais usam a credential individual em
`X-Terminal-Token`; quando exigido, `X-Terminal-Id` carrega o mesmo Terminal.
Todas as operações de compra usam timeout `(connect=5s, read=20s)` em
`PurchaseApi` e workers Qt. Erros técnicos são logados sem headers/body sensível
e a interface recebe mensagens amigáveis.

| Situação | Método e URL | Body/headers | Resposta | Responsável |
| --- | --- | --- | --- | --- |
| COMPATÍVEL | `GET /terminal/serial/{serial}` | sem body; timeout 5s | `TerminalActivationResponse` | `ActivationCheckThread` |
| MIGRAÇÃO | `POST /terminal/{terminalId}/credential/migrate` | token global somente com flag explícita | credential individual uma vez | `migrate_legacy_credential` |
| COMPATÍVEL | `GET /produtos/sync?uuidTerminal={uuid}&lastSync={Instant opcional}` | sem body; timeout 10s | `ProdutoSyncResponse {syncAt, fullSync, changes}` | `SyncService` |
| COMPATÍVEL | `GET /terminal/health` | sem body; timeout 3s | health leve + latência medida localmente | `NetworkMetricsCollector` |
| COMPATÍVEL | `POST /terminal/telemetry` | UUID + blocos system/network/application/display; timeout 5s | estado aceito e classificação atual | `TelemetryService` |
| COMPATÍVEL | `WS /terminal-socket` | `{terminalId,status}` a cada 10s | `HEARTBEAT_ACK {terminalId,status,lastPing}` após persistência | `TerminalSocket` |
| COMPATÍVEL | `POST /carrinho` | `CarrinhoRequest {terminalId, items}` | `CarrinhoResponseDTO` | `PurchaseApi` |
| COMPATÍVEL | `POST /pagamento/terminal/{carrinhoId}` | sem body | `PointPaymentResponse` | `PurchaseApi.start_point/resume_point` |
| COMPATÍVEL | `GET /pagamento/terminal/{terminalId}/ativo` | sem body | `PaymentStatusResponse` ou 204 | recovery |
| COMPATÍVEL | `POST /pagamento/terminal/order/{orderId}/cancelamento` | query terminalId | `PaymentStatusResponse` | cancelamento |
| COMPATÍVEL | `GET /order/{orderId}/status?terminalId=...` | sem body | `PaymentStatusResponse` correlacionado/reconciliado | `PurchaseApi.get_order` |
| COMPATÍVEL | `POST /comprovante` | `ComprovanteRequest {terminalId, pedidoId, tipoEnvio, destinatario}`; timeout `(5s,45s)` | `ComprovanteEnvioResponse` | `PurchaseApi.send_receipt` / `ReceiptSendWorker` |
| COMPATÍVEL | `GET /checkout/carrinho?idCarrinho=...` | sem body | sessão de checkout | `PurchaseApi.create_app_checkout` |
| COMPATÍVEL | `GET /checkout/qrcode?id=...` | sem body | `image/png` | `PurchaseApi.create_app_checkout` |
| ENDPOINT LEGADO | `POST /usuarios/anonimo` | tela sem rota ativa | endpoint ausente | `LoginScreen`, não navegável |
| ENDPOINT LEGADO | utilitário paginado em `Produtos.get_produtos_api` | variável | contrato antigo | sem chamadores |

## PointPaymentResponse

```json
{
  "type": "PAYMENT_STATUS",
  "orderId": "uuid",
  "paymentAttemptId": "uuid",
  "terminalId": "uuid",
  "status": "WAITING_PAYMENT",
  "mercadoPagoStatus": "at_terminal",
  "transactionId": null,
  "statusDetail": null,
  "message": "..."
}
```

O Python consome somente o status interno. Status Mercado Pago e detalhes ficam para diagnóstico/backend.

No status, `paymentAttemptId` identifica a tentativa local; `paymentId` permanece alias de compatibilidade. Eventos de tentativa diferente são ignorados quando a sessão já conhece a atual. `reconciled=true` significa consulta remota feita pelo backend, não aprovação.

## CPF e comprovantes pós-compra

CPF continua sem campo/endpoint na Order/Pagamento; o Terminal não o guarda localmente e mantém a ação desabilitada.

WhatsApp/e-mail usam `POST /comprovante` com `terminalId`, `pedidoId`, `tipoEnvio` e `destinatario`. O cliente aceita apenas `ENVIADO`/`JA_ENVIADO` para a mesma Order, usa timeout `(5s,45s)` e não envia tenant, itens, valores ou status financeiro. O Spring valida Order/PaymentAttempt, monta o snapshot e integra FastAPI/n8n; o Terminal não conhece esses serviços.

## Carrinho

Cada item envia `productId`, `quantity`, `receivedWeight`, `expectedUnitPrice` e o `codigoBarras` efetivamente lido. Decimais são strings exatas; o backend valida barcode/tenant e recalcula valores.

## Sincronização do catálogo

O backend deriva `Terminal -> Condomínio` por `uuidTerminal`; o cliente não envia empresa nem condomínio. Na primeira chamada, `lastSync` é omitido e a resposta tem `fullSync=true`. Nas seguintes, o Terminal envia exatamente o `syncAt` confirmado anteriormente:

```json
{
  "syncAt": "2026-08-24T17:00:00.123Z",
  "fullSync": false,
  "changes": [
    {
      "productId": "uuid-a",
      "operation": "UPSERT",
      "produto": {
        "id": "uuid-a",
        "codigo": "789",
        "codigoInterno": "SKU-001",
        "codigosBarras": [
          {"codigo": "789", "tipo": "EAN", "principal": true, "ativo": true},
          {"codigo": "790", "tipo": "GTIN", "principal": false, "ativo": true}
        ],
        "nome": "Produto",
        "descricao": "Descrição",
        "preco": 7.50,
        "unidadeMedida": "UN",
        "categoria": "OUTROS",
        "peso": 1,
        "pesoTolerancia": 0,
        "foto": null,
        "ativo": true,
        "quantidade": 5,
        "createdAt": "2026-08-24T10:00:00Z",
        "updatedAt": "2026-08-24T16:59:00Z"
      }
    },
    {"productId": "uuid-b", "operation": "REMOVE", "produto": null}
  ]
}
```

`UPSERT` atualiza produto e substitui seus barcodes na mesma transação. `REMOVE` é tombstone idempotente, desativa o item e elimina seus códigos do scanner. Não há paginação. O cursor é `Instant` UTC gerado pelo backend.

Uma requisição sem `lastSync` deve receber `fullSync=true`; o cliente rejeita incremental nesse caso. `200 + fullSync=true + changes=[]` é sucesso válido para condomínio sem produtos disponibilizados, diferente de Terminal inexistente (`404`), erro backend (`500`) ou timeout. O Terminal só usa `lastSync` quando seu marcador local confirma um FULL anterior e a contagem do cache é consistente.
# Hardening de autenticação do Terminal (28/09/2026)

O valor enviado é a credential individual, não `TERMINAL_INTERNAL_TOKEN`.
`/terminal/serial/{serial}` permanece bootstrap público e não autoriza operação.
Veja [terminal-device-security.md](terminal-device-security.md).
