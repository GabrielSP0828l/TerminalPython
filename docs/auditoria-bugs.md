# Bugs e riscos do Terminal Python

Voltar para [o índice](00-index.md).

Critério: **confirmado** quando o caminho executável ou contrato prova o comportamento; **potencial** quando depende de timing, ambiente ou dados externos. Linhas referem-se ao worktree auditado.

## BUG-001 — Crédito/débito concluem sem backend

- **Severidade:** crítica
- **Tipo:** confirmado
- **Arquivo/função:** `telas/pagamento.py`, `PagamentoScreen.finalizar_venda`
- **Cenário:** usuário escolhe crédito ou débito.
- **Impacto:** UI volta ao início sem Carrinho, Order, Pagamento ou cobrança Point; estado local fica parcialmente sujo.
- **Correção recomendada:** conectar ao checkout Point e só finalizar após estado definitivo do backend.

## BUG-002 — Qualquer mensagem WebSocket aprova a compra

- **Severidade:** crítica
- **Tipo:** confirmado
- **Arquivo/função:** `database/PaymentListener.py:44-48`; `telas/terminal_screen.py:267-271`
- **Cenário:** socket recebe qualquer JSON, inclusive falha/cancelamento/evento antigo.
- **Impacto:** liberação indevida de mercadoria.
- **Correção recomendada:** validar schema, status definitivo, terminal e Order ativa.

## BUG-003 — Identidade atual do backend quebra ativação nova

**Status após auditoria:** corrigido no cliente com UUID canônico e compatibilidade legada.

- **Severidade:** crítica
- **Tipo:** confirmado por contrato
- **Arquivo/função:** `model/Terminal.py`; `model/Carrinho.py:8-10`; `PaymentListener.__init__`
- **Cenário:** backend devolve `terminalId` UUID sem `uuidTerminal`.
- **Impacto:** carrinho e socket usam `None`; heartbeat pode usar tipo legado.
- **Correção recomendada:** migration compatível para um UUID canônico.

## BUG-004 — Endpoint e DTO de pagamento são incompatíveis

- **Severidade:** crítica
- **Tipo:** confirmado
- **Arquivo/função:** `telas/pagamento.py:275-293`
- **Cenário:** botão PIX tenta `GET /pagamento/terminal?carrinho_id=` e espera QR.
- **Impacto:** fluxo falha contra backend atual; não inicia Point corretamente.
- **Correção recomendada:** contrato coordenado específico para início Point.

## BUG-005 — Evento de pagamento não é publicado pelo backend ativo

- **Severidade:** crítica
- **Tipo:** confirmado no backend atual
- **Arquivo/função:** cliente `PaymentListener`; backend `PagamentoService.atualizarPagamento`
- **Cenário:** webhook processa aprovação.
- **Impacto:** banco/estoque podem concluir enquanto terminal não recebe resultado.
- **Correção recomendada:** publicação confiável após persistência mais consulta/replay.

## BUG-006 — Cache não aceita UUID de produto

**Status:** corrigido; PK textual e migração cobertas por teste.

- **Severidade:** alta
- **Tipo:** confirmado por schema/contrato
- **Arquivo/função:** `DatabaseProdutos.create_table/salvar_ou_atualizar`
- **Cenário:** sync tenta gravar `ProdutoResponse.id` UUID em PK INTEGER.
- **Impacto:** sincronização interrompida; catálogo fica antigo.
- **Correção recomendada:** migration local versionada para PK textual.

## BUG-007 — Sync atual não possui contexto de empresa

**Status:** corrigido; o endpoint atual deriva condomínio pelo `uuidTerminal`.

- **Severidade:** alta
- **Tipo:** confirmado por contrato
- **Arquivo/função:** `SyncService.sincronizar_produtos`
- **Cenário:** GET anônimo em `/produtos/sync`.
- **Impacto:** backend atual rejeita por ausência de `EmpresaContext`.
- **Correção recomendada:** autenticação/endpoint por terminal, sem enviar tenant arbitrário.

## BUG-008 — Produtos não são filtrados pelo estoque do condomínio

**Status:** corrigido pelo `ProdutoSyncService` orientado a Terminal/`EstoqueCondominio`.

- **Severidade:** alta
- **Tipo:** confirmado
- **Arquivo/função:** `SyncService.sincronizar_produtos`
- **Cenário:** sync usa catálogo da empresa.
- **Impacto:** terminal pode exibir/vender produto indisponível naquele condomínio.
- **Correção recomendada:** catálogo disponível derivado do terminal no backend.

