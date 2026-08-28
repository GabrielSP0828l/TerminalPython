# Mercado Pago Point no Terminal Python

Voltar para [[00-index]]. Fluxo completo em [[fluxo-compra]], API em [[api-backend]] e transporte em [[websocket]].

O Terminal nunca consulta o Mercado Pago e nunca armazena credenciais. Ele inicia ou reutiliza a cobrança pelo backend e consome `PAYMENT_STATUS` por WebSocket ou HTTP.

WebSocket é o canal de tempo real. Ao conectar/reconectar com `CompraSession.payment_in_flight=true`, a tela mostra “Verificando pagamento” e consulta `GET /order/{orderId}/status?terminalId=...`. Enquanto aguarda, repete a consulta a cada 10 segundos. O backend reconcilia `Order.mpOrderId` com a API Point e responde `PaymentStatusResponse`.

- `WAITING_PAYMENT`/`ACTION_REQUIRED`: mantém a espera e os IDs;
- `APPROVED`: abre a tela verde com `checked.svg`;
- `REJECTED`, `CANCELLED`, `EXPIRED` ou `REFUNDED`: abre a tela vermelha com `error.svg` e permite retorno ao carrinho;
- indisponibilidade do backend/Mercado Pago: mostra confirmação/reconexão, sem inventar recusa.

Uma nova tentativa só começa depois de falha definitiva. Oscilação de rede ou resposta ambígua preserva `cartId`/`orderId` e reutiliza a cobrança anterior; nenhuma chave de idempotência é criada no Python.

## Deadline local durante cobrança

O fim dos 10 minutos encerra a experiência local, mas não inventa um resultado financeiro. Se o POST Point ainda está em execução, o Terminal bloqueia a UI e aguarda seu callback delimitado. Com `orderId`, usa somente `GET /order/{orderId}/status?terminalId=...`; com resposta ambígua e apenas `cartId`, conserva o fluxo idempotente já existente do backend para recuperar a mesma Order. O timeout, sozinho, nunca inicia uma nova tentativa.

`APPROVED` recebido durante a reconciliação prevalece e abre sucesso. `REJECTED`, `CANCELLED`, `FAILED`, `EXPIRED` e `REFUNDED` encerram e limpam a sessão expirada. Estado ainda intermediário após a janela de recuperação vira `RECONCILIATION_PENDING`: a tela inicial pode aparecer, mas uma nova compra continua bloqueada e o polling correlacionado prossegue.
