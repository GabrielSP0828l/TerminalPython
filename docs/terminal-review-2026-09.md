# Revisão do Terminal App247 — setembro de 2026

Data: 27 de setembro de 2026.

Escopo: `/home/jefiro/Documentos/projetos/TerminalPython`, com conferência somente leitura do backend em `/home/jefiro/Documentos/projetos/app247` e de `24por7_contexto/`.

Esta auditoria considera implementado somente o fluxo executável no *working tree* atual. README, documentação, classes não navegáveis, comentários e testes isolados não foram tratados como prova suficiente.

Documentos relacionados: [[terminal-audit-architecture]], [[terminal-pending]], [[arquitetura]], [[fluxo-compra]], [[api-backend]], [[websocket]], [[sqlite]], [[auditoria-bugs]] e [[melhorias]].

## Atualização de hardening P0/P1 — 27/09/2026

Esta seção substitui o estado histórico abaixo para os itens 1, 2 e 3 solicitados. Foram implementados: contenção de `.env`/runtime no Git, placeholders, permissões `0600`, autenticação `X-Terminal-Token` em HTTP e handshakes WS, reset fail-closed, `integrity_check` no startup, recovery sem identidade, kiosk por `APP_ENV`, Wi-Fi mínimo pré-ativação e cleanup uniforme dos workers Qt. Detalhes: [[terminal-device-security]], [[terminal-local-state-recovery]], [[terminal-kiosk-mode]] e [[terminal-worker-lifecycle]].

A autenticação reaproveita o segredo interno já existente no backend. Ela deixa de confiar somente no UUID, mas continua **parcial**: o segredo é compartilhado entre instalações e só admite rotação global. Credencial aleatória/hash/revogação individual por Terminal permanece P0.

Validação posterior ao hardening: 184/184 testes Python via `unittest`, suíte Maven do backend aprovada, compileall aprovado e SQLite `ok`. Smoke development: `1024x600`, `fullscreen=False`; smoke production: `fullscreen=True` na tela virtual `800x600` do plugin offscreen. A confirmação física production `1024x600` permanece pendente. Nenhuma integração externa real foi disparada.

## 1. Resumo executivo

O Terminal possui um núcleo funcional considerável e, no fluxo principal, melhor do que partes da documentação indicam. Ativação, catálogo por condomínio, sync FULL/INCREMENTAL atômico, scanner de produtos, carrinho com `Decimal`, reprecificação autoritativa, confirmação pré-pagamento, Point, tela laranja, cancelamento integral conservador, polling, WebSocket, recovery no startup, tela aprovada, e-mail/WhatsApp, Wi-Fi, display, heartbeat e telemetria possuem código real e testes.

O fluxo feliz de pagamento não apresentou o bug descrito de loading tardio: a tela laranja é aberta assim que o backend devolve uma cobrança Point aceita/intermediária. `FINALIZAR` apenas abre o resumo; somente `CONFIRMAR E PAGAR` inicia o worker financeiro. O cliente não conclui venda pela resposta de criação e não depende exclusivamente do WebSocket.

Os riscos mais graves são operacionais e de segurança:

1. `.env` com senha administrativa configurada está versionado; a senha observada é curta. Arquivos/bancos de instalações e backups já aparecem no índice/histórico do repositório.
2. HTTP operacional, heartbeat e WebSocket não possuem autenticação criptográfica do dispositivo; UUID/path é tratado como identidade suficiente em vários pontos.
3. reset administrativo local pode ser agendado durante pagamento ativo e, no próximo boot, move `terminal.json` e `terminal.db` antes de qualquer reconciliação.
4. perda/corrupção de `terminal.json` com `active_payment` existente leva à reativação, não a um estado seguro de recuperação.
5. o entry point atual não é fullscreen: fixa `1024x600` e chama `show()`.

Resultado das verificações:

