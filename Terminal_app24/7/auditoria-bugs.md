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

**Status:** corrigido para queda/reconexão do backend e perda de WebSocket; persistência após reboot físico permanece em [[melhorias]].

- **Severidade:** alta
- **Tipo:** corrigido
- **Arquivo/função:** `PaymentListener.run`; persistência local
- **Cenário:** webhook aprova enquanto socket está offline.
- **Impacto:** backend pago e terminal exibindo espera/erro.
- **Correção:** conexão/reconexão abre “Verificando pagamento”, consulta o endpoint correlacionado e mantém polling HTTP controlado a cada 10 segundos. O backend reconcilia com a Order Point antes de responder.
- **Validação:** testes cobrem `APPROVED`, `WAITING_PAYMENT` e `REJECTED` recebidos pela consulta pós-reconexão.

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
- **Correção aplicada:** `MainWindow` inicia/para `InternetMonitor` contra `API_URL`; `OfflineOverlay` abre o mesmo fluxo administrativo autenticado de Wi-Fi e é suspenso somente durante a manutenção. Socket, sync e heartbeat continuam donos da própria reconexão.

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

**Status:** aberto; confirmado por código em 17 de outubro de 2026.

- **Severidade:** média
- **Tipo:** confirmado
- **Arquivo/função:** não há `signal.signal` em `src/`; `MainWindow._parar_servicos` só roda pelo fluxo administrativo/`closeEvent`.
- **Cenário:** `systemctl --user stop`, `sudo poweroff` ou reboot.
- **Impacto:** workers, sockets e checkpoints não são encerrados de forma ordenada. Além disso, `_parar_servicos` pode bloquear a thread principal por muito mais que `TimeoutStopSec=30` (`confirmation.stop` espera até 50 s, cada worker de pagamento até 25 s, recuperação até 25 s).
- **Correção recomendada:** tratar `SIGTERM` via `QSocketNotifier`/timer chamando `encerrar_terminal`, e limitar a soma das esperas ao orçamento de parada da unit. SQLite (journal DELETE) e o checkpoint de pagamento continuam seguros; o risco maior é `terminal.json`/arquivos auxiliares (BUG-046).

## BUG-048 — Um único 401/403 bloqueia o Terminal até reiniciar

**Status:** aberto; confirmado por código em 17 de outubro de 2026 (impacto de 403 depende do backend).

- **Severidade:** média
- **Tipo:** confirmado (latch) / potencial (403 por regra de negócio)
- **Arquivo/função:** `BackendClient.request` grava `AUTH_REQUIRED`/`FORBIDDEN` em `terminal_access_state` para qualquer endpoint; só a ativação volta a `OPERATIONAL`. `TerminalSocket._heartbeat` e `PaymentListener.run` **retornam definitivamente** após 401. `MainWindow._guard_device_auth` reposiciona a tela a cada 1 s.
- **Cenário:** credencial rotacionada/revogada e depois restaurada, ou um 403 pontual em endpoint não essencial.
- **Impacto:** operação bloqueada, heartbeat e socket de pagamento mortos até reinício manual, mesmo depois de reprovisionado. O texto atual pede reinício, então é comportamento conhecido, mas não automático.
- **Correção recomendada:** restringir o latch a endpoints de identidade/handshake, revalidar periodicamente e reiniciar heartbeat/listener ao voltar a `OPERATIONAL`.

## BUG-049 — Socket de pagamento não detecta conexão meio-aberta

**Status:** aberto; potencial, identificado em 17 de outubro de 2026.

- **Severidade:** média (mitigada)
- **Tipo:** potencial
- **Arquivo/função:** `PaymentListener.run` usa `settimeout(5)` e trata `WebSocketTimeoutException` com `continue`, sem ping/pong de aplicação; o backend mantém a sessão em `PaymentWebSocketHandler.sessions` enquanto `isOpen()`.
- **Cenário:** queda breve de Wi-Fi (medida perda de 13,33% no campo, ver [[wifi]]) sem FIN/RST.
- **Impacto:** o terminal continua `CONNECTED` e não reconecta; eventos `PAYMENT_STATUS`, `PRODUCT_SYNC_REQUIRED` e reset são perdidos. Pagamento é coberto pelo polling de `/order/{id}/status`; catálogo só atualiza no sync periódico (300 s) e reset no bootstrap (60 s). A telemetria mostra estado de socket falso.
- **Correção recomendada:** `ping` periódico com prazo de pong (ou derrubar o listener quando o heartbeat de `/terminal-socket` falhar).

## BUG-050 — Logs da aplicação não sobrevivem a reinício no Raspberry

**Status:** aberto; confirmado no Raspberry em 16 de outubro de 2026.

- **Severidade:** média
- **Tipo:** confirmado
- **Arquivo/função:** o app só registra em stdout (`logging.basicConfig`), a unit `systemd --user` envia ao journal e o journald do equipamento está com `Storage=volatile`. Não há arquivo de log.
- **Impacto:** as 6 falhas de partida do `app247-terminal.service` em 16/10 (14:29–14:37) e qualquer incidente de pagamento antes de um reboot não podem ser investigados.
- **Correção recomendada:** journald persistente com limite (`SystemMaxUse`) ou log rotativo próprio em `/var/lib/app247/logs`, sem segredos.

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

**Status:** recusa corrigida em 17 de outubro de 2026; rollback parcial aberto.

- **Severidade:** média
- **Tipo:** confirmado na primeira instalação da 1.0.3 no Raspberry
- **Causa:** `enable_user_service_offline` só aceitava `default.target.wants/app247-terminal.service -> ../app247-terminal.service`; o `systemctl --user enable` das instalações 1.0.0/1.0.1 cria link absoluto para a mesma unit. O `--activate` falhou e voltou `current` para 1.0.1.
- **Correção:** link absoluto para `USER_SERVICE_DESTINATION` é aceito como equivalente; link para outra unit continua recusado (`tests/test_service_startup.py`).
- **Aberto:** `restore_previous_release` restaura apenas `current`; launcher, unit, política de Wi-Fi e atalho já gravados permanecem. No campo o resultado foi coerente (launcher novo funciona com a 1.0.1), mas o rollback deveria restaurar ou declarar esses arquivos.

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
