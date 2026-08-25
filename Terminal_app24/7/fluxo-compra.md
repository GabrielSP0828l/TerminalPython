# Fluxo real da compra

Voltar para [[00-index]].

## Scanner e produto

1. Cliente entra em `TerminalScreen`.
2. Scanner preenche `QLineEdit` e envia Enter.
3. `readProduct()` consulta `produtos.codigo` no SQLite.
4. Ausente: aviso local. Presente: `Produtos.from_tuple` cria modelo.
5. Produto novo gera `Item(quantidade=1, received_weight=1.0)` e linha visual.
6. Repetição incrementa quantidade; não consulta backend.

O status do produto no cache não é filtrado. A disponibilidade do condomínio não participa do scan.

## Carrinho local

`Carrinho` existe somente em memória. Agrupa por código, remove item, soma quantidades e produz:

```json
{
  "terminalId": "uuid",
  "items": [
    {"productId": "uuid", "quantity": 1, "receivedWeight": 1.0}
  ]
}
```

`Carrinho.total()` usa preço × quantidade. `Item.subtotal()` usa peso quando truthy, criando possível divergência visual. Não há persistência local, ID de tentativa ou outbox.

## Crédito e débito

Os dois botões chamam `PagamentoScreen.finalizar_venda()`:

1. zeram labels/contadores;
2. removem widgets;
3. voltam às boas-vindas;
4. não chamam backend;
5. não limpam `carrinho.items` nem `linhas`.

Portanto não criam Carrinho, Items, Order, Pagamento ou cobrança Point.

## PIX presencial

1. `POST /carrinho`, sem timeout, na UI thread.
2. Lê `carrinhoId`.
3. Chama `GET /pagamento/terminal?carrinho_id=...`.
4. Espera `{valor, qrCode, qrCodeBase64}`.

Backend atual expõe `GET /pagamento/terminal/{carrinho_id}` e retorna booleano após iniciar Point. O caminho é incompatível. Se um backend legado respondesse, `PixScreen` permitiria confirmação manual sem status financeiro definitivo.

## Pagamento no app

1. Thread daemon faz `POST /carrinho`.
2. Faz `GET /checkout/carrinho?idCarrinho=...`.
3. Faz `GET /checkout/qrcode?id=...`.
4. Salva PNG e atualiza widgets diretamente na thread.
5. Timeout/cancelamento apenas volta de tela.

Não existe listener da sessão, associação obrigatória de usuário ou conversão automática da sessão em Order no fluxo observado.

## Backend, Mercado Pago e resultado

O backend implementa Carrinho → Order → reserva → cobrança Point → webhook → Order/Pagamento/estoque. Porém o cliente não alcança corretamente esse fluxo.

`PaymentListener` conecta no socket do UUID e emite qualquer JSON. `pagamento_aprovado()` ignora `paid`, `terminalId` e `orderId`, mostra sucesso e depois limpa o carrinho. O backend ativo atualiza pagamento/order no webhook, mas não publica `PaymentEvent` para esse socket.

## Falhas, duplicação e reconexão

- clique/retry pode criar carrinhos duplicados;
- timeout após POST não distingue falha de resposta de falha de persistência;
- carrinho remoto pode ficar `OPEN` órfão;
- cliente não guarda `carrinhoId`/`orderId` para reconciliar;
- sockets reconectam sem replay/consulta;
- pagamento aprovado offline pode nunca aparecer;
- evento atrasado pode liberar nova compra;
- timeout/cancelamento local não altera backend;
- reset de fábrica não cancela operações financeiras: ele é apenas local.

## Matriz do fluxo esperado

| Etapa | Implementação atual |
|---|---|
| scanner → produto | sim, cache local |
| produto → carrinho visual | sim |
| carrinho → backend | somente PIX/app |
| Items persistidos | backend suporta quando POST funciona |
| Order | não criada corretamente pelo cartão atual |
| cobrança Point | contrato cliente incompatível |
| maquininha | responsabilidade correta do backend |
| webhook | implementado no backend |
| resultado ao terminal | socket existe; publicação ativa ausente |
| correlação | inexistente no cliente |
| reset após aprovação | existe, mas aprovação não é validada |
