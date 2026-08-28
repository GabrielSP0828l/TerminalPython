# Melhorias recomendadas

Voltar para [o índice](00-index.md). Nenhuma melhoria abaixo foi implementada nesta auditoria.

## MEL-001 — Unificar identidade do terminal

**Status:** implementada nesta primeira etapa, incluindo compatibilidade com JSON legado.

- **Prioridade:** P0
- **Complexidade:** média
- **Benefício:** restaura ativação, heartbeat, carrinho e socket com UUID único, preservando instalações legadas.
- **Arquivos envolvidos:** `model/Terminal.py`, `CadastroTerminalScreen.py`, `Carrinho.py`, `TerminalSocket.py`, `PaymentListener.py`, migration de `terminal.json`.

## MEL-002 — Definir contrato terminal-oriented de produtos disponíveis

- **Prioridade:** P0
- **Complexidade:** alta (cliente + backend)
- **Benefício:** terminal recebe somente catálogo vendável do próprio condomínio, sem escolher empresa/condomínio.
- **Arquivos envolvidos:** `SyncService.py`, `Produtos.py`, backend Produto/Estoque/Terminal controllers e DTOs, documentação API.

## MEL-003 — Migrar cache SQLite para UUID e schema versionado

- **Prioridade:** P0
- **Complexidade:** média
- **Benefício:** compatibilidade com IDs atuais e upgrades seguros em terminais instalados.
- **Arquivos envolvidos:** `DatabaseProdutos.py`, novo mecanismo de migrations, `terminal.db`.

## MEL-004 — Implementar estado explícito da tentativa de compra

- **Prioridade:** P0
- **Complexidade:** alta
- **Benefício:** impede reset prematuro, cliques duplicados e eventos antigos; permite recuperação.
- **Arquivos envolvidos:** `TerminalScreen`, `PagamentoScreen`, `ConfirmacaoScreen`, modelos/persistência operacional.

## MEL-005 — Conectar checkout Point incrementalmente

- **Prioridade:** P0
- **Complexidade:** alta
- **Benefício:** crédito/débito passam a criar carrinho/Order/cobrança exclusivamente via backend e aguardam confirmação.
- **Arquivos envolvidos:** `pagamento.py`, novo serviço HTTP, backend Pagamento/Order DTOs e documentação.

## MEL-006 — Corrigir entrega e correlação de status

- **Prioridade:** P0
- **Complexidade:** alta (cliente + backend)
- **Benefício:** somente a Order ativa do terminal correto pode liberar a UI.
- **Arquivos envolvidos:** `PaymentListener.py`, `terminal_screen.py`, backend `PagamentoService`, `PaymentEvent`, handlers WebSocket.

## MEL-007 — Reconciliação após startup/reconexão

- **Prioridade:** P0
- **Complexidade:** alta
- **Benefício:** resolve “backend pago + terminal em erro” e eventos perdidos.
- **Arquivos envolvidos:** persistência de tentativa, sockets, client HTTP, novo/ajustado endpoint backend autorizado.

## MEL-008 — Idempotência do envio do carrinho/checkout

- **Prioridade:** P0
- **Complexidade:** alta (contrato conjunto)
- **Benefício:** evita carrinhos, Orders e cobranças duplicadas após timeout/clique duplo.
- **Arquivos envolvidos:** telas de pagamento, serviço HTTP, backend Carrinho/Order/Pagamento e banco.

## MEL-009 — Centralizar HTTP com workers Qt

- **Prioridade:** P1
- **Complexidade:** média
- **Benefício:** timeouts, parsing e erros uniformes sem bloquear/violar a UI thread.
- **Arquivos envolvidos:** `SyncService.py`, `CadastroTerminalScreen.py`, `pagamento.py`, `app_payment_screen.py`, `login_screen.py`, `Produtos.py`.

## MEL-010 — Tratar estados internos completos

**Status:** implementada visualmente em 28 de agosto de 2026.

- **Prioridade:** P1
- **Complexidade:** média
- **Benefício:** UI coerente para intermediário, aprovado, recusado, cancelado e expirado, sem interpretar detalhes do Mercado Pago.
- **Arquivos envolvidos:** listener, telas de pagamento/confirmacão e DTO backend.
- **Implementação:** vermelho fullscreen para falha definitiva, laranja para ação na Point, loading para processamento e verde para aprovado; SVGs são recoloridos em memória e motivos técnicos não chegam ao cliente.

