# Bugs e riscos do Terminal Python

Voltar para [o índice](00-index.md).

Critério: **confirmado** quando o caminho executável ou contrato prova o comportamento; **potencial** quando depende de timing, ambiente ou dados externos. Linhas referem-se ao worktree auditado.

## BUG-001 — Crédito/débito concluem sem backend

**Status:** corrigido — revisão formal em 17 de outubro de 2026. `telas/pagamento.py` não existe mais; o método (débito/crédito/PIX) é escolhido na Point e o único caminho de sucesso é `PagamentoScreen._handle_payment_approved`, alcançado somente quando `CompraSession.apply_status` recebe status definitivo do backend para a Order ativa.

- **Severidade:** crítica
- **Tipo:** confirmado
- **Arquivo/função:** `telas/pagamento.py`, `PagamentoScreen.finalizar_venda`
- **Cenário:** usuário escolhe crédito ou débito.
- **Impacto:** UI volta ao início sem Carrinho, Order, Pagamento ou cobrança Point; estado local fica parcialmente sujo.
- **Correção recomendada:** conectar ao checkout Point e só finalizar após estado definitivo do backend.

## BUG-002 — Qualquer mensagem WebSocket aprova a compra

**Status:** corrigido — revisão formal em 17 de outubro de 2026. `PaymentListener.route_message` só encaminha `type=PAYMENT_STATUS`; `PagamentoScreen.processar_evento` exige `terminalId` igual ao local e `CompraSession.apply_status` exige `orderId` da sessão, `paymentAttemptId` compatível e status em `APPROVED/PAID/PROCESSED`. Testes: `test_event_from_other_terminal_never_approves`, `test_event_without_definitive_status_never_approves`.

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

**Status:** corrigido — revisão formal em 17 de outubro de 2026. O cliente usa `POST /pagamento/terminal/{cartId}` (`PurchaseApi`), consulta `GET /order/{orderId}/status` e `GET /pagamento/terminal/{terminalId}/ativo`; todos existem no `PagamentoController`/`OrderController` atuais (ver [[auditoria-2026-10]]).

- **Severidade:** crítica
- **Tipo:** confirmado
- **Arquivo/função:** `telas/pagamento.py:275-293`
- **Cenário:** botão PIX tenta `GET /pagamento/terminal?carrinho_id=` e espera QR.
- **Impacto:** fluxo falha contra backend atual; não inicia Point corretamente.
- **Correção recomendada:** contrato coordenado específico para início Point.

## BUG-005 — Evento de pagamento não é publicado pelo backend ativo

**Status:** corrigido — revisão formal em 17 de outubro de 2026. O backend (`07e9d4a`) publica `PaymentEvent` em `PaymentStateTransitionService` e `PaymentWebSocketHandler.sendToTerminal` envia com `@TransactionalEventListener(AFTER_COMMIT)`. O terminal mantém polling HTTP e reconciliação como rede de segurança (BUG-015).

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

**Status:** corrigido — revisão formal em 17 de outubro de 2026. `finalizar_venda` não existe mais; `MainWindow.reset_compra` chama `TerminalScreen.liberar_tela`, que recria `Carrinho()` e limpa `linhas`, e só ocorre após estado terminal ou sem pendência remota.

- **Severidade:** alta
- **Tipo:** confirmado
- **Arquivo/função:** `PagamentoScreen.finalizar_venda`
- **Cenário:** remove widgets e zera labels, sem limpar `carrinho.items`/`linhas`.
- **Impacto:** próxima compra pode reutilizar itens invisíveis; `linhas` ainda bloqueia scans como existentes.
- **Correção recomendada:** usar um único reset somente após resultado definitivo.

## BUG-010 — POST de carrinho pode duplicar compras

**Status:** corrigido — revisão formal em 17 de outubro de 2026. `CompraSession.begin_payment` recusa tentativa concorrente; o `cartId` é gravado em checkpoint SQLite antes do pagamento, retentativas usam `PUT /carrinho/{id}`, o backend responde `PAYMENT_ALREADY_ACTIVE` e o terminal adota a cobrança existente em vez de criar outra.

- **Severidade:** alta
- **Tipo:** potencial
- **Arquivo/função:** `PagamentoScreen.ir_para_pix`; `AppPaymentScreen.gerar_checkout`
- **Cenário:** clique duplo, timeout ou retry após resposta perdida.
- **Impacto:** múltiplos carrinhos e potencialmente Orders/cobranças duplicadas.
- **Correção recomendada:** bloquear tentativa concorrente, idempotência e persistência de IDs.

## BUG-011 — Sem timeout nas chamadas de compra

**Status:** corrigido — revisão formal em 17 de outubro de 2026. Todo HTTP de compra passa por `BackendClient`/`PurchaseApi` com timeout (padrão 10 s) e `requests.Timeout` vira `PurchaseApiError` tipado.

- **Severidade:** alta
- **Tipo:** confirmado
- **Arquivo/função:** `pagamento.py`; `app_payment_screen.py`; `Produtos.get_produtos_api`
- **Cenário:** backend não responde.
- **Impacto:** UI congela no PIX ou thread fica presa indefinidamente.
- **Correção recomendada:** connect/read timeouts e erros tipados centralizados.

## BUG-012 — HTTP é executado na UI thread

**Status:** corrigido — revisão formal em 17 de outubro de 2026. Ativação, Point, status, retomada, comprovante e checkout por app rodam em `QThread` com signals e guarda `isRunning()`.

- **Severidade:** alta
- **Tipo:** confirmado
- **Arquivo/função:** `CadastroTerminalScreen.verificar_ativacao`; `PagamentoScreen.ir_para_pix`
- **Cenário:** rede lenta a cada timer/click.
- **Impacto:** interface congela por até 5 s na ativação ou indefinidamente no pagamento.
- **Correção recomendada:** worker Qt com signals e guarda contra sobreposição.

## BUG-013 — Thread de checkout altera widgets Qt diretamente

**Status:** corrigido — revisão formal em 17 de outubro de 2026. `AppCheckoutWorker` só emite `succeeded/failed`; `AppPaymentScreen` atualiza widgets na UI thread.

- **Severidade:** alta
- **Tipo:** potencial/race confirmada no desenho
- **Arquivo/função:** `AppPaymentScreen.gerar_checkout:169-172`
- **Cenário:** thread daemon chama `hide`, `setPixmap`, `setText`.
- **Impacto:** comportamento indefinido, crash ou corrupção da UI.
- **Correção recomendada:** emitir signals para a UI thread.

## BUG-014 — Evento tardio pode liberar nova compra

**Status:** corrigido — revisão formal em 17 de outubro de 2026. `reset` zera `order_id`/`payment_attempt_id` e cada compra recebe Order própria; eventos com `orderId` ou tentativa divergentes retornam `IGNORED`. Testes: `test_late_event_from_previous_purchase_does_not_release_new_one`, `test_event_from_old_payment_attempt_is_ignored`.

- **Severidade:** crítica
- **Tipo:** potencial
- **Arquivo/função:** `PaymentListener`; `TerminalScreen.pagamento_aprovado`
- **Cenário:** compra A expira/reset; compra B começa; evento de A chega.
- **Impacto:** B é marcada como sucesso/liberada.
- **Correção recomendada:** geração/tentativa persistida e correlação estrita por Order.

## BUG-015 — Aprovação durante desconexão não é recuperada

**Status:** corrigido para queda/reconexão do backend e perda de WebSocket; a recuperação após reboot físico foi implementada em 3 de outubro de 2026 pela MEL-017 (tabela `active_payment`) — revisão de status em 25 de novembro de 2026.

- **Severidade:** alta
- **Tipo:** corrigido
- **Arquivo/função:** `PaymentListener.run`; persistência local
- **Cenário:** webhook aprova enquanto socket está offline.
- **Impacto:** backend pago e terminal exibindo espera/erro.
- **Correção:** conexão/reconexão abre “Verificando pagamento”, consulta o endpoint correlacionado e mantém polling HTTP controlado a cada 10 segundos. O backend reconcilia com a Order Point antes de responder.
- **Validação:** testes cobrem `APPROVED`, `WAITING_PAYMENT` e `REJECTED` recebidos pela consulta pós-reconexão.

## BUG-016 — Listener pode não encerrar