- SQLite real: integridade `ok`, schema de catálogo v2, cinco tabelas esperadas;
- compilação Python: sucesso;
- testes: 174/174 aprovados;
- smoke Qt offscreen: sucesso em `1024x600`, `fullscreen=False`;
- nenhuma cobrança, envio de comprovante, alteração de Wi-Fi ou rotação física real foi executada.

### Separação entre bloqueador, bug e warning

- **Bloqueadores de produção:** exposição/versionamento de segredo e estado operacional, canais sem autenticação de dispositivo, reset/reativação sem guarda financeira e ausência de kiosk fullscreen.
- **Bugs confirmados:** comportamentos reproduzidos ou derivados diretamente de um caminho executável, enumerados na seção 6.
- **Warnings:** drift do `.venv`, warnings de sintaxe originados por dependências no `compileall`, aviso Qt/Wayland do smoke offscreen e ferramentas Raspberry ausentes no host de desenvolvimento. Esses warnings não causaram falha nos 174 testes.
- **Não testado:** qualquer conclusão que dependa de Point, scanner, touch, Wi-Fi ou Raspberry físico está explicitamente marcada; não foi convertida em bug sem evidência no código.

## 2. Arquitetura atual

O mapa completo está em [[terminal-audit-architecture]]. Em síntese:

```text
configuração/.env
  -> reset pendente
  -> identidade Terminal
  -> ativação se necessário
  -> restauração active_payment
  -> catálogo/sync
  -> Home
  -> scanner/carrinho
  -> resumo
  -> Point
  -> WS + polling/recovery
  -> resultado
  -> pós-compra
  -> reset local da experiência
```

`MainWindow` é o coordenador. `CompraSession` concentra a máquina de estado local e o timer global; `TerminalScreen` possui o carrinho; `PagamentoScreen` possui workers e timers financeiros. SQLite é cache de catálogo e checkpoint operacional, nunca fonte oficial de pagamento/estoque.

## 3. Funcionalidades completas

### Ativação básica

- QR com informações do equipamento;
- polling em worker com timeout;
- consumo do DTO real do backend;
- UUID canônico do backend;
- persistência atômica em `terminal.json`;
- Terminal não escolhe Empresa/Condomínio.

### Catálogo e sync

- endpoint real `/produtos/sync` por `uuidTerminal`;
- FULL inicial e recovery FULL de cache inconsistente;
- incremental por `syncAt` do servidor;
- validação do envelope/lote;
- commit único para produtos, barcodes, tombstones e cursor;
- coalescimento de eventos concorrentes;
- startup, periódico, WebSocket e reconnect;
- promoção/preço recebidos do backend;
- produto com estoque negativo permanece disponível se associação/produto estiverem ativos.

### Fluxo principal de compra

- scanner de barcode HID;
- adição e incremento por leitura repetida;
- remoção de produto;
- carrinho com `Decimal`;
- total e promoção visual;
- backend reprecifica e bloqueia aumento sem nova confirmação;
- tela de resumo anterior à cobrança;
- proteção contra múltiplos cliques.

### Pagamento Point

- checkpoint local antes do request financeiro;
- cart persistido antes do POST Point;
- worker fora da UI;
- loading curto;
- tela laranja imediatamente após aceite remoto;
- instrução para botão verde e troca de método;
- correlação por Terminal, Order e PaymentAttempt;
- WS + polling HTTP;
- cancelamento integral via backend;
- cancelamento incerto conserva bloqueio;
- aprovação centralizada e idempotente;
- falha definitiva preserva carrinho;
- timeout global não inventa resultado.

### Recovery

- `active_payment` persiste tentativa, cart, Order, pagamento, attempt, status e intenção de cancelamento;
- startup restaura checkpoint;
- startup sem checkpoint consulta tentativa ativa no backend;
- reconnect consulta backend;
- callback antigo é rejeitado;
- polling degradado mantém tela visível;
- `PAYMENT_ALREADY_ACTIVE` adota a tentativa autoritativa existente.

### Pós-compra e comprovante

