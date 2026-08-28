# Telas do Terminal

Voltar para [[00-index]]. Fluxo funcional em [[fluxo-compra]] e limites de integração em [[compatibilidade-backend]].

## Display de referência

A interface operacional é validada prioritariamente no display físico de 7 polegadas, em `1024×600`. A janela continua fullscreen e as páginas permanecem no `QStackedWidget`; nenhuma tela de compra abre janela separada.

## Tela de compra

`TerminalScreen` é composta por header, catálogo rolável, scanner/peso e footer fixo. Somente o catálogo rola. Total, cancelamento e `FINALIZAR` permanecem visíveis.

O catálogo usa `QGridLayout` dentro de `QScrollArea`. O cálculo parte da largura do viewport, já descontada a barra vertical:

- cards entre 250 e 292 px de largura;
- no máximo quatro colunas;
- 3 colunas em `1024×600`;
- espaçamento de 12 px;
- altura fixa de 224 px;
- scroll vertical sempre disponível e scroll horizontal desativado;
- distribuição real por `row, column = divmod(index, columns)`.

Cada card mostra somente nome, subtotal exibido, quantidade e a ação `REMOVER`. O nome usa 26 px e no máximo duas linhas, com elipse quando necessário; o preço usa 34 px; a quantidade usa 22 px. Nenhum barcode, UUID, categoria ou identificador técnico é exibido.

O footer usa uma única faixa horizontal para aproveitar a altura de 600 px. `TOTAL` usa 28 px, o valor usa 46 px e `FINALIZAR` usa 26 px com 72 px mínimos de altura. O relógio global de 10 minutos permanece no canto superior em 20 px.

Ao atingir `00:00`, o scanner, remoções, cancelamento e `FINALIZAR` são desabilitados antes da navegação. Sem pendência financeira, o controlador limpa a compra e abre a tela de boas-vindas; a lista não possui lógica própria de timeout.

Não existe campo de promoção no modelo/contrato local atual; a tela não inventa preço promocional. Caso o backend passe a fornecer preço original e promocional, o contrato deve ser definido primeiro em [[api-backend]] e [[compatibilidade-backend]].

## Confirmação da compra

A estrutura e a fonte única do carrinho foram preservadas. A revisão foi tipográfica e de contraste:

- título `CONFIRME SUA COMPRA`: 40 px;
- nome: 26 px;
- quantidade e preço: 24 px;
- total em card branco sólido, texto escuro e borda azul: rótulo 28 px e valor 48 px;
- `VOLTAR` e `CONFIRMAR E PAGAR`: 26 px e 72 px mínimos de altura;
- fundo escuro pintado explicitamente para não depender do compositor Qt.

O mesmo evento global bloqueia imediatamente `VOLTAR` e `CONFIRMAR E PAGAR`; o controlador cancela o resumo, reutiliza `reset_compra` e retorna às boas-vindas quando ainda não há operação financeira a reconciliar.

## Preparação do pagamento

O loading continua usando `icon/tube-spinner.svg`, renderizado em 128×128. `Preparando pagamento...` usa 32 px. Nenhuma alteração foi feita no início, correlação ou resultado financeiro descritos em [[mercado-pago]] e [[websocket]].

Se a sessão expirar durante esse loading, a tela não libera ações. Um worker Point ainda em execução pode terminar apenas para informar com segurança se existem `cartId`/`orderId`; seu callback é aceito somente para a tentativa capturada. Sem referência remota após a resposta delimitada, ocorre reset. Com referência remota, a tela passa à reconciliação.

## Validação visual

Em render Qt offscreen exato de `1024×600`, seis produtos resultaram em três cards por linha, cards de `292×224`, segunda linha por scroll vertical, nenhum scroll horizontal e footer fixo. A confirmação manteve total e botões integralmente visíveis. A validação automatizada não inicia cobrança real.
