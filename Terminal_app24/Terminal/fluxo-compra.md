# Fluxo real da compra

Voltar para [[00-index]]. Contratos em [[api-backend]] e Point em [[mercado-pago]].

## Estado local

`TerminalScreen.carrinho` é a fonte única dos itens durante o processo; `CompraSession` mantém prazo, geração, tentativa e IDs remotos. A tabela SQLite singleton `active_payment` mantém o checkpoint financeiro necessário para sobreviver ao reinício. A tela de confirmação lê o mesmo carrinho e reconstrói somente widgets visuais.

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
          -> PENDING/CREATED/AT_TERMINAL/ACTION_REQUIRED/PROCESSING: laranja
          -> CANCELAR COMPRA: Spring -> Mercado Pago -> reconciliação
          -> falha definitiva: erro vermelho/retry
          -> APPROVED: sucesso verde
              -> WhatsApp/e-mail: POST /comprovante em worker
              -> FINALIZAR: reset local
```

“Pagar no App” saiu da tela principal. A classe legada permanece sem rota ativa. Crédito/débito/PIX não foram recriados.

## Segurança financeira

A resposta de criação da cobrança é intermediária. Apenas `APPROVED` da Order e Terminal ativos libera a compra. Falha preserva itens e mostra “Tentar novamente”. Timeout com IDs remotos reconcilia antes de liberar. Backend continua responsável por Order, Pagamento, credenciais Mercado Pago e estoque.

Enquanto `CompraSession.payment_in_flight=true`, `cartId`, `orderId` e `paymentId` não são limpos por perda de socket ou indisponibilidade do backend. Ao conectar/reconectar, o Terminal mostra “Verificando pagamento” e chama `GET /order/{orderId}/status`; enquanto aguarda também repete a consulta a cada 10 segundos. `WAITING_PAYMENT` conserva a tela, `APPROVED` abre `checked.svg` e falha definitiva abre `error.svg`.

No primeiro clique válido, o botão e o lock lógico são ativados antes do worker. A tentativa é persistida antes do primeiro HTTP, e o `cartId` é gravado sincronicamente antes do POST financeiro. No startup, a sessão volta como `RECONCILIATION_PENDING`; com Order conhecida consulta seu status, sem Order descobre a tentativa pelo Terminal e só então pode reutilizar o mesmo `cartId`. Cem sinais rápidos continuam representando um único início.

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

`Finalizar` apenas abre o resumo. `Confirmar e pagar` é desabilitado imediatamente e muda para “Preparando...” antes do worker. Cobrança pendente mostra “Aguardando pagamento”, orientação para ligar/conectar a Point e “Verificar novamente”. Após falhas repetidas, a tela permanece visível e o polling desacelera para 30 segundos; não volta às boas-vindas com `payment_active=true`. Falha definitiva usa vermelho e preserva o carrinho; aprovação usa verde.

No display de 7 polegadas (`1024×600`), o carrinho usa grid rolável de três colunas e footer fixo; a sessão global continua limitada a 10 minutos. A disposição e as métricas visuais estão em [[telas]].

Não existe reset imediato após `APPROVED`. A entrada única `_handle_payment_approved` encerra a espera financeira, para o deadline do checkout, mantém `orderId`, abre a tela verde e inicia um timer separado de inatividade pós-compra. Aprovação recebida por WebSocket, polling ou recuperação percorre esse mesmo caminho.

Na tela aprovada, WhatsApp/e-mail enviam apenas Terminal, Order, canal e destinatário ao Spring em worker Qt. O Spring valida a venda e monta o comprovante; o Terminal não conhece FastAPI/n8n, não reconstrói itens e não muda o pagamento se a entrega falhar. Entrada touch ou request em andamento pausa o timer. `FINALIZAR` chama somente `reset_compra(outcome="finalized")`, limpa carrinho/sessão/IDs/timers locais e volta à Home, sem cancelar a Order. CPF permanece desabilitado por ausência de endpoint real.

## Point: criação, orientação e cancelamento

O loading `ENVIANDO PAGAMENTO` cobre somente `POST /carrinho` e a criação/aceite remoto. A primeira resposta correlacionada com `orderId` encerra esse loading. A tela laranja passa a ser o estado operacional e explica que cancelar Débito/Crédito na Point não encerra necessariamente a Order: enquanto o backend devolver estado não terminal, a mesma cobrança continua ativa e nenhuma segunda Order é criada.

`CANCELAR COMPRA` marca `CANCELLING`, persiste essa intenção no checkpoint e usa worker próprio. Somente `CANCELLED`/`EXPIRED` autoritativo limpa a sessão e abre Home; timeout mantém a tela laranja e o polling. `APPROVED` durante a corrida prevalece. No timeout global de 10 minutos, uma Order conhecida entra nesse mesmo cancelamento seguro, nunca em reset local direto. Veja o contrato compartilhado `payment-point-flow.md`.