**Status:** corrigido — revisão formal em 17 de outubro de 2026. `recv` tem timeout de 5 s, `PaymentListener.stop` fecha o socket e espera dentro do orçamento de `shutdown_budget` (BUG-047).

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

**Status:** corrigido — revisão formal em 17 de outubro de 2026. O scanner cria itens com `received_weight=None`; `Carrinho.total` e `Carrinho.__str__` passaram a usar `Item.subtotal()`, igual à linha, e o valor cobrado continua sendo o do backend. Teste: `test_cart_total_matches_line_subtotal_for_weighted_item`.

- **Severidade:** alta
- **Tipo:** confirmado
- **Arquivo/função:** `Item.subtotal`; `Carrinho.total`; `TerminalScreen`
- **Cenário:** todo item recebe peso 1.0; linha pode usar peso e total usa quantidade.
- **Impacto:** valores visuais divergentes e payload sem semântica correta para pesáveis.
- **Correção recomendada:** regra por unidade de medida validada no backend.

## BUG-019 — PIX pode ser confirmado manualmente

**Status:** corrigido — revisão formal em 17 de outubro de 2026. `PixScreen` foi removida; não existe botão de confirmação financeira manual. A tela de pagamento apenas aguarda o backend ou solicita cancelamento via Spring.

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
- **Correção aplicada:** `MainWindow` inicia/para `InternetMonitor` contra `API_URL`; `OfflineOverlay` abre o mesmo fluxo administrativo autenticado de Wi-Fi e é suspenso somente durante a manutenção. Socket, sync e heartbeat continuam donos da própria reconexão.

## BUG-023 — Logs expõem dados e não têm estrutura

**Status:** corrigido — revisão formal em 17 de outubro de 2026. `PixScreen` foi removida; o fluxo ativo usa `logging` com `orderId`/estágio, sem copia-e-cola nem credenciais. Restam `print` apenas em código morto (`Produtos.get_produtos_api`, `login.py`), rastreado em BUG-052.

- **Severidade:** alta
- **Tipo:** confirmado
- **Arquivo/função:** `PixScreen` imprime copia-e-cola; vários `print`/`traceback.print_exc`
- **Cenário:** PIX legado ou falha HTTP.
- **Impacto:** dado de pagamento e detalhes técnicos em console; baixa rastreabilidade.
- **Correção recomendada:** logging estruturado/sanitizado com terminal, carrinho e Order.

## BUG-024 — Segredo de configuração local e URL hardcoded

**Status:** corrigido — revisão formal em 17 de outubro de 2026. Não há URL hardcoded em `src/`; endpoints vêm de `config/settings.py`/`/etc/app247/terminal.env`, `.env` está no `.gitignore` e só exemplos são versionados.

- **Severidade:** média
- **Tipo:** confirmado/potencial
- **Arquivo/função:** `.env`; `PagamentoScreen.__init__:26`
- **Cenário:** arquivo local contém endpoints; classe também contém URL ngrok, embora não a use nas requisições atuais.
- **Impacto:** configuração duplicada, túnel legado e risco de versionamento indevido.
- **Correção recomendada:** uma configuração validada; manter `.env` fora do versionamento e nunca incluir tokens.

## BUG-025 — Código morto contém falhas de runtime

**Status:** aberto — revisão formal em 17 de outubro de 2026. `parentrminal` não existe mais, mas `TecladoScreen` ainda cancela para `parent.login` (inexistente) e `LoginScreen` usa `/usuarios/anonimo`. Inacessível hoje porque `LoginScreen` está comentada em `application.py`; tratado junto com BUG-052.

- **Severidade:** baixa enquanto inacessível
- **Tipo:** confirmado
- **Arquivo/função:** `TecladoScreen.finalizar` (`parentrminal`); cancelamento usa `parent.login`, hoje `None`; `LoginScreen` usa endpoint ausente.
- **Cenário:** reativação futura dessas telas.
- **Impacto:** `AttributeError`/fluxo quebrado.
- **Correção recomendada:** só revisar/remover em etapa separada após confirmar intenção.

## BUG-026 — Socket permite personificação/substituição de terminal

**Status:** corrigido — revisão formal em 17 de outubro de 2026. `/terminal-socket` e `/payment-socket/{id}` enviam a credencial individual (`terminal_auth_headers`) e o `TerminalHandshakeInterceptor` do backend a valida contra o `terminalId` do path.

- **Severidade:** alta
- **Tipo:** confirmado no desenho
- **Arquivo/função:** URLs e handlers nativos cliente/backend
- **Cenário:** cliente informa UUID de outro terminal.
- **Impacto:** heartbeat falso ou ocupação do canal de pagamento de outro equipamento.
- **Correção recomendada:** autenticação de provisionamento e vínculo no handshake.

## BUG-027 — Erros relevantes são engolidos ou exibidos ao cliente

**Status:** corrigido — revisão formal em 17 de outubro de 2026. Telas de compra exibem somente textos fixos ou mapeados (`DOMAIN_MESSAGES`, mensagens de cliente/QR/comprovante); detalhes vão para o log. O único `except:` restante está em `login.py` (código morto, BUG-052).

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
- **Correção aplicada:** todas as telas foram migradas ao tema central, folhas QSS duplicadas removidas e geometria portrait validada por testes Qt offscreen.

## BUG-034 — Compra iniciava Point sem resumo explícito

**Status:** corrigido em 27 de agosto de 2026.

- `PAGAR AGORA` iniciava o worker diretamente e `PAGAR NO APP` competia na mesma tela.
- Agora há `FINALIZAR -> CONFIRME SUA COMPRA -> CONFIRMAR E PAGAR`.
- A confirmação lê a mesma instância de `Carrinho`; voltar preserva os produtos e o botão é desabilitado antes do worker.

## BUG-035 — Navegação quebrada no teclado legado

**Status:** corrigido em 27 de agosto de 2026; rota permanece inativa.

O atributo inexistente `parentrminal` foi corrigido para `parent.terminal`. O endpoint legado de login não foi reativado.

## BUG-036 — Administração sem senha e ausência de saída segura

**Status:** corrigido em 28 de agosto de 2026.

O toque longo abria diretamente as configurações. Agora uma senha de ambiente, mascarada e nunca logada, protege o menu inteiro por acesso. A autorização expira ao sair. `Fechar Terminal` executa confirmação contextual e shutdown cooperativo; `Esc`/close comum não encerram o quiosque.

## BUG-037 — Estados financeiros pequenos e reset aprovado prematuro

**Status:** corrigido em 28 de agosto de 2026.

Falha, instrução e sucesso eram cards e a aprovação apagava a compra após cinco segundos. Agora os estados são fullscreen, usam SVG branco/ícone + texto + cor, retry não cria cobrança e `FINALIZAR` é o único reset normal. WhatsApp/e-mail usam o contrato real do backend; CPF continua explicitamente pendente.

## BUG-041 — Ações pós-compra eram placeholders após aprovação

**Status:** corrigido em 13 de setembro de 2026.

- **Causa:** `ConfirmacaoScreen` conectava CPF, e-mail e WhatsApp a `_show_unavailable`; não havia método HTTP nem worker de comprovante no cliente.
- **Impacto:** mesmo com Order aprovada preservada, o cliente não conseguia solicitar o envio já suportado pelo Spring.
- **Correção:** `POST /comprovante` foi integrado em `ReceiptSendWorker`; a tela conserva `orderId`, usa teclados touch reutilizáveis, valida entrada, impede clique duplo e pausa o timeout durante input/request.
- **Segurança:** ações só habilitam em `APPROVED/SUCCESS`; falha de entrega mantém pagamento aprovado. CPF continua desabilitado pela ausência de contrato.
- **Validação:** suíte completa com 168 testes, incluindo contrato, reconciliação, falha, clique repetido, timers e layout `1024×600`.

## BUG-038 — Carrinho parecia lista e perdia legibilidade no display de 7 polegadas

**Status:** corrigido em 28 de agosto de 2026.

- **Causa:** o `resizeEvent` limitava `TerminalScreen` a duas colunas em qualquer largura a partir de 800 px; os cards expandiam e aparentavam linhas largas. O conteúdo do grid também não forçava a altura total das linhas no `QScrollArea`.
- **Impacto:** baixo aproveitamento de `1024×600`, tipografia percebida como pequena e risco de sobreposição visual ao formar uma segunda linha.
- **Correção:** cálculo pelo viewport, 3 colunas em 1024 px, cards `292×224`, altura mínima do conteúdo por quantidade de linhas, scroll apenas vertical, footer horizontal fixo e tipografia/contraste ampliados no carrinho e confirmação.
- **Validação:** teste Qt automatizado com quarta mercadoria em `(row=1, column=0)` e render offscreen com seis mercadorias em `1024×600`.