- tela verde somente após estado aprovado;
- `orderId` preservado para ações;
- Finalizar encerra só a experiência local;
- WhatsApp e e-mail por teclado touch;
- Terminal chama apenas Spring;
- worker, timeout e proteção de clique duplo;
- resposta correlacionada;
- falha não altera aprovação.

### Operação

- menu admin com senha mascarada;
- Wi-Fi por NetworkManager/nmcli em worker;
- orientação Wayland/X11 com timeout;
- `ESC` consumido e fechamento não autorizado recusado;
- heartbeat com ACK;
- telemetria completa e não bloqueante;
- lifecycle/reset remoto confirmado por HTTP.

## 4. Funcionalidades parciais

| Área | O que funciona | O que falta/está frágil |
|---|---|---|
| Ativação | QR, polling, persistência | Wi-Fi/admin antes da ativação; retry/backoff; credencial de dispositivo |
| Scanner | EAN + Enter e repetição | parser central, debounce/framing, QR cliente/cupom, health do HID |
| Carrinho | add, incremento, remoção total, total | decremento unitário; peso/balança; persistência do carrinho visual |
| Pagamento | fluxo Point e recovery intermediário | recuperar UX aprovada após crash; autenticação de dispositivo; cleanup dos workers |
| SQLite | catálogo versionado e checkpoint | corruption handling; versionamento unificado; concorrência UI/sync |
| Pós-compra | Finalizar, e-mail, WhatsApp | CPF e identificação/histórico |
| Admin | senha, Wi-Fi, display, reset, saída | segredo forte/rotação/rate limit; reset seguro com pagamento |
| Kiosk | cursor oculto, ESC/close guard | fullscreen real e lockdown do compositor |
| Raspberry | métricas e adapters de SO | pacote/autostart/watchdog e validação física |
| Logging | correlação financeira e mascaramento | rotação/persistência/estrutura e remoção de prints legados |
| Testes | 174 unit/smoke aprovados | hardware, E2E, segurança e corrupção/recovery extremo |

## 5. Funcionalidades ausentes

- parser/classificador de input do scanner;
- QR `APP247:LINK:<token>`;
- QR `APP247:COUPON:<token>`;
- fluxo “Deseja salvar esta compra no histórico?”;
- vínculo de compra por CPF sem criar conta;
- aplicação e UX de cupom, inclusive mínimo e reserva;
- leitura real de balança/peso;
- autenticação forte de Terminal nos endpoints e WebSockets;
- recuperação guiada de SQLite corrompido;
- autostart/systemd/labwc/watchdog/logrotate no repositório;
- CI/configuração de testes declarada em `pyproject.toml` ou equivalente;
- testes físicos automatizados/roteiro executado no Raspberry/Point.

## 6. Bugs confirmados

### BUG-01 — Kiosk não abre fullscreen (`P1`) — CORRIGIDO

`main.py` executa `setFixedSize(1024, 600)` e `show()`; `showFullScreen()` está comentado. O smoke confirmou `fullscreen=False`. A documentação afirma o contrário.

### BUG-02 — Reset local ignora pagamento ativo (`P0`) — CORRIGIDO

`ConfiguracaoScreen.confirmar_reset` agenda reset sem consultar `CompraSession`. No boot seguinte, `FactoryResetService.apply_pending` move banco e identidade antes de criar `ActivePaymentStore`. Uma tentativa financeira pode continuar no backend/Point sem correlação ativa no Terminal.

### BUG-03 — Identidade inválida pode ocultar checkpoint financeiro (`P0`) — CORRIGIDO

`Terminal.is_activated` converte JSON inválido/ausente em “não ativado”. Nesse caminho `inicializar_terminal` não roda e `active_payment` não é restaurado. Reativação com outra identidade faz `ActivePaymentStore.load(terminal_id)` ignorar o registro anterior.

### BUG-04 — Wi-Fi indisponível na primeira ativação offline (`P1`) — CORRIGIDO

