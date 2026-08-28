# Arquitetura atual do terminal

> Atualização em 24 de agosto de 2026: `MainWindow` mantém `SyncService` (imediato + 300 s) e `TerminalSocket` (10 s com ACK) fora das telas. Configuração/SQLite/identidade/cursor usam raiz absoluta e ambos os serviços possuem parada cooperativa. Consulte [[sincronizacao]] e [[heartbeat]].

Voltar para [[00-index]].

## Estrutura real

```text
main.py
├── config.py / .env
├── telas/
│   ├── bemvindo.py
│   ├── CadastroTerminalScreen.py
│   ├── ConfiguracaoScreen.py
│   ├── terminal_screen.py
│   ├── pagamento.py
│   ├── pix.py
│   ├── app_payment_screen.py
│   ├── ConfirmacaoScreen.py
│   ├── login_screen.py (não instanciada)
│   ├── teclado.py (instanciada, fluxo inativo)
│   └── OfflineOverlay.py (monitor da API + acesso autenticado ao Wi-Fi)
├── model/
│   ├── Terminal.py
│   ├── Produtos.py
│   ├── Carrinho.py
│   └── Item.py
├── service/
│   ├── SyncService.py
│   ├── TerminalSocket.py
│   ├── TerminalInfo.py
│   ├── FactoryResetService.py
│   ├── InternetMonitor.py (ativo após ativação; monitora API_URL)
│   └── HoldToExitLabel.py
├── database/
│   ├── DatabaseProdutos.py
│   └── PaymentListener.py
└── tests/
    ├── test_terminal.py
    └── test_factory_reset.py
```

Não há `__init__.py`, client HTTP central, state machine ou camada formal de casos de uso. Os imports dependem da execução na raiz.

## Inicialização real

1. `QApplication` cria `MainWindow`.
2. `FactoryResetService.apply_pending()` é executado antes das telas.
3. São criadas boas-vindas, cadastro, configurações e overlay.
4. `Terminal.is_activated()` exige JSON válido, UUID, `ativo=true` e `activated=true`.
5. Ativado: `iniciar_operacao_terminal()` instancia telas operacionais, inicia sync daemon e heartbeat daemon.
6. Não ativado: mostra cadastro; QR é gerado em memória e um único timer dispara worker HTTP a cada 5 s.
7. Ao ativar em runtime, o mesmo lifecycle idempotente inicia telas, sync e heartbeat sem reinício.

No estado auditado não há `terminal.json` ativo devido ao reset, então a execução seguinte toma o ramo de cadastro.

## Telas e transições

| Tela | Entrada | Saída |
|---|---|---|
| Boas-vindas | startup ativado/reset de compra | terminal; gesto de 2 s abre configurações |
| Cadastro | startup não ativado | boas-vindas após resposta ativada |
| Configurações | gesto prolongado | voltar ou agendar reset local |
| Terminal | boas-vindas | pagamento, app ou cancelamento |
| Pagamento | carrinho não vazio | PIX, cartão ou voltar |
| PIX | resposta legada esperada | confirmação manual, cancelamento ou timeout |
| AppPayment | pagar no app | cancelamento/timeout; sem conclusão ativa |
| Confirmação | qualquer JSON no socket | limpa carrinho após 20 s |

## Estado real

Não existe enum de aplicação. Estado é a combinação de:

- widget atual no `QStackedWidget`;
- existência/validade de `terminal.json`;
- `TerminalScreen.carrinho`, `linhas`, totais e widgets;
- `_operacao_iniciada` no `MainWindow`;
- timers de ativação, foco, PIX, app e confirmação;
- threads de sync/checkout/heartbeat e `QThread` de pagamento;
- arquivos de reset e cache.

Isso permite estados inconsistentes: tela inicial com carrinho antigo, UI vazia com items em memória, timeout local com Order ativa e evento antigo durante nova compra.

## Concorrência

- Ativação: `QThread`, uma consulta por vez, sinal para UI — adequado.
- Sync: thread daemon, SQLite criado nela — não bloqueia UI.
- Heartbeat: thread daemon, loops sem stop.
- Pagamento: `QThread`, `recv()` potencialmente bloqueante.
- Checkout app: thread daemon que altera widgets diretamente — inseguro no Qt.
- PIX: HTTP síncrono na UI — pode congelar.
- Reset: adiado para o próximo startup, evitando mover SQLite aberto — adequado.

## Código legado/morto

- `LoginScreen` não é adicionada ao stack e chama `/usuarios/anonimo`, ausente no backend.
- `TecladoScreen.finalizar` referencia `parentrminal`; botão cancelar depende de `parent.login` inexistente.
- `Produtos.get_produtos_api` não possui chamador.
- `PagamentoScreen.self.API_URL` hardcoded não é usado nas requisições.
- monitor de internet está comentado.
- `LoginScreen` permanece legado sem rota ativa; `InternetMonitor` agora faz parte do lifecycle pós-ativação.
