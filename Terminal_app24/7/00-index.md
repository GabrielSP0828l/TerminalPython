# Terminal Python App 24/7 — documentação técnica

Estado funcional verificado em 28 de agosto de 2026. O Terminal está adaptado ao contrato de sync FULL/INCREMENTAL, cursor `syncAt` do backend, `PRODUCT_SYNC_REQUIRED` e manutenção local autenticada.

## Visão e arquitetura

- [[terminal-python]] — contexto, responsabilidades, estado executivo e limites.
- [[arquitetura]] — lifecycle atual, services, threads e fontes de verdade.
- [[arquitetura-atual]] — inventário histórico detalhado.
- [[fluxo-compra]] — scanner, carrinho, checkout, pagamento, resultado e reset executáveis hoje.
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

- 113 testes Python passaram, inclusive Wi-Fi, display, recuperação de pagamento e Qt offscreen;
- compilação dos módulos alterados passou;
- endpoint real configurado respondeu HTTP 200 e retornou `syncAt`;
- SQLite canônico: `/home/jefiro/Documentos/projetos/TerminalPython/db/terminal.db`;
- nenhuma cobrança ou chamada financeira real foi executada.
- Wi-Fi e rotação foram simulados; adaptador, compositor e touchscreen ainda exigem validação no Raspberry físico.

## Conclusão

Ativação, UUID, catálogo local, sync em tempo real, heartbeat e roteamento de pagamento são separados e testados. Avisos WebSocket não carregam dados: sempre acionam o endpoint HTTP, com recuperação no reconnect e cursor gerado no servidor.
