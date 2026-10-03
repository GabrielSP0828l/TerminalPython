# Arquitetura do Terminal

Voltar para [[00-index]]. Inventário funcional em [[arquitetura-atual]] e
distribuição em [[distribuicao-atualizacao]].

## Estrutura executável

```text
src/app247_terminal/main.py
  → application.MainWindow
      ├── ui/screens
      │    └── CatalogService
      │         └── repositories → database/connection → SQLite
      ├── services (HTTP, WebSocket, sync, pagamento, lifecycle)
      ├── models (Terminal, carrinho, itens e CompraSession)
      └── config/settings.py
```

`main.py` configura logs, prepara o layout persistente, cria `QApplication` e
entrega o lifecycle para `MainWindow`. Navegação, timers, signals/slots,
workers, recovery financeiro e regras das telas permanecem em
`application.py`/componentes existentes; a reorganização não mudou contratos.

## Limites de responsabilidade

- UI: apresenta estado, captura scanner/toque e delega operações.
- Services: API Spring, sync, pagamento, WebSockets, heartbeat, telemetria,
  Wi-Fi, display e lifecycle.
- Repositories: catálogo, checkpoint de pagamento e vínculo local.
- Database: construção uniforme de conexões SQLite; schema/migrations atuais
  continuam idempotentes no repository de produtos.
- Backend: fonte de verdade para organização, estoque, Order e pagamento.

`TerminalScreen` usa `CatalogService` e `CustomerLinkStateService` em vez de
abrir repositories diretamente. Os demais acessos locais continuam
incrementais para preservar o comportamento auditado.

## Threads preservadas

- `PaymentListener`, workers HTTP, InternetMonitor, Wi-Fi e display: `QThread`.
- Sync, heartbeat e telemetria: threads Python com parada cooperativa.
- Callbacks financeiros continuam correlacionados por `CompraSession` e chegam
  à UI por signals/slots; nenhuma rede lenta passou para a thread Qt.

## Código, assets e estado

`src/` e `assets/` pertencem à release imutável. SQLite, identidade, credencial,
orientação, cursores e marcadores pertencem a `APP247_DATA_DIR`. O resolver de
assets funciona no repositório, via systemd e no PyInstaller.

Veja [[sqlite]], [[terminal-local-state-recovery]], [[fluxo-compra]],
[[websocket]] e [[distribuicao-atualizacao]].