## BUG-039 — Cronômetro chegava a `00:00` sem lifecycle central de expiração

**Status:** corrigido em 28 de agosto de 2026.

- **Severidade:** crítica.
- **Causa:** `CompraSession._tick` atualizava `remaining_changed` e emitia `expired`, porém `main.py` conectava o sinal diretamente a `PagamentoScreen.tratar_timeout_global`. Não existia um handler de lifecycle no controlador nem uma flag explícita de emissão única/atividade; lista, confirmação, scanner e callbacks tardios ficavam fora de uma política central verificável.
- **Impacto:** o display podia permanecer em `00:00` com a compra antiga utilizável ou dependente do comportamento de uma tela que não era a atual.
- **Correção:** `MainWindow._checkout_session_expired` bloqueia interações, valida a geração e reutiliza `reset_compra` quando não há pendência remota. Tentativas/IDs remotos seguem reconciliação segura. `CompraSession` para o timer, marca `active=false` e protege a emissão com `_expired_emitted`.
- **Proteções adicionais:** status exige `orderId`; `paymentId` só é aplicado depois da correlação; status/resume workers capturam Order/tentativa/carrinho; reset desconecta callbacks locais e restaura deadline/flag. Uma interrupção solicitada não publica sucesso nem falha tardia.
- **Validação:** testes com duração injetada de dois segundos cobrem o `QTimer` real chegando a zero, lista, confirmação, scanner bloqueado, nova geração, emissão única, loading Point sem IDs e falha definitiva após timeout, sem cobrança real.

## BUG-040 — Rotação de boot dependia de saída e orientação hardcoded

**Status:** corrigido em 28 de agosto de 2026.

- **Causa:** `start.sh` aplicava uma saída/transform específicos, divergindo da documentação de detecção.
- **Impacto:** outro Raspberry/monitor podia não girar, iniciar errado ou exigir edição manual.
- **Correção:** `DisplayService` detecta backend/saída, aplica orientação por argv, persiste a escolha e o `start.sh` reaplica o arquivo salvo sem bloquear o boot em caso de erro.
- **Validação:** output aparece somente em fixture de teste; Wayland sem ferramenta, X11, timeout e reaplicação salva também são cobertos.

## BUG-041 — Point ficava em loading depois do aceite remoto e cancelamento podia liberar estado cedo

**Status:** corrigido em 14 de setembro de 2026.

- **Causa:** `_apply_status` mostrava a tela laranja somente para `AT_TERMINAL/ACTION_REQUIRED`; `PENDING`, `CREATED`, `WAITING_PAYMENT` e `PROCESSING` voltavam ao loading, embora o worker de criação já tivesse terminado. Não existia endpoint de cancelamento integral nem intenção persistida.
- **Impacto:** a instrução para pressionar verde chegava tarde, cancelamento de método podia parecer cancelamento da compra e timeout não possuía encerramento remoto confirmado.
- **Correção:** todos os estados não terminais após `orderId` usam a tela laranja; cancelamento passa pelo Spring, persiste intenção/idempotência, reconcilia e só libera Home em estado terminal. Home/startup/reconnect retomam a pendência.
- **Validação:** testes cobrem aceite `CREATED`, `PROCESSING`, timeout de cancelamento, cancelamento confirmado, aprovação concorrente, restart e bloqueio de ressubmissão após intenção de cancelar.

## BUG-030 — Sync somente no startup e paths relativos

**Status:** corrigido em 24 de agosto de 2026.

- **Causa:** thread executava uma única requisição; `.env`, SQLite, identidade e cursor dependiam do diretório corrente.
- **Impacto:** catálogo não mudava durante sessões longas e uma inicialização externa à raiz podia ler/escrever outro estado.
- **Correção:** paths absolutos centralizados, execução imediata + periódica a cada 300 s, snapshot validado/transacional, UPSERT, desativação de ausentes e cursor pós-commit.

## BUG-042 — Release preparada não podia ser ativada e serviço ficava manual

**Status:** corrigido em 3 de outubro de 2026.

- **Causa:** a segunda chamada do instalador recusava a release existente antes
  de processar `--activate`; a unidade systemd era apenas um exemplo e nunca era
  instalada ou habilitada pelo fluxo.
- **Impacto:** o procedimento documentado falhava e o binário podia ser iniciado
  fora do systemd, sem `/etc/app247/terminal.env`, exibindo “Servidor não
  configurado”.
- **Correção:** ativação idempotente da release preparada, diagnóstico
  bloqueante, rollback do symlink, geração da unidade e gerenciamento explícito
  do serviço.
- **Validação:** teste isolado cobre preparar, ativar, criar symlink e renderizar
  a unidade sem chamar o systemd real.

## BUG-043 — Instalador distribuído dependia do checkout fonte

**Status:** corrigido em 4 de outubro de 2026.

- **Causa:** `scripts/install.sh` derivava `dist/`, template e unit exclusivamente
  a partir da raiz do repositório e exigia `APP247_INSTALL_VERSION`.
- **Impacto:** um `.tar.gz` entregue a um Raspberry novo não podia ser instalado
  pelos comandos standalone documentados.
- **Correção:** detecção explícita por `SCRIPT_DIR`, leitura de `VERSION`, fontes
  adjacentes no pacote, trust anchor idempotente e comparação integral de uma
  release já existente.
- **Validação:** o verificador extrai cada pacote em temporário e executa a fase
  de preparação com todos os destinos redirecionados para um sandbox.

## BUG-044 — GUI era iniciada fora da sessão gráfica e o estado local não respeitava o usuário da tela

**Status:** corrigido em 4 de outubro de 2026; validação física em Raspberry Pi permanece pendente.

- **Causa:** a unit de sistema iniciava PyQt como usuário de serviço, sem o
  socket Wayland/DBus da sessão gráfica. Além disso, `/var/lib/app247` e a
  credencial individual eram provisionados para o usuário de serviço, embora a
  GUI passe a executar como o usuário gráfico.
- **Impacto:** Qt falhava ao conectar ao display, o usuário gráfico recebia
  `PermissionError` ao abrir estado local e a credencial segura `0600` era
  recusada por não pertencer ao processo que a consumia. `Restart=always`
  também reabria o programa após o fechamento administrativo.
- **Correção:** o instalador resolve o usuário gráfico, instala/habilita uma
  unit `systemd --user` e usa launcher que descobre Wayland/X11 de forma
  verificada. Dados compartilhados usam grupo `app247`, SGID `2770` e arquivos
  `0660`; a credencial continua `0600` e é migrada ao usuário gráfico na
  ativação. O encerramento administrativo para recursos cooperativamente e
  normaliza o retorno para `0`; a unit usa `Restart=on-failure`, limite de cinco
  partidas/minuto e ignora apenas falha não crítica de orientação.
- **Hardening:** o instalador rejeita links simbólicos no diretório de dados
  antes de executar `chown`/`chmod` como root, prevenindo alteração de arquivos
  externos por uma atualização.
- **Validação:** testes automatizados cobrem unit, launcher, lock, argumentos,
  Wayland, permissões, credencial e lifecycle CLI; build e pacote standalone
  assinado foram verificados em ambiente amd64. Falta teste físico Wayland no
  Raspberry.

## BUG-045 — Corrupção recorrente do sistema no Raspberry Pi com SSD USB

**Status:** em investigação; nenhuma causa confirmada. Evidências coletadas via SSH em 16 de outubro de 2026.

- **Severidade:** alta (terminal indisponível até reinstalação)
- **Tipo:** potencial — ambiente/hardware, não atribuído ao código do Terminal.
- **Ambiente verificado:** Raspberry Pi 4 Model B Rev 1.5, Raspbian 13 (trixie), kernel `6.18.50+rpt-rpi-v8`, bootloader de 17/05/2026 atualizado. SSD 128 GB (`/dev/sda`, 119,2 GiB) em ponte USB-SATA **Initio `13fd:5917`**, driver `uas`, USB 3 (5 Gbit/s); `sda1` vfat em `/boot/firmware`, `sda2` ext4 `rw,noatime` em `/`; swap só em `zram0` 1,8 GB. Filesystem criado em 14/09/2026 (imagem regravada), 7 montagens, estado `clean`, 10 GB escritos. App instalado: `/opt/app247/current -> releases/1.0.1` (não 1.0.2).