## BUG-009 — Reset de cartão não limpa o carrinho lógico

- **Severidade:** alta
- **Tipo:** confirmado
- **Arquivo/função:** `PagamentoScreen.finalizar_venda`
- **Cenário:** remove widgets e zera labels, sem limpar `carrinho.items`/`linhas`.
- **Impacto:** próxima compra pode reutilizar itens invisíveis; `linhas` ainda bloqueia scans como existentes.
- **Correção recomendada:** usar um único reset somente após resultado definitivo.

## BUG-010 — POST de carrinho pode duplicar compras

- **Severidade:** alta
- **Tipo:** potencial
- **Arquivo/função:** `PagamentoScreen.ir_para_pix`; `AppPaymentScreen.gerar_checkout`
- **Cenário:** clique duplo, timeout ou retry após resposta perdida.
- **Impacto:** múltiplos carrinhos e potencialmente Orders/cobranças duplicadas.
- **Correção recomendada:** bloquear tentativa concorrente, idempotência e persistência de IDs.

## BUG-011 — Sem timeout nas chamadas de compra

- **Severidade:** alta
- **Tipo:** confirmado
- **Arquivo/função:** `pagamento.py`; `app_payment_screen.py`; `Produtos.get_produtos_api`
- **Cenário:** backend não responde.
- **Impacto:** UI congela no PIX ou thread fica presa indefinidamente.
- **Correção recomendada:** connect/read timeouts e erros tipados centralizados.

## BUG-012 — HTTP é executado na UI thread

- **Severidade:** alta
- **Tipo:** confirmado
- **Arquivo/função:** `CadastroTerminalScreen.verificar_ativacao`; `PagamentoScreen.ir_para_pix`
- **Cenário:** rede lenta a cada timer/click.
- **Impacto:** interface congela por até 5 s na ativação ou indefinidamente no pagamento.
- **Correção recomendada:** worker Qt com signals e guarda contra sobreposição.

## BUG-013 — Thread de checkout altera widgets Qt diretamente

- **Severidade:** alta
- **Tipo:** potencial/race confirmada no desenho
- **Arquivo/função:** `AppPaymentScreen.gerar_checkout:169-172`
- **Cenário:** thread daemon chama `hide`, `setPixmap`, `setText`.
- **Impacto:** comportamento indefinido, crash ou corrupção da UI.
- **Correção recomendada:** emitir signals para a UI thread.

## BUG-014 — Evento tardio pode liberar nova compra

- **Severidade:** crítica
- **Tipo:** potencial
- **Arquivo/função:** `PaymentListener`; `TerminalScreen.pagamento_aprovado`
- **Cenário:** compra A expira/reset; compra B começa; evento de A chega.
- **Impacto:** B é marcada como sucesso/liberada.
- **Correção recomendada:** geração/tentativa persistida e correlação estrita por Order.

## BUG-015 — Aprovação durante desconexão não é recuperada

**Status:** corrigido para queda/reconexão do backend e perda do WebSocket; reboot físico continua pendente.

- **Severidade:** alta
- **Tipo:** confirmado pela ausência de mecanismo
- **Arquivo/função:** `PaymentListener.run`; persistência local
- **Cenário:** webhook aprova enquanto socket está offline.
- **Impacto:** backend pago e terminal exibindo espera/erro.
- **Correção recomendada:** consulta de estado no reconnect/startup e replay confiável.

## BUG-016 — Listener pode não encerrar

- **Severidade:** média
- **Tipo:** potencial
- **Arquivo/função:** `PaymentListener.stop/run`
- **Cenário:** `ws.recv()` bloqueia; `stop()` chama `wait()` sem fechar socket.
- **Impacto:** shutdown travado; recurso/conexão órfã.
- **Correção recomendada:** timeout/close cooperativo e lifecycle da janela.

## BUG-017 — Sync não representa remoções/status

**Status:** corrigido em 24 de agosto de 2026 pelo contrato `UPSERT/REMOVE` e filtro `status=1`.

- **Severidade:** alta
- **Tipo:** confirmado
- **Arquivo/função:** `SyncService`; `DatabaseProdutos`
- **Cenário:** produto é desativado/removido ou backend envia `ativo`.
- **Impacto:** cache mantém e scanner aceita produto obsoleto; consulta não filtra status.
- **Correção recomendada:** contrato delta completo/tombstones e filtro local.

## BUG-018 — Cálculo de peso é inconsistente

