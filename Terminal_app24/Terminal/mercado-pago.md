# Mercado Pago Point no Terminal Python

Voltar para [[00-index]]. Fluxo completo em [[fluxo-compra]], API em [[api-backend]] e transporte em [[websocket]].

O Terminal nunca consulta o Mercado Pago e nunca armazena credenciais. Ele inicia ou reutiliza a cobrança pelo backend e consome `PAYMENT_STATUS` por WebSocket ou HTTP.

WebSocket é o canal de menor latência, mas HTTP é o canal autoritativo de recuperação. Ao conectar/reconectar, a tela consulta a Order conhecida ou descobre a tentativa em `GET /pagamento/terminal/{terminalId}/ativo`, inclusive quando o processo perdeu o estado em memória. O backend reconcilia com a API Point e responde `PaymentStatusResponse`.

- `WAITING_PAYMENT`/`ACTION_REQUIRED`: mantém a espera e os IDs;
- `APPROVED`: abre a tela verde com `checked.svg`;
- `REJECTED`, `CANCELLED`, `EXPIRED` ou `REFUNDED`: abre a tela vermelha com `error.svg` e permite retorno ao carrinho;
- indisponibilidade do backend/Mercado Pago: mostra confirmação/reconexão, sem inventar recusa.

Uma nova tentativa só começa depois de falha definitiva. Oscilação de rede ou resposta ambígua preserva `cartId`/`orderId` no SQLite e reutiliza a cobrança anterior; nenhuma chave de idempotência é criada no Python. `PAYMENT_ALREADY_ACTIVE` fornece os IDs da tentativa existente e é tratado como recuperação.

## Deadline local durante cobrança

O fim dos 10 minutos encerra a experiência local, mas não inventa um resultado financeiro. Se o POST Point ainda está em execução, o Terminal bloqueia a UI e aguarda seu callback delimitado. Com `orderId`, usa somente `GET /order/{orderId}/status?terminalId=...`; com resposta ambígua e apenas `cartId`, conserva o fluxo idempotente já existente do backend para recuperar a mesma Order. O timeout, sozinho, nunca inicia uma nova tentativa.

`APPROVED` recebido durante a reconciliação prevalece e abre sucesso. `REJECTED`, `CANCELLED`, `FAILED`, `EXPIRED` e `REFUNDED` são estados terminais, mas somente cancelamento solicitado pelo Terminal e confirmado remotamente retorna direto à Home. Estado intermediário mantém a tela laranja e o polling correlacionado.

O botão `CANCELAR COMPRA` chama `POST /pagamento/terminal/order/{orderId}/cancelamento?terminalId=...`. O backend persiste `cancellationRequested` e a chave idempotente antes de chamar `POST /v1/orders/{remoteOrderId}/cancel`. Falha ou timeout não limpa IDs. Como a API Point permite cancelamento por API apenas em `created`, uma Order já `at_terminal` pode exigir cancelamento na maquininha; a UI orienta essa ação e continua reconciliando até estado terminal.

## Limite entre aprovação e comprovante

O comprovante começa somente depois que o backend converte o estado real em aprovação interna. `_handle_payment_approved` é a entrada única da interface, inclusive após reconciliação, e para os timers/polling financeiros antes de abrir o pós-compra. Falha de `POST /comprovante` não altera `CompraSession.state=SUCCESS`, `orderId`, Order, PaymentAttempt ou estoque e nunca retorna o cliente ao pagamento. `FINALIZAR` encerra apenas a experiência local; não chama cancelamento remoto.