### Evidências (16/10/2026, boot das 14:28, ~1h45 de uptime)

| Evidência | Resultado | Interpretação |
|---|---|---|
| `journalctl -k -b 0` | `EXT4-fs (sda2): orphan cleanup on readonly fs` | o boot anterior **não foi desmontado corretamente** (queda de energia, travamento ou desligamento forçado) |
| `journalctl -b 0 -p err` | `usb usb2-port2: Cannot enable. Maybe the USB cable is bad?` (2×) — porta onde está o SSD | falha de enumeração do SSD no boot; compatível com cabo, case, porta ou alimentação marginal. **Indício mais forte até agora.** |
| `vcgencmd get_throttled` | `0x0` | nenhuma subtensão/throttling **desde este boot** (não cobre boots anteriores) |
| `vcgencmd measure_temp` | 74–76 °C com load 0,15 e ARM a 600 MHz | temperatura alta em repouso; perto do limite de throttling (80 °C). Risco, não causa comprovada de corrupção. |
| `sd 0:0:0:0` | `Write cache: enabled ... doesn't support DPO or FUA` | queda de energia pode perder escritas ainda no cache da ponte/SSD |
| journald | `Storage=volatile` | **logs de boots anteriores não existem**; por isso não há histórico das corrupções passadas |
| relógio | boot iniciou com hora 05/10 00:26 e só sincronizou via NTP 45 s depois | sem RTC; timestamps iniciais do boot são falsos |
| `smartctl` | não instalado | SMART ainda não lido (a ponte Initio pode exigir `-d sat`) |
| `app247-terminal.service` | 6 falhas de start entre 14:29 e 14:37, ativo desde 14:42 | observação separada; causa não investigada (journal do usuário indisponível) |

- **Observação isolada:** em desligamento anterior pela touchscreen apareceu `Shut down request (2)` com cursor piscando, sem teclado; depois iniciou normalmente. Sem logs persistentes, não é possível correlacionar.
- **Hipóteses ainda abertas:** alimentação insuficiente (fonte/cabo de energia), cabo/case USB-SATA, temperatura, desligamento sem `poweroff`. A rede ([[wifi]]) não explica corrupção de disco.
- **Procedimento operacional:** desligar somente com `sudo poweroff` e aguardar o LED verde parar antes de remover a alimentação.
- **Próximos passos dependentes de autorização:** journal persistente (`Storage=persistent`) para capturar a próxima ocorrência; instalar `smartmontools` e ler SMART; testar outro cabo/case/porta USB 3 e fonte oficial 5,1 V/3 A; dissipador/ventoinha. Não reinstalar, não alterar `cmdline.txt`/quirks USB/kernel sem nova evidência.

### Ocorrência de 24/11/2026 — boot preso no bootloader (USB não inicializa)

| Evidência | Resultado | Interpretação |
|---|---|---|
| tela do bootloader (`order f41`, `restart 35/-1`) | SD: `Failed to open device: 'sdcard' (cmd 37a0010 status 1fff0001)`; USB-MSD: `PCIe timeout: 0x0000000f` e `USB xHC init failed` | o bootloader não conseguiu subir o PCIe/VL805, por isso **nunca leu o SSD**; ficou reiniciando em loop |
| sem nada nas USB e com fonte trocada | mesma tela | não era periférico nem a fonte usada naquele teste |
| SSD lido no PC | partições `bootfs`/`rootfs` íntegras (imagem recém-gravada, ainda sem expandir) | a imagem não era a causa |
| após regravar a imagem | boot normal, primeiro boot concluído (`cloud-init: done`) | a falha **não se repetiu**; causa da falha do PCIe no bootloader segue sem confirmação (intermitente) |
| `journalctl -k -b 0` | `brcm-pcie: link up, 5.0 GT/s`, VL805 `1106:3483`, sem `Cannot enable`/erros USB | USB normal neste boot |
| `vcgencmd` | `throttled=0x0`, 57 °C | sem subtensão; temperatura bem menor que em 16/10 |
| `rpi-eeprom-update` | bootloader 17/05/2026 → **23/09/2026 preparado** (`pieeprom.upd`), VL805 `000138c0` já atual | aplicado no próximo reboot |
| journald | `/etc/systemd/journald.conf.d/90-persistent.conf` (`Storage=persistent`, `SystemMaxUse=200M`) | precisa ser `90-` para vencer `/usr/lib/.../40-rpi-volatile-storage.conf`; logs agora em `/var/log/journal` |

- **Reboot de 21:32 (`systemctl reboot`, aplica o bootloader):** voltou em ~40 s; `vcgencmd bootloader_version` = `2026/09/23`, `throttled=0x0`, 60 °C. Mas o kernel registrou de novo `usb usb2-port1: Cannot enable. Maybe the USB cable is bad?` (2×) seguido de `attempt power cycle` — só então o SSD enumerou (SuperSpeed, `uas`). Também `EXT4-fs (sda2): orphan cleanup on readonly fs` mesmo após desligamento ordenado (o journal do boot `-1` termina normalmente em `systemd-shutdown`, sem erro). A falha de enumeração da porta do SSD é **reproduzível no boot**; reforça cabo/case USB-SATA Initio, porta ou alimentação, e explica o `USB xHC`/`PCIe` instável do bootloader como hipótese relacionada, não confirmada.
- Sistema reinstalado (imagem limpa, usuário `jefiro`, Wi-Fi `BR`); app Terminal **ainda não instalado**.
- `mmc1: Controller never released inhibit bit(s)` aparece com o slot SD vazio; sem impacto ao bootar pelo SSD.

### Ocorrência de 24–25/11/2026 — app fecha sozinho, atalho não abre, SSH recusa

Com o app 1.0.6 instalado e operando, o terminal parou na noite de 24/11. No dia 25 o operador viu o app fechado, o atalho da área de trabalho não abria e o SSH respondia `kex_exchange_identification: Connection reset by peer`, mas o Pi ainda respondia ao ping.

| Evidência | Resultado | Interpretação |
|---|---|---|
| `journalctl -b -1` (journal persistente) | app normal até a última linha: heartbeat a cada 10 s, sync e telemetria com 202. **Último registro: 24/11 23:26:04.** Sem erro do app, sem erro do kernel, sem `systemd-shutdown` | os registros param de uma vez, sem desligamento ordenado. É o padrão de quando o root (`/dev/sda2`) some: o kernel não consegue mais gravar o próprio erro |
| sintomas sem SSH | ping ok, `sshd` aceita o TCP e reseta antes do banner; app fechado; atalho sem efeito | processos que já estavam na RAM seguem vivos, mas nada consegue carregar binários ou bibliotecas do disco. Bate com o SSD desconectado |
| 1º boot no dia 25 (tela do bootloader 2026/09/23) | `PCIe timeout: 0x0000008f`, `USB xHC init failed` em loop | mesma falha do bootloader do dia 24; o VL805 não inicializou |
| 2º boot no dia 25 | o controlador inicializa (`USB2 root HUB port 1 init`); `xHC-CMD err: 4 type: 11` na porta 4 em full-speed, que é o touch da tela (`0484:5750` MPI7002) e não o SSD; depois o boot segue normal | a falha do PCIe/VL805 no bootloader é **intermitente** |
| após bootar (`lsusb -t`, `vcgencmd`) | SSD `13fd:5917` em **480M (USB 2)** com `uas`, mesmo ligado em porta azul; `throttled=0x0` | o bridge Initio não negociou SuperSpeed (em 24/11 negociou após `power cycle`); não houve subtensão neste boot. O app 1.0.6 voltou ativo sozinho |

- **Conclusão:** quedas do app sem rastro no log, mais a falha intermitente do USB no bootloader e no kernel, apontam para o **case/bridge USB-SATA Initio `13fd:5917`** (ou o cabo dele) como causa principal. Não foi possível provar pelo log, porque a queda impede a gravação. Não é defeito do app.
- **Ação recomendada:** trocar o case por um bridge ASMedia (ASM1153E/ASM235CM) ou JMicron (JMS578/JMS583); como alternativa, usar hub USB com fonte própria. Para registrar a próxima queda mesmo sem disco, considerar log remoto (`netconsole` ou `systemd-journal-remote`), o que exige autorização para alterar o Pi.