- **Severidade:** alta
- **Tipo:** confirmado
- **Arquivo/função:** `Item.subtotal`; `Carrinho.total`; `TerminalScreen`
- **Cenário:** todo item recebe peso 1.0; linha pode usar peso e total usa quantidade.
- **Impacto:** valores visuais divergentes e payload sem semântica correta para pesáveis.
- **Correção recomendada:** regra por unidade de medida validada no backend.

## BUG-019 — PIX pode ser confirmado manualmente

- **Severidade:** crítica
- **Tipo:** confirmado em eventual backend legado
- **Arquivo/função:** `PixScreen.finalizar_pagamento`
- **Cenário:** usuário toca CONFIRMAR sem aprovação backend.
- **Impacto:** terminal finaliza localmente pagamento não confirmado.
- **Correção recomendada:** remover confirmação financeira manual; aguardar backend.

## BUG-020 — Timer de ativação é criado duas vezes

**Status após auditoria:** corrigido; existe um único timer e uma única consulta em voo.

- **Severidade:** média
- **Tipo:** confirmado
- **Arquivo/função:** `CadastroTerminalScreen.__init__:23-30,135-143`
- **Cenário:** instalação não ativada.
- **Impacto:** primeiro timer perde referência mas continua ativo; consultas duplicadas/sobrepostas na UI.
- **Correção recomendada:** um único timer com estado in-flight.

## BUG-021 — Ativação na mesma execução não inicia sync/heartbeat

**Status após auditoria:** corrigido por `MainWindow.iniciar_operacao_terminal`, compartilhado entre startup e ativação em runtime.

- **Severidade:** alta
- **Tipo:** confirmado
- **Arquivo/função:** `CadastroTerminalScreen.verificar_ativacao`; `MainWindow.__init__`
- **Cenário:** terminal é ativado após abrir app.
- **Impacto:** telas/listener iniciam, mas `SyncService` e `TerminalSocket` não; exige reinício para operação completa.
- **Correção recomendada:** lifecycle único pós-ativação idempotente.

## BUG-022 — Monitor offline está desativado

**Status:** corrigido em 28 de agosto de 2026.

- **Severidade:** média
- **Tipo:** confirmado
- **Arquivo/função:** `main.py:100-102`
- **Cenário:** internet/backend cai.
- **Impacto:** overlay nunca aparece e não há recuperação coordenada.
- **Correção aplicada:** `MainWindow` inicia/para um monitor do `API_URL`. O overlay oferece acesso ao mesmo fluxo administrativo autenticado de Wi-Fi e é suspenso somente durante essa manutenção. Reconexão de socket, sync e heartbeat permanece com os serviços existentes.

## BUG-023 — Logs expõem dados e não têm estrutura

- **Severidade:** alta
- **Tipo:** confirmado
- **Arquivo/função:** `PixScreen` imprime copia-e-cola; vários `print`/`traceback.print_exc`
- **Cenário:** PIX legado ou falha HTTP.
- **Impacto:** dado de pagamento e detalhes técnicos em console; baixa rastreabilidade.
- **Correção recomendada:** logging estruturado/sanitizado com terminal, carrinho e Order.

## BUG-024 — Segredo de configuração local e URL hardcoded

- **Severidade:** média
- **Tipo:** confirmado/potencial
- **Arquivo/função:** `.env`; `PagamentoScreen.__init__:26`
- **Cenário:** arquivo local contém endpoints; classe também contém URL ngrok, embora não a use nas requisições atuais.
- **Impacto:** configuração duplicada, túnel legado e risco de versionamento indevido.
- **Correção recomendada:** uma configuração validada; manter `.env` fora do versionamento e nunca incluir tokens.

## BUG-025 — Código morto contém falhas de runtime

- **Severidade:** baixa enquanto inacessível
- **Tipo:** confirmado
- **Arquivo/função:** `TecladoScreen.finalizar` (`parentrminal`); cancelamento usa `parent.login`, hoje `None`; `LoginScreen` usa endpoint ausente.
- **Cenário:** reativação futura dessas telas.
- **Impacto:** `AttributeError`/fluxo quebrado.
- **Correção recomendada:** só revisar/remover em etapa separada após confirmar intenção.

## BUG-026 — Socket permite personificação/substituição de terminal

- **Severidade:** alta
- **Tipo:** confirmado no desenho
- **Arquivo/função:** URLs e handlers nativos cliente/backend
- **Cenário:** cliente informa UUID de outro terminal.
- **Impacto:** heartbeat falso ou ocupação do canal de pagamento de outro equipamento.
- **Correção recomendada:** autenticação de provisionamento e vínculo no handshake.

