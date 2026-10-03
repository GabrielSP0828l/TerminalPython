# Recuperação de pagamento Point

Voltar para [[00-index]]. Fluxo geral em [[fluxo-compra]], persistência em [[sqlite]], contratos em [[api-backend]] e canais em [[websocket]].

## Regra

Uma tentativa não resolvida nunca é substituída por outra. Timeout, Point desligada, HTTP offline e WebSocket perdido mantêm `payment_in_flight=true` e exigem consulta ao backend. Apenas `APPROVED`, `REJECTED/FAILED`, `CANCELLED`, `EXPIRED` ou `REFUNDED` encerram o checkpoint local.

```text
CONFIRMAR E PAGAR
  -> lock visual/lógico + active_payment SQLite
  -> POST /carrinho
  -> checkpoint síncrono do cartId
  -> POST /pagamento/terminal/{cartId}
       -> WAITING_PAYMENT: tela pendente + polling
       -> timeout/erro: descobrir/reconciliar
       -> PAYMENT_ALREADY_ACTIVE: adotar IDs anteriores e reconciliar
       -> estado terminal: sucesso ou retry seguro
```

## Startup e reconnect

`MainWindow` restaura `active_payment` antes de liberar o fluxo. Com `orderId`, consulta seu status; com apenas `cartId`, primeiro pergunta ao endpoint de tentativa ativa e só reutiliza o mesmo carrinho depois de `204`; sem checkpoint, ainda faz descoberta em background para cobrir crash/cliente antigo. Reconexão WebSocket repete essa descoberta, mas WebSocket não é fonte única.

Os workers carregam token da tentativa local, Order e PaymentAttempt esperadas. Callback tardio divergente é descartado. Depois de falhas repetidas, o polling desacelera de 10 para 30 segundos e o usuário vê `VERIFICAR NOVAMENTE`; a UI não retorna às boas-vindas com tentativa ativa.

## Point desligada

A mensagem é “Aguardando pagamento” e “Verifique se a maquininha está ligada e conectada”. Não é exibida recusa sem estado terminal do backend. Ao ligar a Point, webhook ou próxima consulta pode produzir `APPROVED`; se a Order expirar, `EXPIRED` limpa a pendência e libera outra tentativa.

Não há botão Cancelar nesta versão: limpar localmente seria inseguro e o backend ainda não expõe cancelamento Point com confirmação remota. Heartbeat, telemetria e sync permanecem em serviços/threads separados.
