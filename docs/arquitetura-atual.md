# Arquitetura atual

Voltar para [o índice](00-index.md).

> Atualização de 15 de agosto de 2026: a primeira etapa pós-auditoria refatorou o cadastro inicial. A ativação agora usa um único timer, consulta HTTP em `QThread`, UUID canônico compatível com o DTO atual, gravação atômica do JSON e lifecycle pós-ativação idempotente. As seções históricas abaixo descrevem a fotografia encontrada na auditoria quando indicado.

> Atualização de 24 de agosto de 2026: `config.py` passou a definir raiz e paths absolutos; `MainWindow` mantém serviços de sincronização periódica (5 min) e heartbeat confirmado (10 s) durante todo o lifecycle. Ambos rodam fora da UI, iniciam somente após ativação e possuem parada cooperativa. Consulte [[sincronizacao]], [[heartbeat]] e [[sqlite]].

## Estrutura real

```text
main.py
├── MainWindow / QStackedWidget
├── telas/
│   ├── bemvindo.py
│   ├── CadastroTerminalScreen.py
│   ├── terminal_screen.py
│   ├── pagamento.py
│   ├── pix.py
│   ├── app_payment_screen.py
│   ├── ConfirmacaoScreen.py
│   ├── ConfiguracaoScreen.py
│   ├── login_screen.py (não instanciada)
│   ├── teclado.py (parcial/defeituosa)
│   └── OfflineOverlay.py (monitor desativado)
├── model/
│   ├── Terminal.py
│   ├── Produtos.py
│   ├── Carrinho.py
│   └── Item.py
├── service/
│   ├── SyncService.py
│   ├── TerminalSocket.py
│   ├── TerminalInfo.py
│   ├── InternetMonitor.py (desativado)
│   └── HoldToExitLabel.py
├── database/
│   ├── DatabaseProdutos.py
│   └── PaymentListener.py
├── db/terminal.json
├── db/terminal.db
└── config.py / .env
```

Não existem packages Python declarados por `__init__.py`; os imports dependem do diretório de execução ser a raiz do projeto. Não há client HTTP central, state machine, camada de casos de uso ou testes automatizados.

## Inicialização real

1. `main.py` carrega PyQt5, cria `QApplication` e `MainWindow`.
2. `MainWindow` instancia sempre a tela de boas-vindas e a tela de cadastro.
3. `Terminal.is_activated()` carrega e valida o JSON e exige `ativo` e `activated` verdadeiros.
4. Se o arquivo existe:
   - inicia `SyncService.sincronizar_produtos` em uma `threading.Thread` daemon;
   - instancia todas as telas de operação;
   - `TerminalScreen` abre SQLite e inicia imediatamente `PaymentListener`;
   - inicia `TerminalSocket` em outra thread daemon;
   - mostra a tela de boas-vindas.
5. Se o arquivo não existe, mostra `CadastroTerminalScreen`, que consulta a ativação a cada 5 segundos em um único `QThread`, impedindo consultas sobrepostas.
6. O monitor de internet e o overlay offline estão instanciados, mas sua inicialização está comentada.

## Telas e transições observadas

| Tela | Entrada | Saídas reais |
|---|---|---|
| `TelaBemVindos` | startup ativado/reset | `TerminalScreen`; segurar logo por 2 s encerra o app |
| `CadastroTerminalScreen` | startup não ativado | ao ativar, inicializa telas e vai para boas-vindas |
| `TerminalScreen` | boas-vindas | pagamento presencial, pagamento no app, cancelar |
| `PagamentoScreen` | botão pagar agora | PIX, crédito, débito ou voltar |
| `PixScreen` | tentativa PIX | confirmação manual ou retorno após timeout/cancelamento |
| `AppPaymentScreen` | pagar no app | retorno por cancelamento/timeout; não há conclusão conectada |
| `ConfirmacaoScreen` | qualquer mensagem no socket de pagamento | após 20 s limpa carrinho e volta ao início |
| `ConfiguracaoScreen` | manter o logotipo pressionado por 2 s na tela inicial | voltar ou solicitar restauração dos padrões locais |
| `LoginScreen` | nenhuma: criação comentada | código legado |
| `TecladoScreen` | é instanciada, mas fluxo normal não chega nela | possui referências inválidas |

## Modelos locais

- `Terminal`: espelho JSON da ativação, com dois identificadores (`terminalId` e `uuidTerminal`) e IDs tipados incorretamente como `int`.
- `Produtos`: representação do catálogo/cache; ainda contém `quantidade` como se fosse saldo do produto.
- `Item`: produto, quantidade e peso recebido.
- `Carrinho`: lista somente em memória; agrupa por código, calcula total e gera o body REST.

## Estados reais

Não existe enum ou máquina de estados no cliente. O estado resulta de:

- widget atual do `QStackedWidget`;
- existência de `db/terminal.json`;
- conteúdo mutável de `TerminalScreen.carrinho` e `linhas`;
- timers locais de PIX, app e confirmação;
- flags `PaymentListener.is_running`, `MainWindow.is_offline` e `InternetMonitor.running`;
- conexões WebSocket independentes.

Estados representáveis e inconsistentes incluem carrinho preenchido com tela inicial, QR expirado com carrinho backend ainda ativo, UI limpa com carrinho local ainda contendo itens e confirmação exibida para mensagem não aprovada.

## Threading e UI

- `SyncService`: thread Python daemon; usa SQLite criado dentro da própria thread.
- `TerminalSocket`: thread Python daemon com loops e sleeps.
- `PaymentListener`: `QThread`; sinal chega à UI por `Qt.QueuedConnection`.
- `AppPaymentScreen`: thread Python daemon, mas altera widgets Qt diretamente fora da UI thread.
- Ativação e PIX: chamadas HTTP síncronas na UI thread.
- Timers Qt: foco (1 s), ativação (5 s), PIX/app/confirmacão (1 s e single-shot).

## Funcionalidades a preservar

- leitura rápida por código de barras usando cache local;
- agrupamento visual por código e botões de quantidade/remoção;
- cálculo local para feedback imediato, sujeito à validação final do backend;
- ativação baseada em identidade física e serial, sem escolha manual de empresa/condomínio;
- separação entre terminal e credenciais Mercado Pago: não há token MP no Python;
- sincronização fora da UI no startup;
- heartbeat e listener de pagamento fora da UI;
- confirmação explícita antes do reset no caminho WebSocket (a correlação/status precisam ser corrigidos sem perder essa intenção).

## Menu de manutenção local

O gesto prolongado no logotipo não encerra mais diretamente o processo. Ele emite um sinal e abre `ConfiguracaoScreen`. A primeira ação disponível é a restauração dos padrões locais, protegida por confirmação.

Para não mover um SQLite ainda aberto por telas/threads, a ação cria `db/factory-reset.pending` e encerra o aplicativo. Na próxima inicialização, antes das telas e services, `FactoryResetService.apply_pending()` move a identidade, banco/cache, cursor de sync e QR temporário para um backup datado. Configuração `.env`, backend e credenciais externas permanecem intocados.