## BUG-027 — Erros relevantes são engolidos ou exibidos ao cliente

- **Severidade:** média
- **Tipo:** confirmado
- **Arquivo/função:** vários `except:`; `PagamentoScreen.ir_para_pix` mostra `str(e)` em `QMessageBox`
- **Cenário:** falha de rede/JSON/backend.
- **Impacto:** diagnóstico perdido ou corpo técnico exibido ao consumidor.
- **Correção recomendada:** separar erro técnico logado de mensagem amigável.

## BUG-028 — Cadastro excedia a altura e aparentava perder fullscreen

**Status:** corrigido em 16 de agosto de 2026.

- **Severidade:** alta para operação do primeiro cadastro.
- **Tipo:** confirmado por inspeção de size hints e reprodução em `1024x600`.
- **Arquivo/função:** `telas/CadastroTerminalScreen.py::_montar_interface`; `css/cadastro_terminal.css`; entrypoint de `main.py`.
- **Cenário:** cadastro como primeira tela em terminal com 600 px de altura.
- **Causa:** título, subtítulo, QR fixo de 300 px, identificação e status eram empilhados verticalmente, somados a 160 px de margins internas/externas e spacings. O card tinha largura máxima de 620 px e não era expansível. A janela ainda recebia `show()` logo após `showFullScreen()`.
- **Impacto:** o Qt não conseguia respeitar todos os size hints; card/componentes ficavam comprimidos, cortados ou desalinhados, dando aparência de página menor que o fullscreen.
- **Correção aplicada:** página/card expansíveis, corpo em grid responsivo, modo horizontal para paisagem, vertical para retrato, QR escalado no resize e um único `showFullScreen()` no `MainWindow`.
- **Validação:** testes em `1024x600`, `600x1024`, resize repetido e smoke test do stacked fullscreen.

## BUG-029 — Estilos visuais fragmentados entre telas

**Status:** corrigido em 27 de agosto de 2026.

- **Severidade:** média.
- **Tipo:** confirmado.
- **Arquivo/função:** QSS inline em `terminal_screen.py`, `pix.py`, `pagamento.py`, `app_payment_screen.py`, `ConfirmacaoScreen.py`, `OfflineOverlay.py` e folhas em `css/`.
- **Cenário:** telas equivalentes definem diretamente famílias de azul, vermelho e verde, fontes, paddings e raios diferentes.
- **Impacto:** identidade inconsistente, estados visualmente ambíguos e manutenção sujeita a divergências.
- **Correção aplicada:** todas as telas foram migradas aos tokens/temas centrais; folhas QSS sem chamadores foram removidas; tipografia, cards, botões, inputs, loading e estados foram unificados.
- **Validação:** smoke visual de todas as telas em `768x1360` e render do carrinho/confirmação com texto longo e preço grande.

## BUG-034 — Carrinho iniciava cobrança sem confirmação explícita

**Status:** corrigido em 27 de agosto de 2026.

- **Causa:** “PAGAR AGORA” chamava diretamente o worker Point; “PAGAR NO APP” competia como ação paralela.
- **Correção:** ação única `FINALIZAR`, nova `ConfirmacaoCompraScreen` ligada ao mesmo Carrinho e início remoto somente por `CONFIRMAR E PAGAR`.
- **Regressão protegida:** voltar preserva a mesma instância do carrinho e duplo toque é bloqueado ao desabilitar o botão.

## BUG-035 — Teclado legado avançava por atributo inexistente

**Status:** corrigido em 27 de agosto de 2026; rota continua inativa.

- `self.parentrminal` foi substituído por `self.parent.terminal`.
- Teclas e ações foram ampliadas para toque; o endpoint legado de login continua registrado como incompatível e não foi reativado.

## BUG-036 — Menu administrativo e saída do quiosque sem autenticação

**Status:** corrigido em 28 de agosto de 2026.

- **Causa:** toque longo abria diretamente `ConfiguracaoScreen`; reset ficava exposto e não existia uma saída administrativa explícita.
- **Correção:** `AdminAuthScreen` obrigatória, senha central por ambiente sem fallback, autorização efêmera, guardas nas ações e opção `Fechar Terminal`.
- **Hardening:** `Esc` é consumido, `closeEvent` comum é ignorado e o shutdown autorizado para serviços cooperativamente sem resetar compra ou assumir cancelamento financeiro.
- **Validação:** senha correta/incorreta, cancelar, reautenticação, reset guardado, compra/pagamento ativos, encerramento e ausência de segredo em logs.

