# Auditoria completa — outubro de 2026

Voltar para [[00-index]]. Bugs detalhados em [[auditoria-bugs]]; melhorias em [[melhorias]].

Executada em 16–17 de outubro de 2026 sobre o worktree `main` (com alterações não commitadas de empacotamento) e sobre o Raspberry de campo via SSH, somente leitura. Nenhuma cobrança real foi iniciada.

## Escopo e método

- leitura do código de `src/app247_terminal`, `updater/`, `scripts/` e `packaging/`;
- comparação de cada endpoint com os controllers e o handler WebSocket de `../app247` (commit `07e9d4a`);
- suíte completa: **234 testes aprovados** (`QT_QPA_PLATFORM=offscreen pytest`);
- reprodução isolada de `terminal.json` vazio;
- diagnóstico do Raspberry (ver BUG-045 e [[wifi]]).

## Estrutura

~12 mil linhas Python em `src/` (5,2 mil em testes). Camadas: `config/settings.py` (env e paths), `models/` (Terminal, Carrinho, Item, CompraSession), `repositories/` (SQLite: catálogo, checkpoint de pagamento, vínculo de cliente), `services/` (HTTP centralizado em `BackendClient`/`PurchaseApi`, sync, heartbeat, listener, Wi-Fi, display, telemetria, reset), `ui/screens/` (telas PyQt5) e `updater/` (validação de releases assinadas). Diretórios legados vazios descritos em BUG-052.

## Inicialização real

```text
main.run → prepare_runtime_layout → Terminal.load (sem tratamento: BUG-046)
  → MainWindow: reset pendente → ActivePaymentStore (integrity_check)
  → [pagamento pendente sem credencial] tela de recuperação
  → [ativado + credencial] iniciar_operacao_terminal:
        SyncService (thread) · TerminalSocket heartbeat (thread)
        PaymentListener (QThread) · InternetMonitor · Telemetria
        bootstrap de lifecycle (60 s)
  → [não ativado] cadastro por serial com polling
```

## Fluxo de compra real

```text
scanner (HID) → ScannerRouter → SQLite buscar_por_codigo → Carrinho (dedupe por produto.id)
 → resumo (ConfirmacaoCompra) → PointCheckoutWorker:
      POST/PUT /carrinho → checkpoint SQLite → POST /pagamento/terminal/{cartId}
 → PROCESSING: tela "finalize na maquininha" + polling GET /order/{id}/status
 → PAYMENT_STATUS (WS) ou polling → CompraSession.apply_status
      (ignora orderId/attemptId divergentes) → APPROVED / FAILED
 → confirmação, comprovante opcional, reset
```

A aprovação só ocorre com `orderId` igual ao da sessão e status definitivo do backend. Timeout, queda de rede e restart levam a reconciliação (`/pagamento/terminal/{terminalId}/ativo`), nunca a aprovação local.

## Integrações

Todos os endpoints usados existem no backend atual:

| Terminal | Backend |
|---|---|
| `GET /terminal/serial/{serial}` | `TerminalController` |
| `GET /terminal/{id}/bootstrap`, `POST .../factory-reset/{started,completed}`, `POST .../credential/migrate` | `TerminalController` |
| `GET /produtos/sync` | `ProdutoController` |
| `POST /carrinho`, `POST /carrinho/empty`, `PUT/GET /carrinho/{id}` | `CarrinhoController` |
| `POST /pagamento/terminal/{cartId}`, `GET /pagamento/terminal/{terminalId}/ativo`, `POST /pagamento/terminal/order/{orderId}/cancelamento` | `PagamentoController` |
| `GET /order/{orderId}/status` | `OrderController` |
| `GET /checkout/carrinho`, `GET /checkout/qrcode` | `CheckoutSessionController` |
| `POST /terminal/customer-link/consume` | `TerminalQrController` |
| `POST /comprovante` | `ComprovanteController` |
| `GET /terminal/health`, `POST /terminal/telemetry` | `TerminalTelemetryController` |
| WS `/terminal-socket`, `/payment-socket/{terminalId}` | `TerminalWebSocketConfig` + `TerminalHandshakeInterceptor` |