## MEL-027 — CPF e comprovantes pós-compra

**Status:** pendente de contrato backend.

- **Prioridade:** P1.
- **Motivo:** Order/Pagamento não possuem CPF e não há endpoint de comprovante nem integração WhatsApp; o e-mail existente é exclusivo de identidade.
- **Interface atual:** preserva quatro ações no sucesso e informa indisponibilidade sem simular persistência/envio.
- **Próximo passo:** definir endpoints idempotentes por Order/Terminal, modelo de comprovante interno e providers no backend; nunca colocar SMTP/WhatsApp secrets no Terminal.

## MEL-011 — Lifecycle único pós-ativação

**Status:** implementada nesta primeira etapa.

- **Prioridade:** P1
- **Complexidade:** baixa
- **Benefício:** ativação em runtime inicia exatamente uma vez sync, heartbeat, listener e telas.
- **Arquivos envolvidos:** `main.py`, `CadastroTerminalScreen.py`, services.

## MEL-012 — Autenticar terminal e WebSockets

- **Prioridade:** P1 antes de produção
- **Complexidade:** alta
- **Benefício:** impede personificação e vazamento/liberação cross-terminal.
- **Arquivos envolvidos:** provisionamento local, headers/handshake, backend Security/WebSocket/TerminalService.

## MEL-013 — Tornar sync transacional e completo

**Status:** implementada em 24 de agosto de 2026 para o contrato atual FULL/INCREMENTAL, incluindo UPSERT/REMOVE e cursor do backend.

- **Prioridade:** P1
- **Complexidade:** média
- **Benefício:** cache não fica parcial; desativações/tombstones e cursor são aplicados atomicamente.
- **Arquivos envolvidos:** `SyncService.py`, `DatabaseProdutos.py`, contrato backend.

## MEL-014 — Normalizar preço, quantidade e peso

- **Prioridade:** P1
- **Complexidade:** média
- **Benefício:** linha, total visual e validação backend usam semântica consistente por unidade de medida.
- **Arquivos envolvidos:** `Item.py`, `Carrinho.py`, `terminal_screen.py`, DTO/item backend.

## MEL-015 — Logging estruturado e sanitizado

- **Prioridade:** P1
- **Complexidade:** baixa
- **Benefício:** rastreia terminal/carrinho/Order/status sem imprimir QR, tokens, body sensível ou stack trace ao usuário.
- **Arquivos envolvidos:** todos os módulos com `print`, `except` e traceback.

## MEL-016 — Monitorar backend e estado da compra

- **Prioridade:** P1
- **Complexidade:** média
- **Benefício:** offline/reconexão deixam de depender do Google e não alteram status financeiro localmente.
- **Arquivos envolvidos:** `InternetMonitor.py`, `main.py`, overlay, client HTTP/socket.

## MEL-017 — Persistir estado operacional mínimo

- **Prioridade:** P1
- **Complexidade:** média
- **Benefício:** reboot preserva IDs necessários à reconciliação sem transformar SQLite em fonte de verdade.
- **Arquivos envolvidos:** SQLite/migrations, checkout e startup.

## MEL-018 — Testes automatizados sem cobrança real

**Status:** cobertura de sincronização e heartbeat implementada em 24 de agosto de 2026; cobertura global continua evolutiva.

- **Prioridade:** P1
- **Complexidade:** média
- **Benefício:** protege scanner, carrinho, DTOs, timeout, reconexão e estados de pagamento.
- **Arquivos envolvidos:** nova suíte `tests/`, doubles HTTP/WebSocket, fixtures SQLite/Qt.

## MEL-019 — Remover confirmação manual financeira do PIX legado

- **Prioridade:** P1
- **Complexidade:** baixa após contrato correto
- **Benefício:** impede aprovação por ação do usuário.
- **Arquivos envolvidos:** `pix.py`, fluxo de status.

## MEL-020 — Revisar código morto em etapa isolada

