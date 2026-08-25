# Fluxo atual da compra

Voltar para [o índice](00-index.md).

## Sessão global

`CompraSession` é a fonte de estado operacional da compra em memória. O prazo único de 15 minutos começa no primeiro produto válido escaneado e não reinicia ao abrir pagamento Point ou pagamento no app. Ela guarda geração, tentativa, `cartId`, `orderId`, `paymentId`, estado e instante inicial.

## Scanner e lista

1. `TerminalScreen.readProduct` busca o código no cache SQLite ativo.
2. O primeiro scan cria uma linha com quantidade 1 e inicia a sessão.
3. Novo scan do mesmo código incrementa a quantidade.
4. Não existem botões manuais `+`/`-`.
5. O botão `x` preserva o comportamento anterior: remove a linha inteira.
6. Se a última linha for removida, a sessão volta a `IDLE`.

## Pagar agora — Point

```text
TerminalScreen
  -> PagamentoScreen (loading)
  -> worker: POST /carrinho
  -> worker: POST /pagamento/terminal/{carrinhoId}
  -> PointPaymentResponse com orderId/status
  -> orientação para pressionar o botão verde da maquininha
  -> WebSocket + GET correlacionado de status
```

A segunda chamada só retorna com sucesso depois que o backend aceitou/enviou a cobrança Point e persistiu os dados disponíveis. Nenhuma credencial Mercado Pago existe no Python.

`WAITING_PAYMENT` e `ACTION_REQUIRED` continuam aguardando. `APPROVED` abre a `ConfirmacaoScreen`; `REJECTED`, `CANCELLED`, `EXPIRED` e `REFUNDED` informam a falha e permitem voltar à lista com os itens locais. Eventos de outra Order ou terminal são ignorados.

## Falha e idempotência

O botão não inicia outra tentativa enquanto `payment_in_flight` estiver ativo. Se a resposta do início Point for perdida após o carrinho ser criado, o cliente repete somente o `POST` Point com o mesmo `carrinhoId`; o backend reutiliza a Order e a chave idempotente da Order. Falha anterior ao envio Point preserva a lista e libera nova tentativa.

## Timeout

Ao zerar o relógio:

- sem tentativa remota, a compra local é limpa e o terminal volta ao início;
- com `orderId`, o terminal consulta o backend antes de concluir;
- com `cartId` e resposta Point incerta, repete idempotentemente o início para recuperar o `orderId`;
- estado ainda intermediário mantém a tela bloqueada e continua reconciliando, pois não existe endpoint operacional de cancelamento Point;
- aprovação durante a verificação vence o timeout; eventos antigos são rejeitados pela Order atual.

## Aprovação e limpeza

`ConfirmacaoScreen` mostra “Pagamento aprovado / Compra concluída” por cinco segundos. `MainWindow.reset_compra()` interrompe espera, limpa carrinho, linhas, totais e IDs/timers da sessão, preservando UUID, ativação, configurações e cache de produtos.

## Pagar no app

O fluxo foi preservado. HTTP e geração do QR agora rodam em `QThread`, sem alterar widgets fora da UI, e o contador usa o mesmo prazo global. Cancelar retorna à lista. A conclusão financeira completa do checkout pelo app continua uma pendência do contrato backend.
