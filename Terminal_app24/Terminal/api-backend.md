# APIs usadas pelo terminal

Voltar para [o índice](00-index.md).

Todas as operações de compra usam timeout `(connect=5s, read=20s)` em `PurchaseApi` e workers Qt. Erros técnicos são logados e a interface recebe mensagens amigáveis.

| Situação | Método e URL | Body/headers | Resposta | Responsável |
| --- | --- | --- | --- | --- |
| COMPATÍVEL | `GET /terminal/serial/{serial}` | sem body; timeout 5s | `TerminalActivationResponse` | `ActivationCheckThread` |
| COMPATÍVEL | `GET /terminal/{terminalId}/bootstrap` | sem body; timeout 5s | lifecycle autoritativo | `TerminalLifecycleApi` |
| COMPATÍVEL | `POST /terminal/{terminalId}/factory-reset/started` | sem body; timeout 5s | 2xx idempotente | `TerminalLifecycleApi` |
| COMPATÍVEL | `POST /terminal/{terminalId}/factory-reset/completed` | sem body; timeout 5s | 2xx idempotente | recibo persistente no startup/ativação |
| COMPATÍVEL | `GET /produtos/sync?uuidTerminal={uuid}&lastSync={Instant opcional}` | sem body; timeout 10s | `ProdutoSyncResponse {syncAt, fullSync, changes}` | `SyncService` |
| COMPATÍVEL | `GET /terminal/health` | sem body; timeout 3s | health leve para alcance/latência | `NetworkMetricsCollector` |
| COMPATÍVEL | `POST /terminal/telemetry` | UUID e blocos de saúde; timeout 5s | estado aceito/classificado | `TelemetryService` |
| COMPATÍVEL | `WS /terminal-socket` | `{terminalId,status}` a cada 10s | `HEARTBEAT_ACK {terminalId,status,lastPing}` após persistência | `TerminalSocket` |
| COMPATÍVEL | `POST /carrinho` | `CarrinhoRequest {terminalId, items}` | `CarrinhoResponseDTO` | `PurchaseApi` |
| COMPATÍVEL | `POST /pagamento/terminal/{carrinhoId}` | sem body | `PointPaymentResponse` | `PurchaseApi.start_point/resume_point` |
| COMPATÍVEL | `GET /order/{orderId}/status?terminalId=...` | sem body | `PaymentStatusResponse` correlacionado/reconciliado | `PurchaseApi.get_order` |
| COMPATÍVEL | `GET /pagamento/terminal/{terminalId}/ativo` | sem body | `PaymentStatusResponse` ou `204` | `PurchaseApi.get_active_payment` |
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

As respostas Point também incluem `remoteOrderId` e `cancellationRequested`. O primeiro é somente evidência/correlação exibida em log; não é usado pelo Terminal para chamar o provedor. O segundo restaura `CANCELLING` após restart.

Cancelamento integral usa `POST /pagamento/terminal/order/{orderId}/cancelamento?terminalId={uuid}` sem body. A resposta é `PaymentStatusResponse`. Status não terminal com `cancellationRequested=true` significa “pedido persistido, resultado ainda inconclusivo”; não autoriza Home nem nova cobrança.

No endpoint de status, `paymentAttemptId` identifica a tentativa local e `paymentId` é alias legado. `cartId` recompõe a correlação e `amount` permite mostrar o total aprovado depois de um restart sem persistir uma cópia local do carrinho. A sessão ignora evento de outra tentativa quando já conhece a corrente. `reconciled=true` informa consulta remota, não aprovação.

Se outra Order intermediária já pertence ao Terminal, o POST responde `409` com `code=PAYMENT_ALREADY_ACTIVE`, `orderId`, `paymentAttemptId`, `cartId` e `paymentStatus`. O cliente trata a resposta como recuperação da tentativa existente, nunca como permissão para limpar a flag ou criar outra cobrança. O endpoint por Terminal é usado no startup e reconnect para cobrir perda de memória/evento; `204` é a confirmação autoritativa de que não existe tentativa ativa.

## CPF e comprovantes

O backend real continua sem campo/endpoint para associar CPF a Order/Pagamento. Por isso `ADICIONAR CPF` fica visível, mas desabilitado; o Terminal não persiste CPF localmente nem atribui significado fiscal.

Comprovantes usam exatamente `POST /comprovante`, sem prefixo global. O JSON contém `terminalId`, `pedidoId`, `tipoEnvio` (`WHATSAPP` ou `EMAIL`) e `destinatario`. O backend exige Order e PaymentAttempt `PROCESSED`, `paidAt` e correspondência Order/Terminal. Resposta aceita pelo cliente: `status=ENVIADO` ou `JA_ENVIADO`, com o mesmo `pedido`; resposta divergente é falha.

Telefone amigável é normalizado centralmente para DDI `55`; e-mail recebe validação básica compatível com o Java. Nenhum `empresaId`, item, preço, total ou status declarado pelo cliente é enviado. O timeout exclusivo de comprovante é `(connect=5s, read=45s)`, superior ao read timeout interno documentado do Spring. FastAPI e n8n não aparecem em URL/configuração do Terminal.

## Carrinho

Cada item envia `productId`, quantidade/peso como strings decimais exatas, `expectedUnitPrice` e `codigoBarras`. O backend valida tenant/barcode e recalcula valores.

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

`UPSERT` atualiza produto e substitui todos os barcodes locais na mesma transação. `REMOVE` desativa o item e remove seus códigos escaneáveis. O cursor é `Instant` UTC do backend.

Uma requisição sem `lastSync` deve receber `fullSync=true`; o cliente rejeita incremental nesse caso. `200 + fullSync=true + changes=[]` é sucesso válido para condomínio sem produtos disponibilizados, diferente de Terminal inexistente (`404`), erro backend (`500`) ou timeout. O Terminal só usa `lastSync` quando seu marcador local confirma um FULL anterior e a contagem do cache é consistente.
