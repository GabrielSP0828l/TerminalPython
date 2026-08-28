# Terminal Python App 24/7 — documentação técnica

Estado funcional verificado em 24 de agosto de 2026. O Terminal está adaptado ao contrato de sync FULL/INCREMENTAL, cursor `syncAt` do backend e `PRODUCT_SYNC_REQUIRED`.

## Visão e arquitetura

- [[terminal-python]] — contexto, responsabilidades, estado executivo e limites.
- [[arquitetura]] — lifecycle atual, services, threads e fontes de verdade.
- [[arquitetura-atual]] — inventário histórico detalhado.
- [[fluxo-compra]] — scanner, carrinho, checkout, pagamento, resultado e reset executáveis hoje.

## Integrações e persistência

- [[api-backend]] — catálogo completo das chamadas HTTP e compatibilidade de contrato.
- [[websocket]] — heartbeat, pagamento, reconexão, segurança e correlação.
- [[sqlite]] — schema, cache, sync, reset e estado persistido.
- [[sincronizacao]] — FULL/INCREMENTAL, UPSERT/REMOVE, cursor e coalescência.
- [[heartbeat]] — sinal de vida confirmado após persistência.
- [[compatibilidade-backend]] — divergências `COM-001` em diante entre terminal e backend.

## Auditoria e evolução

- [[auditoria-bugs]] — bugs confirmados e riscos potenciais `BUG-001` em diante.
- [[melhorias]] — plano incremental `MEL-001` em diante, sem refatoração aplicada nesta auditoria.

## Fontes analisadas

- `../../AGENTS.md` completo;
- 27 arquivos Python atuais, totalizando 3.198 linhas incluindo testes;
- configurações, requirements, CSS, JSON, SQLite ativo/backup e estado Git;
- toda a documentação em `../app247/24por7_contexto/`;
- controllers, DTOs, services, repositories e handlers relevantes do backend atual.

## Validação e limites

- 72 testes Python passaram, inclusive recuperação de pagamento e Qt offscreen;
- compilação dos módulos alterados passou;
- endpoint real configurado respondeu HTTP 200 e retornou `syncAt`;
- SQLite canônico: `/home/jefiro/Documentos/projetos/TerminalPython/db/terminal.db`;
- nenhuma cobrança ou chamada financeira real foi executada.

## Conclusão

Ativação, UUID, catálogo local, sync em tempo real, heartbeat e roteamento de pagamento são separados e testados. Avisos WebSocket não carregam dados: sempre acionam o endpoint HTTP, com recuperação no reconnect e cursor gerado no servidor.