O monitor/overlay só inicia após ativação e `CadastroTerminalScreen` não abre admin. O único acesso ao menu é o toque longo no logo da Home, que não é a tela atual.

### BUG-05 — Dependência de imagem do QR não declarada (`P1`) — CORRIGIDO

`CadastroTerminalScreen` usa backend de imagem do `qrcode`; `Pillow` está instalado no `.venv`, mas não está em `requirements.txt` e `qrcode` não o declara como dependência obrigatória. Instalação limpa pode falhar ao gerar o QR.

### BUG-06 — Documentação funcional divergente (`P2`)

Há documentos que afirmam `showFullScreen`, outros dizem que recovery persistente ainda não existe, e o documento compartilhado de recovery diz que cancelamento Point não está disponível. O código atual possui checkpoint/recovery e cancelamento, mas não fullscreen.

### BUG-07 — Tela/fluxo legado de CPF quebrado (`LEGADO`, `P2`)

`TecladoScreen` referencia `parent.login`, que não é criado/adicionado, e não envia CPF. Não há navegação ativa até essa tela; portanto isso não prova suporte a CPF.

### BUG-08 — Estado de peso inconsistente (`P2`)

O carrinho exibe peso total como `float`, sempre inicializado em zero, e nunca popula `received_weight`. `Item.subtotal` possui ramo de peso, mas `Carrinho.total` soma preço × quantidade, não `Item.subtotal`. Fluxo pesável não é funcional.

## 7. Riscos financeiros

### P0

- reset local durante tentativa ativa perde o checkpoint operacional;
- identidade ausente/corrompida pode permitir reativação sem reconciliar tentativa anterior;
- endpoints financeiros e WebSockets não autenticam o dispositivo, ampliando risco de chamada/hijack por UUID/IDs conhecidos;
- segredo administrativo versionado facilita acesso a reset/saída/rede no equipamento físico.

### P1/P2

- resultado aprovado é removido de `active_payment` antes de o cliente finalizar a experiência; crash nessa janela perde tela verde e ações de comprovante;
- POST de carrinho não possui idempotência do cliente: resposta perdida antes do checkpoint pode deixar carrinho órfão;
- shutdown solicita interrupção, mas espera menos que o timeout real; thread HTTP pode sobreviver à destruição da UI;
- não há teste físico de Point offline, cancelamento de método e nova escolha.

Não foram encontrados no fluxo atual:

- aprovação local baseada apenas no 200 de criação;
- reset antes de `APPROVED`;
- nova Order ao cancelar somente a forma de pagamento;
- limpeza local em timeout de cancelamento;
- preço promocional recalculado pelo Terminal;
- credenciais Mercado Pago no Python.

## 8. Riscos de concorrência

### Proteções existentes

- `CompraSession.begin_payment` é single-flight;
- botão de confirmação desabilita antes do worker;
- cancelamento usa estado persistido;
- comprovante usa flag single-flight;
- sync usa lock + uma execução pendente;
- callbacks usam tentativa/Order/PaymentAttempt;
- eventos Qt cruzam threads por signals/slots;
- backend possui locks/idempotência próprios.

### Fragilidades

- workers de status/recovery/resume/cancel não têm cleanup uniforme após `finished`;
- polling prolongado pode acumular objetos `QThread` filhos;
- `parar_workers` aguarda 500 ms, abaixo dos timeouts HTTP;
- `requestInterruption` não cancela `requests` em andamento;
- scanner lê SQLite na UI enquanto sync escreve por conexão separada, sem WAL;
- métricas leem estado de sync/session sem snapshot/lock comum, embora o risco seja apenas telemetria inconsistente;
- `PaymentWebSocketHandler` do backend mantém uma sessão por UUID e substitui a anterior sem autenticação.

O bug de diagnóstico citado na solicitação não está presente no working tree atual. `TerminalScreen.iniciar_pagamento_confirmado` emite mensagens distintas para “pagamento ativo”, “sessão indisponível”, “carrinho vazio”, “tela incorreta” e “interações bloqueadas”.