- O handshake de `/payment-socket/{id}` autoriza a credencial **contra o terminalId do path**; o terminal ainda revalida `terminalId`, `orderId` e `paymentAttemptId`. Um evento do Terminal A não libera o B.
- Status: o backend envia `TerminalPaymentStatus` (`WAITING_PAYMENT`, `APPROVED`, `REJECTED`, `CANCELLED`, `EXPIRED`, `ACTION_REQUIRED`, `REFUNDED`) e `mercadoPagoStatus`; o terminal usa `status` primeiro. Compatível.
- `PaymentSocketService` (STOMP `/topic/payment/...`) coexiste no backend; o terminal não o consome. Não é incompatibilidade, mas é caminho duplicado a revisar no backend.
- `POST /terminal/coupons/apply` existe no backend e ainda não é usado (pendência de QR de cupom).
- Nenhuma nova incompatibilidade de contrato encontrada; ver [[compatibilidade-backend]].

## Pontos fortes verificados

HTTP fora da UI thread com timeouts; correlação estrita de pagamento; checkpoint de pagamento em SQLite com `integrity_check`; polling como rede de segurança do WebSocket; credencial com verificação de dono/permissão/symlink e escrita com `fsync`; sync FULL/INCREMENTAL transacional; releases com Ed25519, SHA-256, arquitetura e bloqueio de downgrade.

## Achados novos

| ID | Severidade | Resumo |
|---|---|---|
| BUG-046 | alta | `terminal.json` vazio/corrompido derruba o app antes da UI — **corrigido 17/10** |
| BUG-047 | média | sem tratamento de `SIGTERM`; esperas de parada excedem `TimeoutStopSec` — **corrigido 17/10** |
| BUG-048 | média | latch global de 401/403; heartbeat/listener morrem até reinício |
| BUG-049 | média | socket de pagamento sem ping detecta mal a queda de Wi-Fi |
| BUG-050 | média | logs do app não persistem no Raspberry |
| BUG-051 | média | instalação de campo com layout antigo e `/opt/app247` gravável pelo usuário gráfico — unit migrável desde 17/10 |
| BUG-053 | alta | `ExecStartPre --apply-display` abria a GUI e entrava em loop — **corrigido 17/10** |
| BUG-054 | média | saída normal da GUI terminava em `TypeError` — **corrigido 17/10** |
| BUG-052 | baixa | código morto e diretórios legados |
| BUG-045 | alta | corrupção recorrente do Raspberry (ambiente, em investigação) |

BUG-045 e BUG-046 se reforçam: o hardware sofre desligamentos sujos e o software não se recupera de um arquivo de identidade danificado.

## Divergências de documentação

- 21 entradas antigas de [[auditoria-bugs]] (BUG-001 a BUG-005, 009 a 014, 016, 018 a 021, 023 a 027) não têm linha de **Status**. O código indica que várias foram resolvidas (ex.: BUG-002 pela correlação de orderId, BUG-011 por timeouts, BUG-019/023 pela remoção do `PixScreen`, BUG-026 pelo handshake autenticado). BUG-025 segue parcialmente aberto (BUG-052). Precisam de revisão formal.
- O contexto de continuidade citava versão 1.0.2 com build ARMHF: o repositório (`APP_VERSION = "1.0.1"`), `release/` (somente amd64) e o Raspberry (`releases/1.0.1`) não confirmam 1.0.2.
- O registro anterior dizia `802-11-wireless.powersave = 2`; o perfil está `default`.

## Prioridade sugerida

1. BUG-046 (recuperação de `terminal.json` + `fsync`) — pequeno e diretamente ligado ao campo.
2. BUG-050 + journal persistente (BUG-045) — sem logs não há diagnóstico.
3. BUG-047 (SIGTERM) e BUG-049 (ping) — robustez em desligamento e rede instável.
4. BUG-051 — testar o instalador atual contra o layout de campo antes de atualizar o Raspberry.
5. BUG-048, revisão de status antigos e BUG-052.

## Não verificado

Fluxo físico completo na Point (aprovar/recusar/cancelar) no Raspberry, renderização em hardware real, causa das 6 falhas de partida de 16/10 (sem logs) e a parte não commitada de `install.sh` em equipamento real.
