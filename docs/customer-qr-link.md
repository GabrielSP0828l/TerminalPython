# Vínculo da compra ao App247 por QR

## Scanner e payload

O listener HID existente continua sendo o único ponto de entrada: o scanner preenche `TerminalScreen.codigo_barras` e envia Enter. `ScannerRouter` centraliza a classificação:

- `app247://customer-link/<opaque>` → `CUSTOMER_LINK_TOKEN`;
- demais valores sem esquema URI → `PRODUCT_BARCODE`;
- vazio, envelope parcial ou URI desconhecida → `UNKNOWN`.

Não há heurística por prefixo JWT ou comprimento para distinguir cliente. Leituras repetidas de produto continuam incrementando quantidade; uma duplicação imediata do mesmo QR de cliente é suprimida. `COUPON_TOKEN` fica apenas reservado conceitualmente e não foi implementado.

## Fluxo HTTP

O QR guarda somente o token opaco de 256 bits. `CustomerLinkWorker` executa fora da thread da UI:

1. abre ou atualiza o carrinho backend (`POST /carrinho`, `POST /carrinho/empty` ou `PUT /carrinho/{id}`);
2. envia `POST /terminal/customer-link/consume` com `{"cartId":"...","token":"..."}`;
3. autentica sempre com a device credential individual em `X-Terminal-Token`;
4. descarta o token do worker no `finally`.

O body nunca envia `userId`, CPF, Empresa ou Condomínio. O Terminal não decide a identidade. O backend retorna apenas `linked`, `displayName` e `cartId`.

## UI e bloqueio financeiro

Antes do vínculo, a tela mostra “Vincule esta compra ao seu App247”. Durante a chamada mostra “Identificando cliente...”. Em sucesso mostra apenas `✓ Compra vinculada a <primeiro nome>`.

O vínculo é opcional e o fluxo anônimo não muda. Se `CompraSession.payment_in_flight` estiver ativo, um QR de cliente não chama o backend e mostra que o cliente não pode ser alterado durante o pagamento.

Mapeamento principal:

| Backend | Mensagem |
|---|---|
| `CUSTOMER_LINK_TOKEN_EXPIRED` | QR expirado. Gere um novo QR no aplicativo. |
| `CUSTOMER_LINK_TOKEN_ALREADY_USED` | Este QR já foi utilizado. Gere um novo QR. |
| `CUSTOMER_LINK_TENANT_MISMATCH` | Este QR não pode ser usado neste Terminal. |
| `CUSTOMER_ALREADY_LINKED` | Esta compra já está vinculada a outro cliente. |
| `CUSTOMER_LINK_PAYMENT_ALREADY_STARTED` | Não é possível alterar o cliente durante o pagamento. |

## Checkout, reset e recovery

O mesmo `cartId` vinculado é atualizado com os itens finais antes de `POST /pagamento/terminal/{cartId}`; não se cria outro carrinho. O request financeiro não contém usuário.

`CustomerLinkStore` persiste no SQLite somente `cart_id` e timestamps. Não persiste token QR, nome, CPF, e-mail, JWT ou credencial. Após reinício, `CustomerLinkRecoveryWorker` consulta `GET /carrinho/{id}` e recupera o estado visual do backend sem reutilizar o QR.

Cancelar/descartar a compra, concluir `APPROVED` ou iniciar nova compra limpa o estado visual/local. A Order aprovada permanece associada no backend. Recovery durante pagamento usa a Order/PaymentAttempt existente e não depende do token.
