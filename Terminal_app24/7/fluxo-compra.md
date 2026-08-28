# Fluxo real da compra

Voltar para [[00-index]]. Contratos em [[api-backend]] e Point em [[mercado-pago]].

## Estado local

`TerminalScreen.carrinho` é a fonte única dos itens; `CompraSession` mantém prazo, geração, tentativa e IDs remotos. A tela de confirmação lê o mesmo carrinho e reconstrói somente widgets visuais.

## Fluxo ativo

```text
scanner -> SQLite -> carrinho visual
  -> FINALIZAR (sem rede)
  -> CONFIRME SUA COMPRA
      -> VOLTAR: mesmo carrinho
      -> CONFIRMAR E PAGAR
          -> POST /carrinho
          -> POST /pagamento/terminal/{carrinhoId}
          -> maquininha Point
          -> WebSocket + GET correlacionado
          -> cobrança aceita: atenção laranja/maquininha
          -> PROCESSING: loading
          -> falha definitiva: erro vermelho/retry
          -> APPROVED: sucesso verde
              -> FINALIZAR: reset
```

“Pagar no App” saiu da tela principal. A classe legada permanece sem rota ativa. Crédito/débito/PIX não foram recriados.

## Segurança financeira

A resposta de criação da cobrança é intermediária. Apenas `APPROVED` da Order e Terminal ativos libera a compra. Falha preserva itens e mostra “Tentar novamente”. Timeout com IDs remotos reconcilia antes de liberar. Backend continua responsável por Order, Pagamento, credenciais Mercado Pago e estoque.

Enquanto `CompraSession.payment_in_flight=true`, `cartId`, `orderId` e `paymentId` não são limpos por perda de socket ou indisponibilidade do backend. Ao conectar/reconectar, o Terminal mostra “Verificando pagamento” e chama `GET /order/{orderId}/status`; enquanto aguarda também repete a consulta a cada 10 segundos. `WAITING_PAYMENT` conserva a tela, `APPROVED` abre `checked.svg` e falha definitiva abre `error.svg`.

## Expiração global da sessão

`CompraSession` mantém o único deadline de 600 segundos. No primeiro tick com `remaining <= 0`, ela publica `00:00`, para o `QTimer`, marca a sessão inativa e emite `expired(generation)` uma única vez. O sinal é recebido por `MainWindow`, nunca pelas telas de lista ou confirmação.

```text
remaining <= 0
  -> interações bloqueadas
  -> MainWindow processa a geração ativa
      -> sem tentativa/IDs remotos: reset_compra -> boas-vindas
      -> request Point ainda executando: aguarda callback delimitado
      -> cartId/orderId existente: PagamentoScreen reconcilia
          -> APPROVED: sucesso
          -> falha definitiva: reset -> boas-vindas
          -> intermediário/incerto: RECONCILIATION_PENDING
```

O reset central limpa o carrinho, IDs, flags, timers visuais e tokens da tentativa. Scanner, `FINALIZAR` e `CONFIRMAR E PAGAR` ficam bloqueados desde a expiração. Uma nova entrada na tela de compra permite um novo scan, que cria outra `generation`, reinicia o deadline completo e não aceita callbacks da tentativa anterior.

## UX

`Finalizar` apenas abre o resumo. `Confirmar e pagar` é desabilitado imediatamente e muda para “Preparando...” antes do worker. A cobrança aceita mostra a instrução da Point em laranja; processamento usa loading; falha definitiva usa vermelho e preserva o carrinho; aprovação usa verde.

No display de 7 polegadas (`1024×600`), o carrinho usa grid rolável de três colunas e footer fixo; a sessão global continua limitada a 10 minutos. A disposição e as métricas visuais estão em [[telas]].

Não existe mais reset automático após `APPROVED`. A Order, Payment e compra local permanecem referenciadas na tela verde até `FINALIZAR`. CPF/e-mail/WhatsApp são opcionais, mas seus contratos ainda não existem no backend; a UI informa essa indisponibilidade e não simula envio ou persistência.
