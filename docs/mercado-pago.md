# Mercado Pago Point no Terminal Python

Voltar para [o índice](00-index.md).

O Python nunca chama o Mercado Pago e não armazena credenciais. `PAGAR AGORA` envia o carrinho ao backend e chama `POST /pagamento/terminal/{carrinhoId}`. O backend deriva conta da empresa e `mercadoPagoTerminalId` do terminal, cria/reutiliza a Order e envia a cobrança Point.

A orientação “pressione o botão verde” só aparece após `PointPaymentResponse` bem-sucedido. Ela descreve uma ação física do cliente; o Python não tenta comandar esse botão.

Estados internos consumidos:

- `WAITING_PAYMENT` e `ACTION_REQUIRED`: continuar aguardando;
- `APPROVED`: sucesso e limpeza;
- `REJECTED`, `CANCELLED`, `EXPIRED`, `REFUNDED`: tentativa encerrada e retorno possível ao carrinho.

O backend converte `created`, `at_terminal`, `processed`, `failed`, `canceled`, `expired`, `refunded` e `action_required`. O cliente não interpreta `status_detail` nem meio de pagamento.

O endpoint Point é idempotente por carrinho/Order. Não existe endpoint operacional de cancelamento disponível ao terminal; por isso timeout ou desconexão nunca são convertidos localmente em recusa.

WebSocket é apenas tempo real. Conexão/reconexão com pagamento ativo e polling de 10 segundos consultam o backend, que reconcilia `Order.mpOrderId` no Mercado Pago. O Terminal preserva IDs em memória, mostra “Verificando pagamento”, não recebe credenciais e só habilita nova tentativa após falha financeira definitiva.