## BUG-046 — `terminal.json` vazio ou corrompido derruba o Terminal antes da UI

**Status:** corrigido em 17 de outubro de 2026 (reproduzido antes da correção); validação no Raspberry pendente.

- **Correção aplicada:** `Terminal.save` faz `fsync` do arquivo temporário e do diretório; `Terminal.load` lança `TerminalConfigCorrupted`; no startup `Terminal.quarantine_if_corrupted` preserva o arquivo como `terminal.json.corrupt-<data>` (nunca apaga) e o Terminal volta à ativação por serial ou à recuperação de pagamento pendente; heartbeat, sync, telemetria e lifecycle usam `Terminal.load_or_none`; credencial ilegível/insegura vira "indisponível" em `MainWindow` e na tela/thread de ativação, sem abortar o PyQt. Testes: `tests/test_terminal_config_recovery.py`.

- **Severidade:** alta
- **Tipo:** confirmado (reproduzido com `terminal.json` vazio em diretório isolado)
- **Arquivo/função:** `main.py:_run_gui` chama `Terminal.load()` sem tratamento; `Terminal.load` propaga `JSONDecodeError`. Mesmo padrão em `TerminalSocket._load_active_terminal` (fora do `try`, mata a thread de heartbeat), `PaymentListener.__init__`, `SyncService.sincronizar_produtos` e `MainWindow` (`TerminalCredentialStore().load()` pode lançar `TerminalCredentialMissing` em arquivo truncado).
- **Cenário:** desligamento sujo durante `Terminal.save()` — que usa tmp + `replace` **sem `fsync`** — ou corrupção do disco (ver BUG-045).
- **Impacto:** processo sai com traceback antes de qualquer tela; `Restart=on-failure` entra em loop até o limite de partidas e o terminal fica sem UI e sem mensagem ao operador.
- **Correção recomendada:** `fsync` do arquivo e do diretório em `Terminal.save`; tratar JSON inválido como estado de recuperação explícito (tela administrativa, sem apagar o arquivo), como já é feito para SQLite em `local_recovery_screen`.

## BUG-047 — `SIGTERM` encerra o processo sem o desligamento cooperativo

**Status:** corrigido em 17 de outubro de 2026 (após a tag `v1.0.3`; entra na próxima release). Validação com `poweroff` real no Raspberry pendente.

- **Correção aplicada:** `main.install_termination_bridge` registra `SIGTERM`, `SIGINT` e `SIGHUP` com `signal.set_wakeup_fd` + `QSocketNotifier`, acordando o loop Qt (um handler Python puro não roda com `exec_` bloqueado em C++) e chamando `MainWindow.encerrar_por_sinal`, que registra o sinal com `paymentInFlight`/`orderId` e usa o mesmo `encerrar_terminal` do painel. `services/shutdown_budget.py` cria um prazo único (`APP247_SHUTDOWN_BUDGET_SECONDS`, padrão 20 s, abaixo de `TimeoutStopSec=30`) iniciado em `_parar_servicos`; todas as esperas de QThread/Thread do encerramento (pagamento, comprovante, recuperação, Wi-Fi, display, listener, monitor, heartbeat, sync, telemetria) usam `wait_ms`/`wait_seconds` e dividem esse prazo. Fora do encerramento cada espera mantém o limite anterior. Após o encerramento cooperativo, `main` faz `logging.shutdown()` e `os._exit(code)`, evitando o abort do Qt por QThread ainda vivo. O checkpoint de pagamento continua no SQLite e é reconciliado no próximo boot.
- **Testes:** `tests/test_shutdown_budget.py` — orçamento compartilhado; 5 workers de pagamento travados consomem no máximo 20 s (antes 125 s); processo GUI real com QThread travado recebe `SIGTERM`, encerra em menos de 5 s com código 0 e sem "Destroyed while thread".

- **Severidade:** média
- **Tipo:** confirmado
- **Arquivo/função:** não há `signal.signal` em `src/`; `MainWindow._parar_servicos` só roda pelo fluxo administrativo/`closeEvent`.
- **Cenário:** `systemctl --user stop`, `sudo poweroff` ou reboot.
- **Impacto:** workers, sockets e checkpoints não são encerrados de forma ordenada. Além disso, `_parar_servicos` pode bloquear a thread principal por muito mais que `TimeoutStopSec=30` (`confirmation.stop` espera até 50 s, cada worker de pagamento até 25 s, recuperação até 25 s).
- **Correção recomendada:** tratar `SIGTERM` via `QSocketNotifier`/timer chamando `encerrar_terminal`, e limitar a soma das esperas ao orçamento de parada da unit. SQLite (journal DELETE) e o checkpoint de pagamento continuam seguros; o risco maior é `terminal.json`/arquivos auxiliares (BUG-046).

## BUG-048 — Um único 401/403 bloqueia o Terminal até reiniciar

**Status:** corrigido em 2 de novembro de 2026 (`9c7fd81`, release 1.0.4); revisão de status em 25 de novembro de 2026. Aberto originalmente em 17 de outubro de 2026.

- **Severidade:** média
- **Tipo:** confirmado (latch) / potencial (403 por regra de negócio)
- **Arquivo/função:** `BackendClient.request` grava `AUTH_REQUIRED`/`FORBIDDEN` em `terminal_access_state` para qualquer endpoint; só a ativação volta a `OPERATIONAL`. `TerminalSocket._heartbeat` e `PaymentListener.run` **retornam definitivamente** após 401. `MainWindow._guard_device_auth` reposiciona a tela a cada 1 s.
- **Cenário:** credencial rotacionada/revogada e depois restaurada, ou um 403 pontual em endpoint não essencial.
- **Impacto:** operação bloqueada, heartbeat e socket de pagamento mortos até reinício manual, mesmo depois de reprovisionado. O texto atual pede reinício, então é comportamento conhecido, mas não automático.
- **Correção recomendada:** restringir o latch a endpoints de identidade/handshake, revalidar periodicamente e reiniciar heartbeat/listener ao voltar a `OPERATIONAL`.
- **Correção aplicada:** `BackendClient` só bloqueia com 401 de `DEVICE_UNAUTHORIZED_CODES` ou 403 de `DEVICE_FORBIDDEN_CODES` (outros 401/403, como QR de outro condomínio, não bloqueiam); `MainWindow._probe_device_access` reconsulta o bootstrap com limite de frequência e `_restore_device_access` volta a `OPERATIONAL` sem reinício, preservando pagamento pendente; `TerminalSocket` e `PaymentListener` aguardam e tentam de novo após 401 em vez de encerrar.
- **Validação:** `tests/test_device_access_recovery.py`, `tests/test_terminal_heartbeat.py`, `tests/test_purchase_api.py`. Validação no Raspberry pendente.

## BUG-049 — Socket de pagamento não detecta conexão meio-aberta

**Status:** corrigido em 25 de novembro de 2026 (entra na próxima release); validação no Raspberry pendente. Identificado em 17 de outubro de 2026.

- **Severidade:** média (mitigada)
- **Tipo:** potencial
- **Arquivo/função:** `PaymentListener.run` usa `settimeout(5)` e trata `WebSocketTimeoutException` com `continue`, sem ping/pong de aplicação; o backend mantém a sessão em `PaymentWebSocketHandler.sessions` enquanto `isOpen()`.
- **Cenário:** queda breve de Wi-Fi (medida perda de 13,33% no campo, ver [[wifi]]) sem FIN/RST.
- **Impacto:** o terminal continua `CONNECTED` e não reconecta; eventos `PAYMENT_STATUS`, `PRODUCT_SYNC_REQUIRED` e reset são perdidos. Pagamento é coberto pelo polling de `/order/{id}/status`; catálogo só atualiza no sync periódico (300 s) e reset no bootstrap (60 s). A telemetria mostra estado de socket falso.
- **Correção recomendada:** `ping` periódico com prazo de pong (ou derrubar o listener quando o heartbeat de `/terminal-socket` falhar).
- **Correção aplicada:** `PaymentListener` lê também os frames de controle (`recv_data(control_frame=True)`). Sem nenhum frame por `PING_INTERVAL_SECONDS` (20 s) envia `ping`; se nada chegar em `PONG_TIMEOUT_SECONDS` (15 s) levanta `PaymentSocketStale` e cai no caminho normal de reconexão (`RECONNECTING`, nova conexão em 5 s, que já dispara sync e consulta de lifecycle). Qualquer frame (evento, ping ou pong) conta como tráfego. Frame `CLOSE` do servidor também força a reconexão. Detecção no pior caso: cerca de 40 s. O backend roda em Tomcat (Spring Boot), que responde ping com pong sozinho; não precisou de mudança no backend.
- **Validação:** `tests/test_websocket_routing.py::PaymentSocketLivenessTest` (relógio falso) e teste manual com socket real em 25/11/2026: um servidor que faz o handshake e fica mudo derruba a conexão e reconecta; um servidor que responde pong mantém uma única conexão.

