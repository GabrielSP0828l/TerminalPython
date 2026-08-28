# Documentação técnica do Terminal Python

Estado funcional verificado em 24 de agosto de 2026. O Terminal usa sincronização incremental orientada por UUID, `syncAt` do backend e invalidação WebSocket em tempo real.

## Documentos

- [Arquitetura atual](arquitetura.md)
- [Fluxo real da compra](fluxo-compra.md)
- [APIs usadas pelo terminal](api-backend.md)
- [WebSocket](websocket.md)
- [Mercado Pago Point](mercado-pago.md)
- [SQLite](sqlite.md)
- [Sincronização de produtos](sincronizacao.md)
- [Heartbeat do terminal](heartbeat.md)
- [Compatibilidade com o backend](compatibilidade-backend.md)
- [Bugs e riscos](auditoria-bugs.md)
- [Melhorias propostas](melhorias.md)
- [Telas e navegação](telas.md)
- [[design-system]] — paleta, tipografia e componentes oficiais
- [[layout-vertical]] — portrait, rotação Wayland e fallback landscape

## Escopo e fontes

Foram lidos os 23 módulos Python do repositório (2.911 linhas), `main.py`, `config.py`, `requirements.txt`, os artefatos locais de configuração/persistência e toda a documentação disponível em `../app247/24por7_contexto/`. Também foram confrontados os controllers, DTOs, services e handlers WebSocket relevantes no código Spring Boot atual.

O arquivo `../app247/24por7_contexto/terminal-python.md` citado no `AGENTS.md` não existe no worktree auditado. O contexto funcional fornecido pelo solicitante foi considerado como especificação desejada.

## Limites da validação

- Nenhuma cobrança real foi criada.
- A interface foi validada por testes Qt offscreen; não foi operada no hardware físico.
- A suíte automatizada inclui testes de fluxo, integrações e layout Qt portrait; nenhuma cobrança real é criada.
- O repositório já continha mudanças do usuário; elas foram preservadas.

## Conclusão executiva

O terminal possui ativação por UUID, cache SQLite com UUID textual, sync FULL/INCREMENTAL com cursor do servidor, invalidação WebSocket, heartbeat confirmado após persistência, carrinho e pagamento Point correlacionado. Nesta verificação, o catálogo local permaneceu vazio porque o endpoint incremental não tinha alterações para o terminal. Pendências de produção incluem autenticação dos sockets e persistência da tentativa de pagamento após reboot.
