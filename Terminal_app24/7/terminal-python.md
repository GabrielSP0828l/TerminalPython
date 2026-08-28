# Terminal Python — estado atual

Voltar para [[00-index]]. Detalhes em [[arquitetura]], [[sincronizacao]], [[sqlite]], [[websocket]] e [[heartbeat]].

## Responsabilidade

O Terminal é cliente PyQt5 do backend Spring Boot. Mantém interface física, ativação, cache SQLite, scanner, carrinho visual, checkout, heartbeat e WebSocket. Backend continua fonte de verdade de Empresa, Condomínio, catálogo, estoque, Carrinho/Items persistidos, Order, Pagamento e Mercado Pago.

## Estado verificado em 24 de agosto de 2026

| Área | Estado |
|---|---|
| Identidade | UUID canônico persistido após ativação |
| Produtos | `/produtos/sync` FULL/INCREMENTAL por Terminal/Condomínio |
| Cursor | `syncAt` exato do backend em `database/last_sync.txt` |
| SQLite | cache UUID, UPSERT/REMOVE atômicos, marcador FULL e contagem consistente |
| Tempo real | `PRODUCT_SYNC_REQUIRED` solicita sync HTTP |
| Recuperação | sync no startup e em conexão/reconexão WebSocket |
| Concorrência | worker único com `sync_in_progress + sync_pending` |
| Heartbeat | canal separado, ACK após persistência de `lastPing` |
| Pagamento | `PAYMENT_STATUS` separado do evento de catálogo e correlacionado |
| Timeout global | 600 s, evento único no `MainWindow`, reset/reconciliação central |
| Interface | design system único, targets touch e portrait `768x1360` |
| Confirmação | `Finalizar` abre resumo; Point somente em `Confirmar e pagar` |
| Administração | toque longo → senha obrigatória → menu existente |
| Rede local | Wi-Fi autenticado via NetworkManager/`nmcli`, worker e timeout |
| Display | horizontal/vertical pelo compositor, persistido no boot |

## Lifecycle

```text
MainWindow pós-ativação
  -> SyncService: startup + periódico + eventos/reconnect
  -> TerminalSocket: heartbeat independente
  -> PaymentListener: pagamento + invalidação de catálogo
  -> telas no QStackedWidget
```

HTTP/SQLite não executam na thread da UI. O scanner consulta o SQLite em cada scan, então commits passam a valer sem reinício. Produto já capturado no carrinho mantém seu snapshot/preço; sync altera o catálogo para leituras futuras.

## Navegação da compra

`TerminalScreen -> ConfirmacaoCompraScreen -> PagamentoScreen -> ConfirmacaoScreen`. A confirmação pré-pagamento não duplica o carrinho. “Pagar no App” não aparece mais no carrinho; a classe legada foi preservada sem rota ativa.

Todas as páginas usam o tema central. Total/ações permanecem fora do scroll e o display deve ser girado pelo sistema, não por widgets Qt. `start.sh` aceita `DISPLAY_ORIENTATION=vertical`, saída/transform opcionais e fallback seguro.

O relógio da compra é responsabilidade exclusiva de `CompraSession`. Em `00:00`, a sessão fica inativa, o timer para e `MainWindow` bloqueia scanner/botões. Lista e confirmação são limpas pelo `reset_compra` existente; pagamento remoto é reconciliado antes de qualquer descarte. O reset restaura o deadline completo e a guarda de emissão para a próxima geração.

## Administração local

O toque longo de dois segundos no logotipo foi preservado. Antes de mostrar `ConfiguracaoScreen`, `AdminAuthScreen` exige a senha de `TERMINAL_ADMIN_PASSWORD`, mascarada e digitável pelo teclado virtual compartilhado. Senha ausente bloqueia o menu. Senha incorreta não revela detalhes. Cancelar preserva a página/compra anterior e sair do menu invalida a autorização.

O menu mantém o reset recuperável e inclui `Configurar Wi-Fi`, `Orientação da tela` e `Fechar Terminal`. Voltar de Wi-Fi/display mantém a mesma autenticação; sair do painel a invalida. Troca/desconexão de Wi-Fi durante pagamento gera aviso contextual e não cancela Mercado Pago. Orientação é bloqueada durante compra/pagamento. Ao confirmar encerramento, o lifecycle cooperativo para recursos e chama `QApplication.quit()`; `Esc` e fechamento comum não saem do quiosque.

## Limites preservados

- não há credenciais Mercado Pago no Python;
- terminal não escolhe empresa/condomínio;
- quantidade do catálogo é informativa e o backend controla estoque oficial;
- sockets ainda não possuem autenticação criptográfica;
- tentativa de pagamento após reboot continua uma evolução separada.