## BUG-050 — Logs da aplicação não sobrevivem a reinício no Raspberry

**Status:** corrigido em 25 de novembro de 2026 (entra na próxima release); validação no Raspberry pendente. Confirmado no Raspberry em 16 de outubro de 2026.

- **Severidade:** média
- **Tipo:** confirmado
- **Arquivo/função:** o app só registra em stdout (`logging.basicConfig`), a unit `systemd --user` envia ao journal e o journald do equipamento está com `Storage=volatile`. Não há arquivo de log.
- **Impacto:** as 6 falhas de partida do `app247-terminal.service` em 16/10 (14:29–14:37) e qualquer incidente de pagamento antes de um reboot não podem ser investigados.
- **Correção recomendada:** journald persistente com limite (`SystemMaxUse`) ou log rotativo próprio em `/var/lib/app247/logs`, sem segredos.
- **Correção aplicada:** log rotativo próprio (`logging_setup.configure_logging`, chamado no início de `_run_gui`) em `LOG_DIR/terminal.log`, por padrão `/var/lib/app247/logs/terminal.log`, com 5 MiB por arquivo e 4 arquivos antigos (cerca de 25 MiB no total; `APP247_LOG_DIR`, `APP247_LOG_MAX_BYTES`, `APP247_LOG_BACKUP_COUNT`). O journal continua recebendo as mesmas linhas pelo stderr. Se o diretório não puder ser aberto ou o arquivo for link simbólico, o Terminal sobe só com o journal e registra o motivo. A configuração do journald do sistema não foi alterada. O arquivo contém as mesmas linhas do journal: a regra de nunca registrar token, credencial ou senha continua valendo para quem escreve o log. O factory reset não apaga os logs.
- **Limite:** o arquivo fica no mesmo SSD. Se o disco cair (BUG-045), nem o journal nem este arquivo registram a queda; para isso continua valendo a sugestão de log remoto do BUG-045.
- **Observação de campo:** em 25/11/2026 o journal do equipamento já estava persistente (`journalctl -b -1` funcionou; ver BUG-045). O arquivo próprio continua útil porque não depende dessa configuração manual nem sai do equipamento numa reinstalação do sistema.
- **Validação:** `tests/test_logging_setup.py` (gravação, rotação com limite, sem handler duplicado, diretório inválido, link simbólico) e partida real da GUI offscreen em 25/11/2026: o arquivo foi criado e recebeu até a linha de encerramento por `SIGTERM`.

## BUG-051 — Instalação de campo diverge do layout e das permissões atuais

**Status:** parcialmente corrigido em 17 de outubro de 2026 — o instalador migra a unit legada (BUG-053); permissões de `/opt/app247` no campo continuam pendentes.

- **Severidade:** média
- **Tipo:** confirmado
- **Evidência:** `/opt/app247` e `/opt/app247/releases` pertencem a `jefro` (usuário gráfico); `releases/1.0.0` é gravável por ele; a unit instalada usa `/usr/local/bin/app247-terminal-launcher` e um override com `ExecStartPre=-/opt/app247/current/app247-terminal`, enquanto o pacote atual usa `app/app247-terminal`. Versão ativa `1.0.1`.
- **Impacto:** o usuário da sessão (com senha fraca e SSH aberto) pode trocar o código executado; a atualização a partir deste layout antigo não foi testada.
- **Correção recomendada:** validar `install.sh` atual contra essa instalação em ambiente de teste antes de aplicar no campo; garantir `root:root` em `/opt/app247` e releases.

## BUG-052 — Código morto e diretórios legados

**Status:** aberto; baixa prioridade.

- **Severidade:** baixa
- **Tipo:** confirmado
- **Arquivo/função:** `ui/screens/login.py` (`/usuarios/anonimo`, comentado em `application.py`), `Produtos.get_produtos_api` (`requests.get` sem autenticação e com `print`), diretórios não versionados `telas/`, `model/`, `service/`, `database/` com apenas `__pycache__`. Complementa BUG-025.
- **Correção recomendada:** remover em etapa própria após confirmar que não há uso.

## BUG-053 — `ExecStartPre --apply-display` abria a GUI e entrava em loop

**Status:** corrigido no repositório em 17 de outubro de 2026; no Raspberry há contorno manual (`override.conf` de 16/10 14:42) até instalar o launcher novo.

- **Severidade:** alta
- **Tipo:** confirmado (logs do Raspberry e reprodução com o launcher de `HEAD`)
- **Causa raiz:** o launcher das releases 1.0.0/1.0.1 (`HEAD:packaging/app247-terminal-launcher`) termina com `exec "$EXECUTABLE"` e **descarta os argumentos**. A unit de usuário instalada no campo chama `ExecStartPre=/usr/local/bin/app247-terminal-launcher --apply-display`; o executável recebia zero argumentos, iniciava a GUI completa (sync, heartbeat) e o systemd matava o pré-start após 90 s (`start-pre operation timed out`, 5× entre 14:29 e 14:36 de 16/10). Reprodução: launcher antigo → `args=0`; launcher novo → `args=1 [--apply-display]`.
- **Origem da unit divergente:** ela não vem de outro provisionador; é a saída de uma versão intermediária do `install.sh` (unit de usuário apontando para o launcher, sem marcador `# Managed by App247`), instalada junto com o launcher antigo. A unit de sistema de `HEAD` chamava o executável direto. O `install.sh` atual recusava sobrescrever essa unit sem marcador, então uma atualização no campo falharia.
- **Correção:** o launcher trata `--apply-display` em caminho próprio (só esse argumento, espera de sessão curta, `timeout` de 20 s, sem lock e sem GUI); o instalador reconhece a unit legada, guarda backup `.legacy-<data>`, substitui e avisa sobre drop-ins que redefinem `ExecStart*`. `Restart=on-failure` com `StartLimitBurst=5` é a política correta para unit de usuário (BUG-044). O `ExecStartPre` continua no launcher porque `DisplayService` precisa de `WAYLAND_DISPLAY` e de `DISPLAY_*` do `terminal.env`, que só o launcher resolve. O timeout do systemd não foi aumentado.
- **Testes:** `tests/test_service_startup.py` (argumento repassado, extras recusados, pré-start limitado mesmo com executável travado, execução em paralelo à GUI com lock, migração da unit legada do campo, preservação de unit alheia).

## BUG-054 — Toda saída normal da GUI terminava em `TypeError`

**Status:** corrigido em 17 de outubro de 2026.

- **Severidade:** média
- **Tipo:** confirmado (encontrado pelo teste de startup de BUG-046)
- **Arquivo/função:** `main._run_gui` chamava `_gui_exit_code(exit_code, window.shutdown_was_requested)`, mas `shutdown_was_requested` é argumento só por nome.
- **Impacto:** o encerramento administrativo saía com traceback e código 1, e `Restart=on-failure` religava o Terminal. Restrito ao worktree não commitado.
- **Correção:** chamada por palavra-chave; coberto por `test_gui_startup_survives_empty_terminal_json`.

## BUG-055 — Ativação no campo recusava o enable legado e o rollback é parcial

**Status:** corrigido em 17 de outubro de 2026 (recusa do enable na 1.0.3; rollback completo após a tag `v1.0.3`, entra na próxima release).

