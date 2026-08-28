# APIs usadas pelo terminal

Voltar para [o índice](00-index.md).

Todas as operações de compra usam timeout `(connect=5s, read=20s)` em `PurchaseApi` e workers Qt. Erros técnicos são logados e a interface recebe mensagens amigáveis.

| Situação | Método e URL | Body/headers | Resposta | Responsável |
| --- | --- | --- | --- | --- |
| COMPATÍVEL | `GET /terminal/serial/{serial}` | sem body; timeout 5s | `TerminalActivationResponse` | `ActivationCheckThread` |
| COMPATÍVEL | `GET /produtos/sync?uuidTerminal={uuid}&lastSync={Instant opcional}` | sem body; timeout 10s | `ProdutoSyncResponse {syncAt, fullSync, changes}` | `SyncService` |
| COMPATÍVEL | `WS /terminal-socket` | `{terminalId,status}` a cada 10s | `HEARTBEAT_ACK {terminalId,status,lastPing}` após persistência | `TerminalSocket` |
| COMPATÍVEL | `POST /carrinho` | `CarrinhoRequest {terminalId, items}` | `CarrinhoResponseDTO` | `PurchaseApi` |
| COMPATÍVEL | `POST /pagamento/terminal/{carrinhoId}` | sem body | `PointPaymentResponse` | `PurchaseApi.start_point/resume_point` |
| COMPATÍVEL | `GET /order/{orderId}/status?terminalId=...` | sem body | `PaymentStatusResponse` correlacionado/reconciliado | `PurchaseApi.get_order` |
| COMPATÍVEL | `GET /checkout/carrinho?idCarrinho=...` | sem body | sessão de checkout | `PurchaseApi.create_app_checkout` |
| COMPATÍVEL | `GET /checkout/qrcode?id=...` | sem body | `image/png` | `PurchaseApi.create_app_checkout` |
| ENDPOINT LEGADO | `POST /usuarios/anonimo` | tela sem rota ativa | endpoint ausente | `LoginScreen`, não navegável |
| ENDPOINT LEGADO | utilitário paginado em `Produtos.get_produtos_api` | variável | contrato antigo | sem chamadores |

## PointPaymentResponse

```json
{
  "type": "PAYMENT_STATUS",
  "orderId": "uuid",
  "terminalId": "uuid",
  "status": "WAITING_PAYMENT",
  "mercadoPagoStatus": "at_terminal",
  "transactionId": null,
  "statusDetail": null,
  "message": "..."
}
```

O Python consome somente o status interno. Status Mercado Pago e detalhes ficam para diagnóstico/backend.

No endpoint de status, a resposta também inclui `paymentId`, `updatedAt` e `reconciled`. `reconciled=true` informa que o backend consultou a Order Point nessa requisição; não significa aprovação. O Terminal continua decidindo a tela exclusivamente por `status`.

## CPF e comprovantes

O backend real não expõe CPF em Order/Pagamento, associação de CPF pós-compra, comprovante por e-mail ou WhatsApp. O `EmailService` atual serve autenticação/onboarding e não deve ser reutilizado implicitamente como comprovante. Não existe provider WhatsApp.

O Terminal não chama endpoint inexistente, não persiste esses dados localmente e não simula envio. A implementação futura deve ser idempotente por `orderId` e Terminal, manter credenciais no backend e tratar falha de entrega sem alterar o estado financeiro aprovado.

## Carrinho

Cada item envia `productId`, `quantity` e `receivedWeight`. Enquanto não existe integração de balança, `receivedWeight` é `null`; quantidade vem exclusivamente do número de scans. O backend recalcula valores.

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

`UPSERT` insere ou atualiza todos os campos locais. `REMOVE` é tombstone idempotente e torna o item indisponível ao scanner. Não há paginação. O cursor é `Instant` UTC gerado pelo backend; o relógio do Terminal não participa do protocolo.

Uma requisição sem `lastSync` deve receber `fullSync=true`; o cliente rejeita incremental nesse caso. `200 + fullSync=true + changes=[]` é sucesso válido para condomínio sem produtos disponibilizados, diferente de Terminal inexistente (`404`), erro backend (`500`) ou timeout. O Terminal só usa `lastSync` quando seu marcador local confirma um FULL anterior e a contagem do cache é consistente.