## 9. UX pendente

- acesso a Wi-Fi durante ativação inicial;
- feedback de produto inexistente sem modal bloqueante;
- decremento unitário/edição de quantidade;
- UX real de peso;
- QR cliente/CPF/histórico;
- cupom e mensagens de mínimo;
- indicação operacional mais explícita quando recovery permanece indefinido por longo período;
- renderização física de todas as telas em 1024×600;
- fullscreen verdadeiro;
- feedback de senha admin bloqueada após tentativas repetidas.

## 10. Integrações pendentes

### Backend disponível, Terminal ausente

| Integração | Backend real | Terminal |
|---|---|---|
| customer link | `POST /terminal/customer-link/consume` | ausente |
| cupom QR | `POST /terminal/coupons/apply` | ausente |
| erro mínimo cupom | `COUPON_MINIMUM_NOT_REACHED` com valores | ausente |
| reserva/liberação cupom | lifecycle backend | ausente na UX/cliente |
| autenticação Terminal QR | `X-Terminal-Token` | não configurada/usada |

### Contrato inexistente/insuficiente

- `CPF_HISTORY` para associar compra sem criar conta;
- credencial única e rotacionável para todos os canais do dispositivo;
- idempotency key do POST de carrinho;
- checksum/contagem vinda do servidor para detectar FULL válido porém truncado semanticamente.

## 11. Raspberry e kiosk

### Implementado

- serial do device tree com fallback de machine-id;
- scanner HID por foco de `QLineEdit`;
- NetworkManager/nmcli;
- Wayland/wlr-randr e X11/xrandr;
- cursor oculto;
- ESC e fechamento protegidos;
- temperatura, energia, CPU/RAM/disco/load;
- `start.sh` e orientação salva.

### Pendente para produção

- fullscreen;
- autostart/supervisão/restart;
- instalação de dependências de SO;
- permissões/polkit/udev;
- configuração labwc/atalhos do compositor;
- rotação do touch junto ao display;
- logrotate/limites de disco;
- ensaio de queda de energia e SQLite;
- interface Wi-Fi física;
- scanner real e leituras rápidas;
- `vcgencmd`/temperatura/subtensão reais;
- reboot com pagamento pendente.

O host auditado é Ubuntu x86_64, possui `nmcli` e `xrandr`, mas não `wlr-randr`/`vcgencmd`; não representa o Raspberry final.

## 12. Telemetria

Status: **IMPLEMENTADO / NÃO VALIDADO EM HARDWARE**.

Coleta sistema, energia, rede, aplicação, WebSocket, sync, compra, pagamento e display em thread daemon. POST possui timeout, falhas não escapam e não bloqueiam venda. Heartbeat é independente. Os testes cobrem parsing de energia, ausência de sensor, rede, payload e falhas.

Pendências: autenticação, telemetria antes da ativação, persistência/alerta local quando backend permanece fora, validação física e saúde do scanner.

## 13. Testes

### Resultado

```text
compileall: OK
unittest: 174 testes em ~5,2 s, OK
SQLite integrity_check: ok
Qt startup smoke: OK, 1024x600, fullscreen=False
```

### Cobertura forte

- dinheiro/promoções;
- migração/cache/barcodes/sync e rollback;
- timer de 10 minutos;
- múltiplos cliques;
- correlação e callbacks atrasados;
- timeout/reconnect/cancelamento/recovery;
- comprovantes e teclados;
- layout de telas principais;
- admin, Wi-Fi e display com doubles;
- heartbeat, telemetria e lifecycle/reset.

### Cobertura ausente ou insuficiente

- estoque negativo explícito;
- produto inexistente e dois scanners rápidos;
- QR cliente/cupom;
- ativação HTTP e falhas de persistência;
- SQLite corrompido/futuro/bloqueado;
- identidade perdida com pagamento ativo;
- reset local durante pagamento;
- crash depois de aprovação e antes de Finalizar;
- autenticação/ataques de UUID e socket duplicado;
- runtime real 24/7 e vazamento de workers;
- Point/Raspberry/Wayland/touch/Wi-Fi físicos;
- backend e Terminal em teste integrado real.