- **Severidade:** média
- **Tipo:** confirmado na primeira instalação da 1.0.3 no Raspberry
- **Causa:** `enable_user_service_offline` só aceitava `default.target.wants/app247-terminal.service -> ../app247-terminal.service`; o `systemctl --user enable` das instalações 1.0.0/1.0.1 cria link absoluto para a mesma unit. O `--activate` falhou e voltou `current` para 1.0.1.
- **Correção:** link absoluto para `USER_SERVICE_DESTINATION` é aceito como equivalente; link para outra unit continua recusado (`tests/test_service_startup.py`).
- **Rollback:** antes desta correção, `restore_previous_release` restaurava apenas `current`; launcher, unit, política de Wi-Fi e atalho já gravados permaneciam (no campo o resultado foi coerente, pois o launcher novo funciona com a 1.0.1). Agora o `--activate` faz snapshot de launcher, unit, link de enable, política do NetworkManager, ícone, atalho, atalho legado e autostart antes de gravá-los; qualquer falha após a troca de `current` restaura cada arquivo ou remove o que não existia, e faz `daemon-reload` antes de religar a release anterior. Teste: `test_failed_activation_restores_files_written_outside_releases` (falha com o instalador anterior).

## BUG-056 — Telas cortadas no display montado em pé

**Status:** corrigido em 17 de outubro de 2026 (entra na próxima release). Validação no Raspberry pendente.

- **Severidade:** alta (cliente não consegue ler nem tocar ações cortadas)
- **Tipo:** confirmado pelo operador no campo e por medição offscreen
- **Ambiente:** display 7" `1024×600` nativo montado em pé (área lógica `600×1024`), na porta HDMI 2 (`HDMI-A-2`).
- **Sintoma:** em `1024×600` rotacionado a interface ficava cortada; em modos maiores (ex.: 1080p) tudo cabia, mas o painel reduzia a imagem e o texto ficava ilegível.
- **Causa:** layouts com largura mínima acima de 600 px — teclado virtual (894), autenticação admin (942), configurações (926), carrinho (871), comprovante (766), pagamento (631), login (628), confirmação da compra (686) e o logo do Bem-vindo exibido no tamanho original (1138) até o primeiro resize. A janela fullscreen não encolhe abaixo do mínimo dos layouts. O teste de retrato existente usava `768×1360` e não incluía carrinho nem confirmação da compra.
- **Correção:** `ui/responsive.py` deriva o perfil compacto da largura lógica da tela (< 760 px) e reaplica quando a geometria muda (orientação pelo painel). Em retrato: `ESPAÇO`/`LIMPAR` descem para uma linha própria no teclado, o rodapé do carrinho empilha total sobre ações, as ações do comprovante viram coluna única e os títulos de login/configurações quebram linha. Ajustes neutros em paisagem: largura mínima real das teclas 44 px, padding lateral menor em botões que já ocupam a largura toda, logo inicial em 240 px, títulos de pagamento e confirmação com quebra. Paisagem permanece visualmente igual.
- **Paisagem (pré-existente, mesma causa):** `AdminAuthScreen` (altura mínima 798, teclas sobrepostas), `TecladoScreen` (616) e `PagamentoScreen` (606) excediam 600 px de altura em `1024×600` deitado. `PaymentStateWidget` e `ConfirmacaoScreen` escolhiam margens por `height() > width()` do próprio widget, então abriam com margens de retrato e o mínimo estourava antes do primeiro resize. Correção: ambos seguem o perfil da tela; deitado, teclas do teclado virtual têm 52 px de altura (em pé continuam 64), e o acesso admin usa margens menores, status de 30 px e `CANCELAR`/`ENTRAR` lado a lado. Maior altura mínima deitado: 578 px (admin).
- **Testes:** `tests/test_portrait_screens.py` valida as 11 telas em `600×1024` e em `1024×600`, incluindo carrinho e confirmação da compra; falha se o mínimo de qualquer tela exceder o display ou se botão sair da área, e cobre a troca de perfil.

## BUG-057 — Atalho da área de trabalho perguntava "Executar / Executar no Terminal"

**Status:** corrigido em 17 de outubro de 2026 no instalador (próxima release) e aplicado manualmente no Raspberry de campo.

- **Severidade:** baixa (operação)
- **Tipo:** confirmado pelo código do libfm 1.4 do Raspberry Pi OS (`raspberrypi-ui/libfm`)
- **Causa:** `fm_file_info_is_executable_type` trata todo `.desktop` local legível da área de trabalho como executável — com ou sem bit `+x` — e `on_exec_file` mostra o diálogo "This file is executable / seems to be an executable script" a menos que `quick_exec` esteja ativo. Nem o modo `0644` nem symlink evitam o diálogo (a exceção só vale para itens `menu://`).
- **Correção:** `install.sh` grava `quick_exec=1` na seção `[config]` de `~/.config/libfm/libfm.conf` do usuário gráfico, partindo do arquivo do usuário ou de `/etc/xdg/libfm/libfm.conf`, sem tocar nas outras chaves; entra no snapshot de rollback; `APP247_DESKTOP_QUICK_EXEC=false` desativa. Efeito colateral aceito: para esse usuário, arquivos executáveis abertos no gerenciador de arquivos rodam sem confirmação.
- **Junto:** `ensure_desktop_directory` agora cria cada nível com o dono gráfico; antes `~/.local/share/app247` ficava `root:root` dentro da home.
- **Campo (17/10 03:06):** `quick_exec=1` gravado em `/home/jefro/.config/libfm/libfm.conf`, dono de `~/.local/share/app247` corrigido e `pcmanfm --reconfigure` executado, sem reiniciar.
- **Testes:** `tests/test_service_startup.py` (criação a partir do arquivo do sistema, atualização de arquivo existente, desativação).

## BUG-058 — Factory reset desfeito pela migração do layout legado

**Status:** corrigido em 31 de outubro de 2026 (entra na próxima release).

- **Severidade:** alta (terminal volta com a identidade e a credencial antigas e não permite novo cadastro)
- **Tipo:** confirmado pelo operador e pelos arquivos em `data/` com data de 30/09 após o reset de 31/10
- **Sintoma:** depois de "Restaurar padrões de fábrica", a inicialização seguinte voltava a operar com o terminal anterior.
- **Causa:** `prepare_runtime_layout` copiava `db/` e `database/` para `data/` sempre que o destino não existia. O reset esvazia `data/` sem tocar a origem legada, então a cópia restaurava `terminal.json`, `device-credential` e `terminal.db`.
- **Correção:** a migração roda uma única vez, controlada por `legacy-layout.migrated`. Instalações sem o marcador que já têm `reset-backups/` ou `reset-staging/` não migram.
- **Pendente:** os arquivos legados, incluindo a credencial antiga, continuam em disco após o reset.
- **Testes:** `tests/test_packaging_architecture.py`.

## BUG-059 — Caixas de aviso ilegíveis

**Status:** corrigido em 31 de outubro de 2026 (entra na próxima release).

- **Severidade:** média (cliente e operador não conseguem ler avisos nem identificar os botões)
- **Tipo:** relatado pelo operador e reproduzido em render offscreen
- **Sintoma:** caixas de aviso com texto e botões da mesma cor do fundo, sem leitura possível.
- **Causa:** `QWidget { color: branco }` do tema é herdado pelo `QMessageBox`, mas o tema não definia fundo para ele. A caixa ficava com o cinza claro da paleta do sistema, e os botões sem `variant` não tinham fundo.
- **Correção:** regras de `QMessageBox` em `Theme.component_stylesheet()`, aplicadas também ao popup "Sem Internet" e à tela de recuperação local em `application.py`, que não tinham stylesheet do tema.
- **Testes:** `tests/test_message_box_theme.py`.

## BUG-060 — Sessão expirada com cliente identificado travava em "Confirmando pagamento"

**Status:** corrigido em 31 de outubro de 2026 (entra na próxima release).

- **Severidade:** alta (terminal fica preso até reiniciar e nenhuma compra nova começa)
- **Tipo:** relatado pelo operador; sequência reproduzida em teste, sem log da ocorrência original
- **Sintoma:** ao zerar o tempo, a tela fica em `CONFIRMANDO PAGAMENTO`, depois de 30 s passa a `AGUARDANDO PAGAMENTO` e não sai mais.
- **Causa:** vincular o cliente grava `cart_id` sem iniciar pagamento. `tratar_timeout_global` tratava esse `cart_id` como possível cobrança, mas a descoberta e o abandono retornam sem efeito quando `payment_in_flight` é falso, e nada concluía a expiração.
- **Correção:** sem Order, sem tentativa em voo e sem worker do Point, a expiração conclui direto. Com `payment_in_flight` ativo, a reconciliação continua igual.
- **Testes:** `tests/test_payment_flow.py`.

