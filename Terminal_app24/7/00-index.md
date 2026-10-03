# Terminal Python App 24/7 — documentação técnica

Estado funcional verificado em 31 de agosto de 2026. O Terminal está adaptado ao catálogo com SKU/múltiplos barcodes, sync FULL/INCREMENTAL, cursor transacional `syncAt`, `PRODUCT_SYNC_REQUIRED` e PaymentAttempt.

## Visão e arquitetura

- [[terminal-python]] — contexto, responsabilidades, estado executivo e limites.
- [[terminal-lifecycle]] — estados autoritativos, reset remoto durável e dados removidos/preservados.
- [[arquitetura]] — lifecycle atual, services, threads e fontes de verdade.
- [[distribuicao-atualizacao]] — PyInstaller, instalação, releases e rollback.
- [[terminal-device-security]] — credencial individual, armazenamento e rotação.
- [[arquitetura-atual]] — inventário histórico detalhado.
- [[fluxo-compra]] — scanner, carrinho, checkout, pagamento, resultado e reset executáveis hoje.
- [[payment-recovery]] — recuperação segura com Point/backend offline, restart, clique repetido e timeout.
- [[telas]] — composição visual, grid do carrinho e métricas do display físico.
- [[menu-administrativo]] — autenticação efêmera, opções e guardas operacionais.
- [[wifi]] — NetworkManager/`nmcli`, segurança, timeouts e validação física.
- [[display]] — orientação do compositor e persistência no boot.

## Integrações e persistência

- [[api-backend]] — catálogo completo das chamadas HTTP e compatibilidade de contrato.
- [[websocket]] — heartbeat, pagamento, reconexão, segurança e correlação.
- [[sqlite]] — schema, cache, sync, reset e estado persistido.
- [[sincronizacao]] — FULL/INCREMENTAL, UPSERT/REMOVE, cursor e coalescência.
- [[heartbeat]] — sinal de vida confirmado após persistência.
- [[telemetria]] — saúde do Raspberry/Terminal Python, coleta leve e limites.
- [[compatibilidade-backend]] — divergências `COM-001` em diante entre terminal e backend.

## Auditoria e evolução

- [[auditoria-bugs]] — bugs confirmados e riscos potenciais `BUG-001` em diante.
- [[melhorias]] — plano incremental `MEL-001` em diante, sem refatoração aplicada nesta auditoria.

## Fontes analisadas

- `../../AGENTS.md` completo;
- módulos Python, testes, scripts e configurações relevantes do worktree atual;
- configurações, requirements, CSS, JSON, SQLite ativo/backup e estado Git;
- toda a documentação em `../app247/24por7_contexto/`;
- controllers, DTOs, services, repositories e handlers relevantes do backend atual.

## Validação e limites

- A suíte inclui testes de migration SQLite, sync/barcodes, Wi-Fi, display, recuperação de pagamento, WebSocket e factory reset remoto; a contagem vigente deve ser obtida na execução registrada no relatório da alteração.
- compilação dos módulos alterados passou;
- endpoint real configurado respondeu HTTP 200 e retornou `syncAt`;
- SQLite canônico: `./data/terminal.db` (desenvolvimento) ou `/var/lib/app247/terminal.db` (produção);
- nenhuma cobrança ou chamada financeira real foi executada.
- Wi-Fi e rotação foram simulados; adaptador, compositor e touchscreen ainda exigem validação no Raspberry físico.

## Conclusão

Ativação, UUID, catálogo local, sync em tempo real, heartbeat e roteamento de pagamento são separados e testados. Avisos WebSocket não carregam dados: sempre acionam o endpoint HTTP, com recuperação no reconnect e cursor gerado no servidor.
