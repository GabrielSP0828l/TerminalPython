# Mercado Pago Point no Terminal Python

Voltar para [[00-index]]. Fluxo completo em [[fluxo-compra]], API em [[api-backend]] e transporte em [[websocket]].

O Terminal nunca consulta o Mercado Pago e nunca armazena credenciais. Ele inicia ou reutiliza a cobrança pelo backend e consome `PAYMENT_STATUS` por WebSocket ou HTTP.

WebSocket é o canal de tempo real. Ao conectar/reconectar com `CompraSession.payment_in_flight=true`, a tela mostra “Verificando pagamento” e consulta `GET /order/{orderId}/status?terminalId=...`. Enquanto aguarda, repete a consulta a cada 10 segundos. O backend reconcilia `Order.mpOrderId` com a API Point e responde `PaymentStatusResponse`.

- `WAITING_PAYMENT`/`ACTION_REQUIRED`: mantém a espera e os IDs;
- `APPROVED`: abre a tela verde com `checked.svg`;
- `REJECTED`, `CANCELLED`, `EXPIRED` ou `REFUNDED`: abre a tela vermelha com `error.svg` e permite retorno ao carrinho;
- indisponibilidade do backend/Mercado Pago: mostra confirmação/reconexão, sem inventar recusa.

Uma nova tentativa só começa depois de falha definitiva. Oscilação de rede ou resposta ambígua preserva `cartId`/`orderId` e reutiliza a cobrança anterior; nenhuma chave de idempotência é criada no Python.