## BUG-061 — Cliente vinculado podia passar para a compra seguinte

**Status:** corrigido em 31 de outubro de 2026 (entra na próxima release).

- **Severidade:** alta (a compra de outra pessoa pode entrar no histórico e na fidelidade do cliente anterior)
- **Tipo:** requisito do operador; caminhos encontrados na leitura do código e reproduzidos em teste
- **Causa:** o vínculo só era limpo em `liberar_tela`. Remover o último item encerrava a sessão e mantinha "Compra vinculada a ...". Resposta do QR chegando depois do cancelamento gravava o `cart_id` antigo na compra nova. Pagamento recuperado após reiniciar mantinha o `cart_id` depois da falha, e a recuperação sem identidade local nunca limpava a sessão.
- **Divergência encontrada:** a recuperação do vínculo no início nunca funcionou. Ela lia `cartId`, mas `GET /carrinho/{id}` devolve `carrinhoId`, então mostrava um aviso de erro a cada início e mantinha o estado antigo.
- **Correção:** `IDLE` limpa o cliente em qualquer caminho, respostas de outra geração são descartadas e o vínculo não é mais recuperado ao iniciar, porque os itens não sobrevivem ao reinício. `CustomerLinkRecoveryWorker` e `PurchaseApi.get_cart` foram removidos. Na recusa, o cliente continua vinculado para a nova tentativa. Remover o último item avisa que a compra deixou de estar vinculada e pede um novo QR, para a pessoa não seguir achando que está identificada.
- **Testes:** `tests/test_customer_unlink.py`.

## BUG-062 — Tela de Wi-Fi conectada alargava a janela em retrato

**Status:** corrigido em 24 de novembro de 2026 e validado no Raspberry de campo (build local 1.0.6 sobre `f94afa9`).

- **Severidade:** alta (depois de abrir o Wi-Fi, todas as telas ficavam cortadas à direita até reiniciar o app, inclusive a de venda)
- **Tipo:** confirmado no campo por captura de tela (`grim`) no display `1024×600` em pé (`HDMI-A-2`, transform 90)
- **Sintoma:** em admin → Wi-Fi, `ATUALIZAR REDES`, `DESCONECTAR`, a lista e `VOLTAR` saíam da tela; ao voltar, Bem-vindo e acesso admin continuavam cortados (janela com ~690 px de largura).
- **Causa:** o card de status punha `Conectado: <SSID>` (H3 negrito, sem quebra) e `DESCONECTAR` lado a lado. No display real isso passa de 600 px; a janela fullscreen cresce para o mínimo do layout e não volta a encolher (mesmo mecanismo do BUG-056).
- **Por que os testes não pegaram:** a medição `QT_QPA_PLATFORM=offscreen`, inclusive rodada no próprio Pi com o `nmcli` real, dava 544 px — as métricas de fonte do offscreen são menores que as do Wayland real. Validação de largura de telas novas deve incluir captura no display.
- **Correção:** `WifiScreen` segue `follow_layout_profile`; em retrato o card empilha SSID/sinal/IP sobre o botão (`QBoxLayout.TopToBottom`) e os dois textos quebram linha. Paisagem continua lado a lado.
- **Testes:** `tests/test_portrait_screens.py::test_wifi_status_card_stacks_in_portrait` (direção por perfil e quebra de linha; a largura em si só é verificável no display).

## BUG-063 — Terminal podia ser fechado fora do painel administrativo

**Status:** corrigido em 25 de novembro de 2026; validação no Raspberry de campo pendente (exige reinstalar a unit).

- **Severidade:** média
- **Tipo:** confirmado por código e por teste da semântica do systemd (`systemd-run --user` com unidades temporárias)
- **Requisito:** cliente ou gestor só fecham o Terminal por admin → "Fechar Terminal".
- **O que já estava certo:** `MainWindow.closeEvent` ignora fechamento sem `_shutdown_authorized` (Alt+F4, fechar pela barra de tarefas ou menu do labwc) e `keyPressEvent` ignora Esc.
- **Brecha:** `SIGTERM`/`SIGINT`/`SIGHUP` vindos de fora do systemd (`pkill app247`, Ctrl+C num terminal, `SIGHUP` de fim de sessão) usavam o mesmo encerramento cooperativo do painel e saíam com **0**. Com `Restart=on-failure`, o systemd tratava isso como fechamento intencional e o Terminal **ficava fechado**.
- **Correção:** `encerrar_por_sinal` registra o sinal (`MainWindow.shutdown_signal`, só quando o encerramento ainda não começou pelo painel) e `main._gui_exit_code` devolve `128+N` (129/130/143). A unit passou a `Restart=always` + `RestartPreventExitStatus=0` + `SuccessExitStatus=129 130 143`: só o código 0 (painel ou restauração) mantém fechado; sinal externo, crash e qualquer outra saída reabrem em 3 s; `systemctl stop`, reboot e `poweroff` não reabrem e não marcam falha. O motivo que levou a trocar `always` por `on-failure` no BUG-044 (reabrir após o fechamento administrativo) fica coberto pelo `RestartPreventExitStatus=0`. O launcher continua saindo com 0 quando já há instância (lock), sem loop.
- **Fora do app (não alterado):** com teclado físico, os atalhos padrão do labwc no Pi ainda abrem menu (`Super`), terminal (`Ctrl+Alt+T`), executar (`Alt+F2`) e desligar/sair (`Ctrl+Alt+Del` → `pishutdown`). Pelo terminal o operador pode matar o app (agora ele volta) ou sair da sessão. No uso normal (touch + leitor de QR, sem modificadores) esses atalhos não são alcançáveis; bloqueá-los exige um `rc.xml` de quiosque no Pi.
- **Testes:** `test_main_cli_lifecycle.py::test_external_signal_exits_non_zero_so_systemd_reopens`, `test_safe_shutdown.py::test_external_signal_is_recorded_but_admin_shutdown_is_not`, `test_shutdown_budget.py` (processo real com `SIGTERM` sai 143), `test_packaging_architecture.py` (política da unit).

## BUG-064 — Setinha da janela de aviso escondia o Terminal

**Status:** corrigido em 25 de novembro de 2026; regra validada no Raspberry de campo com captura de tela (`grim`); app com `app_id` fixo validado na reinstalação.

- **Severidade:** alta (o Terminal some da tela e, no quiosque, não há como trazê-lo de volta sem teclado)
- **Tipo:** confirmado no campo
- **Sintoma:** nas janelas de aviso (`QMessageBox`) aparece uma barra com `˅`, `˄` e `×`. Tocar em `˅` "fechava o terminal".
- **Causa:** o labwc decora pelo servidor toda janela do app, inclusive os diálogos: `titlebar layout = :iconify,max,close` em `/etc/xdg/labwc/rc.xml`. `˅` é *minimizar*, que no labwc esconde o diálogo **e a janela principal**. O app não fechava (o journal não registrou saída); ficava minimizado atrás da área de trabalho, só com o botão "24/7 Terminal" na barra de tarefas.
- **Por que não pelo Qt:** com `Qt.FramelessWindowHint` o labwc 0.20.2 continua desenhando a mesma barra (testado no Pi com Qt 5.15.15).
- **Correção:** `install.sh` grava em `~/.config/labwc/rc.xml` do usuário gráfico um bloco entre marcadores `app247:kiosk-rule` com `<windowRule identifier="app247-terminal" serverDecoration="no" skipTaskbar="yes" skipWindowSwitcher="yes"/>` e recarrega o labwc (`SIGHUP`). O bloco é recolocado a cada instalação, entra no `<windowRules>` existente se houver, preserva o resto (ex.: `<touch>`) e entra no snapshot de rollback. `main` fixa `setDesktopFileName("app247-terminal")` para o `app_id` casar com a regra. Sem barra, sem botão e sem entrada na barra de tarefas, não há mais como minimizar pelo toque. O Qt não desenha decoração própria quando o servidor recusa a dele (verificado).
- **Testes:** `tests/test_service_startup.py` (`test_labwc_rule_*`: preserva o `touch`, é idempotente, entra no `<windowRules>` existente, cria o arquivo quando há labwc, não grava nada sem labwc).

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