`pytest` não está instalado/declarado; a suíte usa `unittest`. Não foram instaladas dependências adicionais.

## 14. P0

1. Segredo administrativo e estado operacional versionados.
2. HTTP/WS operacionais sem autenticação de dispositivo.
3. Reset local remove checkpoint de pagamento ativo no boot.
4. Identidade ausente/corrompida não entra em recovery financeiro seguro.
5. Socket de pagamento pode ser substituído por conexão não autenticada com o mesmo UUID.

## 15. P1

1. Kiosk não está fullscreen.
2. Wi-Fi não é acessível antes da ativação.
3. SQLite corrompido derruba startup sem plano de recuperação.
4. Concorrência SQLite pode bloquear leitura do scanner na UI.
5. Lifecycle/cleanup de workers financeiros é incompleto.
6. Shutdown espera menos que timeouts de rede.
7. Aprovação não é durável até a conclusão do pós-compra.
8. Senha admin curta, sem cooldown/rate limit.
9. Pillow/backend de QR ausente dos requisitos.
10. Deploy/supervisão do Raspberry não está no projeto.

## 16. P2

1. Parser do scanner e QR cliente/cupom.
2. CPF/histórico.
3. Cupom mínimo/reserva/cancelamento.
4. Quantidade unitária e produtos pesáveis.
5. Feedback de scanner não modal.
6. Idempotência de criação do carrinho.
7. Configuração robusta e telemetria pré-ativação.
8. Logs persistentes/rotativos.
9. Limpeza de código legado.
10. Correção da documentação divergente.

## 17. P3

1. Remover `print` remanescente.
2. Recriar/alinhar o `.venv` aos pins.
3. Adicionar configuração de CI/testes.
4. Documentar warnings Qt/Wayland esperados.
5. Avaliar checksum/contagem autoritativa do sync.

## 18. Matriz de features

| Feature | Status | Arquivos principais | Backend | Teste | Prioridade |
|---|---|---|---|---|---|
| ativação | PARCIAL | `CadastroTerminalScreen.py`, `Terminal.py` | compatível | modelo/layout; HTTP incompleto | P1 |
| sync | IMPLEMENTADO | `SyncService.py`, `DatabaseProdutos.py` | compatível | forte | P2 hardening |
| estoque negativo | IMPLEMENTADO | `ProdutoSyncChange.java`, lookup SQLite | compatível | ausente explícito | P2 teste |
| scanner | PARCIAL | `terminal_screen.py` | catálogo compatível | repetição apenas | P2 |
| parser de scanner | AUSENTE | — | endpoints QR existem | ausente | P2 |
| carrinho | PARCIAL | `Carrinho.py`, `terminal_screen.py` | compatível | bom | P2 |
| promoção/preço | IMPLEMENTADO | `Money.py`, `PurchaseApi.py` | autoritativo | forte | — |
| confirmação | IMPLEMENTADO | `ConfirmacaoCompraScreen.py` | n/a | 100 cliques | — |
| pagamento Point | IMPLEMENTADO | `pagamento.py`, `PurchaseApi.py` | compatível | forte/simulado | P0 segurança |
| loading/tela laranja | IMPLEMENTADO | `pagamento.py` | status intermediário | coberto | — |
| cancelamento integral | IMPLEMENTADO | `pagamento.py` | compatível | timeout/confirmado | — |
| cancelamento de método | IMPLEMENTADO por estado | tela permanece ativa | backend mantém intermediário | UI; físico ausente | P1 teste físico |
| recovery | PARCIAL | `ActivePaymentStore.py`, `CompraSession.py` | compatível | forte | P0 bordas |
| WebSocket | FRÁGIL/INSEGURO | `PaymentListener.py`, `TerminalSocket.py` | existe, sem auth | routing/reconnect | P0 |
| timers | IMPLEMENTADO | `CompraSession.py`, `pagamento.py` | compatível | forte | — |
| pós-compra | PARCIAL | `ConfirmacaoScreen.py` | comprovante compatível | bom | P2 CPF |
| comprovante | IMPLEMENTADO | `ConfirmacaoScreen.py`, `PurchaseApi.py` | compatível | forte | — |
| QR cliente | AUSENTE | — | endpoint existe | ausente | P2 |
| CPF histórico | AUSENTE | botão desabilitado | contrato específico ausente | ausente | P2 |
| cupom | AUSENTE | — | endpoint existe | ausente | P2 |
| admin | INSEGURO | `AdminAuthScreen.py`, `ConfiguracaoScreen.py` | local | funcional | P0/P1 |
| Wi-Fi | IMPLEMENTADO / NÃO FÍSICO | `WifiService.py`, `WifiScreen.py` | n/a | doubles | P1 ativação |
| display | IMPLEMENTADO / NÃO FÍSICO | `DisplayService.py`, `DisplayScreen.py` | n/a | doubles | P1 produção |
| telemetria | IMPLEMENTADO / NÃO FÍSICO | collectors + `TelemetryService.py` | compatível | forte | P0 auth |
| kiosk | BUG/PARCIAL | `main.py` | n/a | guards; fullscreen falha | P1 |
| Raspberry deploy | AUSENTE/PARCIAL | `start.sh` | n/a | ausente | P1 |
| logging | PARCIAL | vários | n/a | indireto | P2 |

