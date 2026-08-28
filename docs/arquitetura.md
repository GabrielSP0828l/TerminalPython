# Arquitetura do Terminal

Voltar para [[00-index]]. Inventário detalhado em [[arquitetura-atual]].

```text
MainWindow / showFullScreen
├── QStackedWidget
│   ├── ativação / boas-vindas / configuração
│   ├── AdminAuthScreen ── barreira efêmera por senha de ambiente
│   ├── TerminalScreen ── Carrinho único em memória
│   ├── ConfirmacaoCompraScreen ── view do mesmo Carrinho
│   ├── PagamentoScreen ── workers HTTP Point
│   └── ConfirmacaoScreen ── resultado aprovado/ações/reset explícito
├── CompraSession ── prazo, IDs e estado operacional
├── SyncService ── catálogo SQLite fora da UI
├── TerminalSocket ── heartbeat
└── PaymentListener ── pagamento + invalidação de catálogo
```

O design system é centralizado em `styles/tokens.py` e `styles/theme.py`. As páginas aplicam temas semânticos, mas não guardam paletas independentes. Layouts Qt expansíveis recebem a geometria real do display; não há rotação de widgets.

`PaymentStateWidget` compõe ícone/título/mensagem/ações para estados fullscreen. `styles/svg_icons.py` resolve assets pela raiz e usa `QSvgRenderer` + máscara `SourceIn` para recolorir SVG em runtime. `CompraSession.last_status` mantém somente o status interno necessário ao motivo humano e rejeita `APPROVED` duplicado sem reconstruir a tela. O reset aprovado migrou do timer para a ação explícita `FINALIZAR`.

O backend continua fonte de verdade para identidade organizacional, catálogo/disponibilidade, estoque, Carrinho/Items persistidos, Order, Pagamento e status financeiro. A nova confirmação é exclusivamente UI e não modifica DTOs/endpoints.

## Administração e shutdown

`TelaBemVindos.logo -> MainWindow.abrir_configuracoes -> AdminAuthScreen -> ConfiguracaoScreen.entrar`. A autorização existe apenas enquanto a tela de configuração está aberta e não é persistida. As ações administrativas possuem guarda adicional em `ConfiguracaoScreen`.

`TERMINAL_ADMIN_PASSWORD` é carregada centralmente por `config.py`; `.env.example` contém somente a chave vazia. Nenhum valor é documentado ou registrado.

`MainWindow.encerrar_terminal()` autoriza uma única saída, preserva o estado financeiro e executa `_parar_servicos()` de forma idempotente: timer da compra, relógio, ativação, espera/worker Point, checkout legado, foco/scanner, `PaymentListener`, `SyncService`, heartbeat e monitor opcional. Depois chama `QApplication.quit()`. `closeEvent` sem autorização é ignorado e `Esc` é consumido.

`start.sh` pode configurar a rotação Wayland antes do Python quando `DISPLAY_ORIENTATION=vertical`. Saída e transform são detectáveis/configuráveis; ausência de `wlr-randr` não impede o startup. Veja [[layout-vertical]].