## BUG-037 — Resultado de pagamento pequeno e reset aprovado prematuro

**Status:** corrigido em 28 de agosto de 2026.

- **Causa:** atenção, falha e sucesso eram cards no fundo neutro; `ConfirmacaoScreen` apagava a compra automaticamente em cinco segundos.
- **Impacto:** estados pouco visíveis no totem e impossibilidade de manter referências para CPF/comprovante.
- **Correção:** estados semânticos fullscreen, SVG branco reutilizável, motivos humanos, retry sem cobrança automática e reset aprovado somente em `FINALIZAR`.
- **Limite registrado:** integrações pós-compra não existem no backend e não são simuladas pela UI.

## BUG-038 — Carrinho parecia lista e perdia legibilidade no display de 7 polegadas

**Status:** corrigido em 28 de agosto de 2026.

- duas colunas largas foram substituídas por cálculo real do viewport e três colunas em `1024×600`;
- cards usam `292×224`, grid com altura por linhas e scroll somente vertical;
- footer fixo, tipografia e contraste do carrinho/confirmação foram ampliados;
- teste e render Qt offscreen validam seis produtos na resolução física.

## BUG-040 — Rotação de boot dependia de saída e orientação hardcoded

**Status:** corrigido em 28 de agosto de 2026.

- **Causa:** `start.sh` aplicava uma saída/transform específicos da máquina de desenvolvimento, apesar da documentação declarar detecção.
- **Impacto:** outro Raspberry/monitor podia não girar, iniciar na orientação errada ou exigir edição manual do script.
- **Correção:** `DisplayService` detecta backend e saída ativa, aplica orientação sem shell, persiste a escolha semântica e o `start.sh` reaplica o arquivo salvo com fallback não bloqueante.
- **Validação:** testes cobrem saída `HDMI-A-2` apenas como fixture, ausência de hardcode no script, Wayland sem ferramenta, X11, timeout e reboot simulado.

## BUG-030 — Sync somente no startup e paths relativos

**Status:** corrigido em 24 de agosto de 2026.

- **Causa:** thread executava uma única requisição; `.env`, SQLite, identidade e cursor dependiam do diretório corrente.
- **Impacto:** catálogo não mudava durante sessões longas e uma inicialização externa à raiz podia ler/escrever outro estado.
- **Correção:** paths absolutos centralizados, execução imediata + periódica a cada 300 s, snapshot validado/transacional, UPSERT, desativação de ausentes e cursor pós-commit.

## BUG-031 — Heartbeat opaco, sem confirmação do backend

**Status:** corrigido em 24 de agosto de 2026.

- **Causa:** cliente apenas chamava `send`, não recebia ACK e não possuía parada cooperativa.
- **Impacto:** não era possível afirmar se `lastPing` havia sido persistido; falhas apareciam apenas como reconnect genérico.
- **Correção:** ACK pós-`saveAndFlush` com UUID/status/`lastPing`, validação no cliente, constantes de intervalo/retry/timeout e lifecycle da aplicação.
- **Validação:** ACK real e consulta direta ao MySQL confirmaram avanço de `last_ping`.

## BUG-032 — Notificação de produto podia ser perdida ou tratada como pagamento

**Status:** corrigido em 24 de agosto de 2026.

- **Causa:** o listener encaminhava todo JSON ao fluxo financeiro e não solicitava catálogo ao reconectar; ignorar evento durante uma sync também criaria uma janela de perda.
- **Impacto:** `PRODUCT_SYNC_REQUIRED` podia atingir lógica de pagamento ou o catálogo ficar desatualizado até reiniciar.
- **Correção:** dispatcher por `type`, sync em conexão/reconexão e coordenador serial com `sync_in_progress + sync_pending`.
- **Validação:** testes separam eventos de pagamento/produto, simulam reconexão e coalescem três avisos numa única execução pendente sem concorrência.

## BUG-033 — Cursor avançava com cache local nunca inicializado

**Status:** corrigido em 24 de agosto de 2026.

- **Causa:** `last_sync.txt` era considerado suficiente; SQLite vazio não possuía marcador de FULL concluído.
- **Cenário real:** zero produtos locais + cursor válido resultavam em `fullSync=false, changes=[]` e novo avanço do cursor.
- **Correção:** `catalog_sync_state` transacional, contagem esperada e FULL obrigatório para estado ausente/inconsistente; remoção do `print(response.json())` solto.
- **Validação:** FULL real sem cursor retornou zero porque o condomínio possui zero associações, marcou o cache como válido e permitiu incremental vazio subsequente.
