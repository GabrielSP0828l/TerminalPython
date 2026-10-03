# Documentação técnica do Terminal Python

Estado funcional verificado em 31 de agosto de 2026. O Terminal usa catálogo SQLite v2 com SKU e múltiplos barcodes, sincronização incremental orientada por UUID/`syncAt`, invalidação WebSocket e correlação Order + PaymentAttempt.

## Documentos

- [Arquitetura atual](arquitetura.md)
- [Fluxo real da compra](fluxo-compra.md)
- [APIs usadas pelo terminal](api-backend.md)
- [Contratos atuais com o backend](backend-contracts.md)
- [Matriz Terminal ↔ Backend](terminal-backend-contracts.md)
- [WebSocket](websocket.md)
- [Mercado Pago Point](mercado-pago.md)
- [SQLite](sqlite.md)
- [Sincronização de produtos](sincronizacao.md)
- [Product sync e promoções](product-sync.md)
- [Promoções no Terminal](promocoes.md)
- [Heartbeat do terminal](heartbeat.md)
- [Telemetria do Raspberry/Terminal](telemetria.md)
- [Rede na telemetria](network.md)
- [Compatibilidade com o backend](compatibilidade-backend.md)
- [Bugs e riscos](auditoria-bugs.md)
- [Melhorias propostas](melhorias.md)
- [Telas e navegação](telas.md)
- [[menu-administrativo]] — acesso autenticado e guardas operacionais
- [[wifi]] — NetworkManager/`nmcli`, segurança, timeouts e touchscreen
- [[display]] — orientação por compositor, persistência e startup
- [[design-system]] — paleta, tipografia e componentes oficiais
- [[layout-vertical]] — portrait, rotação Wayland e fallback landscape
- [[terminal-device-security]] — credencial individual, migração e modo seguro
- [[terminal-local-state-recovery]] — SQLite crítico, reset e startup recovery
- [[terminal-kiosk-mode]] — development/production, fullscreen e Wi-Fi pré-ativação
- [[terminal-worker-lifecycle]] — inventário, correlação e encerramento de workers

## Escopo e fontes

- [Vínculo de cliente por QR](customer-qr-link.md) — parser, worker HTTP, UI, payment lock e recovery mínimo.

Foram lidos os módulos Python relevantes, `main.py`, `config.py`, `requirements.txt`, os artefatos locais de configuração/persistência e a documentação disponível em `../app247/24por7_contexto/`. Também foram confrontados os controllers, DTOs, services e handlers WebSocket relevantes no código Spring Boot atual.

O arquivo `../app247/24por7_contexto/terminal-python.md` citado no `AGENTS.md` não existe no worktree auditado. O contexto funcional fornecido pelo solicitante foi considerado como especificação desejada.

## Limites da validação

- Nenhuma cobrança real foi criada.
- A interface foi validada por testes Qt offscreen; não foi operada no hardware físico.
- A suíte automatizada cobre fluxo, credencial individual, SQLite/migração,
  sync/barcodes, pagamento/recovery, telemetria e Qt offscreen; nenhuma cobrança
  real é criada.
- Wi-Fi e rotação foram simulados nos testes; a validação final de adaptador, compositor e touchscreen depende do Raspberry físico.
- O repositório já continha mudanças do usuário; elas foram preservadas.

## Conclusão executiva

O Terminal possui ativação por UUID e credential individual, cache SQLite
versionado, sync FULL/INCREMENTAL atômico, heartbeat, telemetria e pagamento
Point correlacionado por Order/tentativa com recovery após reinício. Permanecem
a validação E2E com os dois processos, scanner/Raspberry e Point físico.
