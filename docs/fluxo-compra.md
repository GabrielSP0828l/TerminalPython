# Fluxo atual da compra

Voltar para [[00-index]]. Telas em [[telas]] e contrato em [[api-backend]].

## Fonte única de estado

`TerminalScreen.carrinho` contém os itens em memória; `CompraSession` contém prazo, geração, tentativa, `cartId`, `orderId`, `paymentId` e estado operacional. A confirmação pré-pagamento consulta esses objetos e não cria cópia do carrinho.

## Scanner e lista

1. scanner preenche o input e envia Enter;
2. `readProduct()` consulta o produto ativo no SQLite;
3. primeiro scan cria um `Item` e inicia o prazo global de 10 minutos;
4. scans repetidos incrementam quantidade;
5. remover elimina a linha inteira; carrinho vazio reseta a sessão local.

## Finalização confirmada

```text
Carrinho visual
  -> FINALIZAR (somente navegação)
  -> Confirme sua compra
      -> VOLTAR (mesmo objeto Carrinho)
      -> CONFIRMAR E PAGAR
          -> botão desabilitado + “PREPARANDO...”
          -> PagamentoScreen / worker Point atual
```

Não há chamada HTTP ao tocar em `Finalizar`. A primeira operação remota acontece somente em “Confirmar e pagar”.

## Point

1. `POST /carrinho` persiste Carrinho/Items;
2. `POST /pagamento/terminal/{carrinhoId}` cria/reutiliza Order e inicia Point;
3. resposta inicial válida muda a UI para atenção laranja e instrui o cliente na Point;
4. WebSocket e `GET /order/{orderId}/status?terminalId=...` reconciliam o estado;

A confirmação usa uma guarda própria para a tela `ConfirmacaoCompraScreen`. Ela não reutiliza a guarda do carrinho, pois aquela exige que `TerminalScreen` seja a tela atual. Ao confirmar, ambos os botões são bloqueados e a navegação para `PagamentoScreen` ocorre antes de iniciar o worker, exibindo imediatamente `tube-spinner.svg`.

O fluxo registra marcos `[PAYMENT-UI]`, `[PAYMENT-HTTP]` e `[PAYMENT-WORKER]`. O worker Point emite `succeeded`, `failed` ou `timed_out` e sempre termina pelo sinal nativo `finished`; se terminar sem outcome, a UI converte isso em erro operacional e encerra o loading.
5. `PROCESSING` mantém loading; somente `APPROVED` correlacionado abre o sucesso verde;
6. falha definitiva abre erro vermelho e “Tentar novamente” retorna ao carrinho;
7. no sucesso, a compra permanece em memória até `FINALIZAR` executar o reset central.

Antes de persistir/cobrar, o backend recalcula cada item. O Terminal envia `expectedUnitPrice` com seis casas. Se o preço atual aumentou, `409 PRICE_CHANGED` substitui os valores locais pelos retornados, mostra a alteração e exige que o cliente revise e confirme novamente. O total local usa `Decimal`; o texto de duas casas nunca alimenta o cálculo.

Falha de comunicação antes de conhecer o resultado usa mensagem operacional neutra, não “recusado”. Timeout com IDs remotos continua reconciliando. A reconciliação possui limite de falhas; ao excedê-lo, a tela sai do loading, mantém a sessão bloqueada (`RECONCILIATION_PENDING`) e não dispara novo POST, aguardando WebSocket/reconciliação do backend. Falha definitiva preserva os itens, invalida os IDs antigos e uma nova cobrança só pode começar novamente pelo fluxo de confirmação. O Python não contém credenciais Mercado Pago nem interpreta status externos diretamente.

Depois de receber `PENDING`, `CREATED` ou `AT_TERMINAL`, o Terminal inicia consulta moderada a cada 10 segundos pelo endpoint de status. O WebSocket antecipa a atualização, mas não é a única fonte. A fase visual possui timeout operacional de 30 segundos e nunca cria outra cobrança para obter status.

## Pós-aprovação

`APPROVED` não limpa Carrinho, Order ou Payment local imediatamente. A tela verde mantém essas referências para CPF/comprovante e bloqueia uma nova compra. Hoje o backend não possui CPF em Order/Pagamento nem endpoints de comprovante por e-mail/WhatsApp; por isso a UI não grava nem afirma envio. `FINALIZAR` é opcionalmente precedido por essas ações futuras e sempre conclui a experiência por `MainWindow.reset_compra()`.

## Fluxos fora da compra principal

`AppPaymentScreen` permanece no código por compatibilidade histórica, mas o botão “Pagar no App” foi removido do carrinho e nenhuma rota ativa abre essa tela. Crédito/débito/PIX não foram recriados.