## 19. O que existe somente como intenção/documentação

- fullscreen canônico;
- QR de cliente e cupom no Terminal;
- CPF pós-compra/histórico;
- validação física Raspberry/Point;
- deployment 24/7 supervisionado;
- segurança de dispositivo para canais operacionais.

Também há documentação desatualizada que descreve como pendente o recovery SQLite já implementado e que descreve como indisponível o cancelamento integral já presente no código/backend.

## 20. Ordem recomendada

1. Contenção de segurança: retirar/rotacionar segredos e dados operacionais do Git; definir autenticação de dispositivo HTTP/WS.
2. Fechar segurança financeira do lifecycle: bloquear reset/reativação quando houver tentativa não reconciliada e cobrir identidade/SQLite corrompidos.
3. Tornar o runtime realmente de produção: fullscreen, Wi-Fi pré-ativação, workers/SQLite robustos e pacote Raspberry supervisionado.
4. Executar matriz física Point/Raspberry, incluindo cancelamento de método, webhook perdido, reboot e aprovação tardia.
5. Só depois implementar parser de scanner, identificação de cliente/CPF e cupom usando os contratos backend reais.

## 21. Dependências

`requirements.txt` declara PyQt5, sip, dotenv, qrcode, requests e websocket-client. Todas são usadas direta ou indiretamente. `Pillow` é usado de fato pelo ambiente para o QR, mas não está declarado. Não há `pyproject.toml`, Pipfile ou pytest config.

O `.venv` auditado tem `python-dotenv 1.2.2`, enquanto o arquivo pede `1.2.3`; os testes passaram mesmo assim. Isso é drift de ambiente, não erro funcional observado.

## 22. Divergências registradas

| Documento/intenção | Código real |
|---|---|
| `MainWindow / showFullScreen` | `setFixedSize(1024,600)` + `show()` |
| recovery após restart “pendente” em docs antigas | `active_payment` + startup recovery implementados |
| shared `payment-recovery.md`: cancelamento indisponível | controller, service e UI de cancelamento existem |
| 134 testes em `docs/00-index.md` | 174 testes executados |
| CPF sem contrato em docs antigas | backend agora tem customer-link/coupon, mas ainda não há `CPF_HISTORY` no Terminal |

As divergências foram documentadas aqui; nenhum comportamento foi alterado nesta tarefa.
