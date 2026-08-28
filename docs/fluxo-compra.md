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
5. `PROCESSING` mantém loading; somente `APPROVED` correlacionado abre o sucesso verde;
6. falha definitiva abre erro vermelho e “Tentar novamente” retorna ao carrinho;
7. no sucesso, a compra permanece em memória até `FINALIZAR` executar o reset central.

Falha de comunicação antes de conhecer o resultado usa mensagem operacional neutra, não “recusado”. Timeout com IDs remotos continua reconciliando. Falha definitiva preserva os itens, invalida os IDs antigos e uma nova cobrança só pode começar novamente pelo fluxo de confirmação. O Python não contém credenciais Mercado Pago nem interpreta status externos diretamente.

## Pós-aprovação

`APPROVED` não limpa Carrinho, Order ou Payment local imediatamente. A tela verde mantém essas referências para CPF/comprovante e bloqueia uma nova compra. Hoje o backend não possui CPF em Order/Pagamento nem endpoints de comprovante por e-mail/WhatsApp; por isso a UI não grava nem afirma envio. `FINALIZAR` é opcionalmente precedido por essas ações futuras e sempre conclui a experiência por `MainWindow.reset_compra()`.

## Fluxos fora da compra principal

`AppPaymentScreen` permanece no código por compatibilidade histórica, mas o botão “Pagar no App” foi removido do carrinho e nenhuma rota ativa abre essa tela. Crédito/débito/PIX não foram recriados.