- **Prioridade:** P2
- **Complexidade:** baixa
- **Benefício:** reduz rotas/telas quebradas e configuração duplicada sem risco ao fluxo ativo.
- **Arquivos envolvidos:** `login_screen.py`, `teclado.py`, `Produtos.get_produtos_api`, URL hardcoded, imagens temporárias.

## MEL-021 — Menu local de configurações e reset recuperável

**Status:** primeira implementação concluída.

- **Prioridade:** P2
- **Complexidade:** baixa
- **Benefício:** substitui o encerramento oculto por uma área de manutenção explícita e permite voltar ao primeiro cadastro sem apagar configuração do backend.
- **Arquivos envolvidos:** `HoldToExitLabel.py`, `bemvindo.py`, `ConfiguracaoScreen.py`, `FactoryResetService.py`, `main.py`.

## MEL-022 — Design system central e adoção visual gradual

**Status:** concluída globalmente em 27 de agosto de 2026.

- **Prioridade:** P1 para novas telas; P2 para migração das telas estáveis.
- **Complexidade:** média.
- **Benefício:** uma única linguagem visual, estados previsíveis e menos QSS/hexadecimais duplicados sem uma reescrita ampla da interface.
- **Implementação:** todas as telas usam `styles/tokens.py`/`styles/theme.py`; QSS legado duplicado foi removido; targets, tipografia e estados foram padronizados.

## MEL-025 — Layout portrait e confirmação explícita

**Status:** implementada em 27 de agosto de 2026.

- `768x1360` é a geometria prioritária, mantendo fallback landscape.
- total e ações permanecem fora do scroll nas telas de compra/confirmacão.
- `Finalizar` abre resumo sem rede; `Confirmar e pagar` inicia o Point atual.
- `start.sh` permite rotação Wayland opcional sem saída hardcoded e sem bloquear startup.
- pendência operacional: validar transform 90/270 e calibração touch no hardware final.

## MEL-026 — Proteção integral do menu administrativo

**Status:** implementada em 28 de agosto de 2026.

- preserva o toque longo e a `ConfiguracaoScreen` existentes;
- exige `TERMINAL_ADMIN_PASSWORD` antes de mostrar qualquer opção;
- reutiliza o teclado alfanumérico touchscreen e mascara o campo;
- descarta a autorização ao sair e exige senha em cada novo acesso;
- mantém o reset recuperável e acrescenta `Fechar Terminal` com aviso contextual;
- bloqueia `Esc`/fechamento comum e centraliza shutdown cooperativo e idempotente;
- não reseta compra nem cancela cobrança em andamento.

## MEL-023 — Coalescer invalidações de catálogo em tempo real

**Status:** implementada em 24 de agosto de 2026.

- **Prioridade:** P0.
- **Benefício:** eventos recebidos durante uma sincronização não abrem writers SQLite concorrentes nem são perdidos.
- **Implementação:** `SyncService.request_sync` usa lock, `sync_in_progress` e `sync_pending`; conexão/reconexão e `PRODUCT_SYNC_REQUIRED` passam pelo mesmo coordenador.
- **Cobertura:** vários eventos rápidos resultam na execução atual mais, no máximo, uma execução pendente.

## MEL-024 — Estado persistente de inicialização do catálogo

**Status:** implementada em 24 de agosto de 2026.

- **Prioridade:** P0.
- **Benefício:** impede usar cursor incremental quando o SQLite foi recriado, truncado ou nunca recebeu FULL.
- **Implementação:** marcador singleton e contagem ativa esperada na mesma transação de catálogo; inconsistência força FULL sem apagar cache antes da resposta.
- **Semântica de vazio:** FULL vazio é válido e inicializa contagem zero; produto da empresa sem `EstoqueCondominio` não aparece no Terminal.

## Ordem recomendada das correções

1. Congelar e testar o contrato de identidade; migrar `terminal.json`.
2. Criar o contrato seguro de catálogo disponível por terminal e migrar SQLite.
3. Definir tentativa/estado/idempotência e DTO de início Point.
4. Conectar cartão ao backend sem reset antecipado.
5. Publicar/consumir estados correlacionados e adicionar consulta após reconexão.
6. Centralizar rede fora da UI, logging e monitoramento.
7. Cobrir tudo com testes antes de remover legado.
