# Telas do Terminal

Voltar para [[00-index]]. Fluxo funcional em [[fluxo-compra]] e limites de integração em [[compatibilidade-backend]].

## Display de referência

A interface operacional é validada prioritariamente no display físico de 7 polegadas, `1024×600` nativo. No campo ele fica **em pé** (área lógica `600×1024`) na porta HDMI 2. A janela continua fullscreen e as páginas permanecem no `QStackedWidget`; nenhuma tela de compra abre janela separada.

O ponteiro do mouse fica visível: a aplicação não aplica cursor em branco.

Toda tela precisa caber nas duas áreas. `ui/responsive.py` define o perfil compacto quando a largura lógica da tela é menor que 760 px e o reaplica quando a orientação muda. No perfil compacto:

- teclado virtual: `ESPAÇO` e `LIMPAR` ficam em linha própria; teclas têm 44 px mínimos de largura e 64 px de altura;
- carrinho: 2 colunas de cards (cálculo existente pelo viewport) e rodapé com `TOTAL` acima de `CANCELAR COMPRA`/`FINALIZAR`;
- comprovante: `FINALIZAR`, WhatsApp e CPF em coluna única;
- títulos de login e configurações quebram linha.

Fora do perfil compacto (deitado, 600 px de altura): teclas do teclado virtual com 52 px de altura; acesso admin com margens menores e `CANCELAR`/`ENTRAR` lado a lado; estados de pagamento e comprovante com margens de paisagem desde a construção.

Medição offscreen (DejaVu Sans): em `600×1024` nenhuma tela passa de 584 px de largura mínima; em `1024×600` nenhuma passa de 578 px de altura mínima. Gate: `tests/test_portrait_screens.py`, nas duas orientações.

## Administração, Wi-Fi e display

O toque longo e a senha de `AdminAuthScreen` continuam sendo a única entrada. A mesma `ConfiguracaoScreen` possui agora três páginas internas: menu, [[wifi]] e [[display]]. O menu preserva reset e fechamento e acrescenta `CONFIGURAR WI-FI` e `ORIENTAÇÃO DA TELA`; voltar de subpágina não pede nova senha, mas sair do painel encerra a autorização.

`WifiScreen` mostra estado, SSID, sinal humano/percentual, IP, atualizar, desconectar/ativar e redes disponíveis. Cards têm ao menos 76 px; senha protegida usa input mascarado e teclado alfanumérico/símbolos. Scan/conexão/desconexão usam spinner, worker e timeout. O overlay offline permite entrar nesse mesmo fluxo autenticado.

`DisplayScreen` mostra orientação e saída atuais e oferece apenas `HORIZONTAL`/`VERTICAL`. Compra/pagamento bloqueiam a ação; o compositor gira a saída e os layouts recebem a nova geometria, sem rotação individual de widgets.

## Caixas de aviso

Todo `QMessageBox` usa as regras de `Theme.component_stylesheet()`: fundo `SURFACE_ELEVATED`, texto branco, botão padrão em `PRIMARY` e demais botões com contorno. Em confirmação destrutiva o botão padrão é `CANCELAR`, então ele é o destacado. Aviso criado a partir de widget sem stylesheet do tema (janela principal) precisa aplicar `Theme.component_stylesheet()` nele mesmo. Gate: `tests/test_message_box_theme.py`.

## Tela de compra

`TerminalScreen` é composta por header, catálogo rolável, scanner/peso e footer fixo. Somente o catálogo rola. Total, cancelamento e `FINALIZAR` permanecem visíveis.

O catálogo usa `QGridLayout` dentro de `QScrollArea`. O cálculo parte da largura do viewport, já descontada a barra vertical:

- cards entre 250 e 292 px de largura;
- no máximo quatro colunas;
- 3 colunas em `1024×600`;
- espaçamento de 12 px;
- altura fixa de 280 px;
- scroll vertical sempre disponível e scroll horizontal desativado;
- distribuição real por `row, column = divmod(index, columns)`.

Cada card mostra somente nome, subtotal exibido, preço unitário (só com Qtd > 1), quantidade em pílula e a lixeira de remover; em promoção, também o preço original riscado e o selo de desconto. O nome usa 26 px e no máximo três linhas, com elipse quando necessário; o preço usa 34 px e só encolhe (até 22 px) quando o valor não cabe na largura do card; a quantidade usa 22 px. Um filete azul e laranja no topo dá a identidade da marca. Detalhes em `docs/design-system.md` (Card de produto do carrinho). Nenhum barcode, UUID, categoria ou identificador técnico é exibido.

O footer usa uma única faixa horizontal para aproveitar a altura de 600 px. `TOTAL` usa 28 px, o valor usa 46 px e `FINALIZAR` usa 26 px com 72 px mínimos de altura. O relógio global de 10 minutos fica oculto e só aparece nos últimos 60 s, em 20 px, com o aviso "Sessão prestes a encerrar". Deitado fica no canto direito do cabeçalho; em pé o cabeçalho não comporta o texto (~370 px), então o relógio ocupa uma linha própria logo abaixo do cabeçalho (lista) ou do título (confirmação), na largura toda. A troca acompanha a orientação em tempo real.

Ao atingir `00:00`, o scanner, remoções, cancelamento e `FINALIZAR` são desabilitados antes da navegação. Sem pendência financeira, o controlador limpa a compra e abre a tela de boas-vindas; a lista não possui lógica própria de timeout.

Inatividade: após 90 s sem toque nem leitura, lista e confirmação mostram "Ainda está aí?" com contagem de 20 s e `CONTINUAR` (ação primária laranja, 72 px). O aviso (`InactivityPrompt`) cobre só a área de conteúdo — lista de produtos ou resumo — com véu escuro e cartão de borda amarela e raio de modal; cabeçalho com o relógio da sessão, total e botões continuam visíveis e livres, inclusive quando os dois avisos aparecem juntos. Em pé o cartão empilha título, contagem e botão; deitado o botão fica ao lado do texto. Sem resposta, a compra encerra pelo caminho do teto (ver [[fluxo-compra]]).

Promoção vem do catálogo sincronizado: `precoOriginal`, `emPromocao`, `promocaoId` e `promocaoNome` (ver [[compatibilidade-backend]]). A tela não calcula preço promocional: exibe o `preco` recebido e, quando `emPromocao` é verdadeiro, o preço original riscado e um selo com o percentual de desconto arredondado para baixo, ou com o nome da promoção quando o percentual não pode ser calculado.

## Confirmação da compra

A estrutura e a fonte única do carrinho foram preservadas. A revisão foi tipográfica e de contraste:

- título `CONFIRME SUA COMPRA`: 40 px;
- nome: 26 px;
- quantidade e preço: 24 px;
- total em card branco sólido, texto escuro e borda azul: rótulo 28 px e valor 48 px;
- `VOLTAR` e `CONFIRMAR E PAGAR`: 26 px e 72 px mínimos de altura;
- fundo escuro pintado explicitamente para não depender do compositor Qt.

O mesmo evento global bloqueia imediatamente `VOLTAR` e `CONFIRMAR E PAGAR`; o controlador cancela o resumo, reutiliza `reset_compra` e retorna às boas-vindas quando ainda não há operação financeira a reconciliar.

## Preparação e recuperação do pagamento

O loading usa `BrandLoader` (arcos azul e laranja da marca, `ui/brand.py`), em 128×128, animado só enquanto visível. `Preparando pagamento...` usa 32 px. O primeiro clique bloqueia botão e estado local antes do worker; sinais seguintes são ignorados.

Se a sessão expirar durante esse loading, a tela não libera ações. Um worker Point ainda em execução pode terminar apenas para informar com segurança se existem `cartId`/`orderId`; seu callback é aceito somente para a tentativa capturada. Sem referência remota após a resposta delimitada, ocorre reset. Com referência remota, a tela passa à reconciliação.

Assim que o Spring confirma a criação remota, a tela laranja `FINALIZE NA MAQUININHA` substitui o loading, inclusive em `PENDING`, `CREATED`, `AT_TERMINAL`, `ACTION_REQUIRED`, `WAITING_PAYMENT`, `PROCESSING` ou `UNKNOWN`. Ela orienta pressionar verde novamente depois de cancelar uma forma e oferece `CANCELAR COMPRA` em botão de perigo com 60 px mínimos. Point desligada, reconnect, restart e falha de consulta permanecem nessa tela quando já existe `orderId`; após três falhas o polling desacelera para 30 segundos.

## Validação visual

Em render Qt offscreen exato de `1024×600`, seis produtos resultaram em três cards por linha, cards de `292×224`, segunda linha por scroll vertical, nenhum scroll horizontal e footer fixo. A confirmação manteve total e botões integralmente visíveis. A validação automatizada não inicia cobrança real.

A tela Point também foi renderizada em `1024×600`: ícone, título, duas instruções e `CANCELAR COMPRA` ficam integralmente visíveis; texto branco mantém alto contraste sobre o laranja e o botão destrutivo usa vermelho escuro, sem elementos pequenos.

## Resultado aprovado e pós-compra

Somente um status interno aprovado e correlacionado (`APPROVED`, `PAID` ou `PROCESSED`) abre `ConfirmacaoScreen`. A página verde conserva `orderId`, mostra `PAGAMENTO APROVADO` e organiza ações em grade 2×2 para `1024×600`: `FINALIZAR` é primária; WhatsApp e e-mail são secundárias funcionais; `ADICIONAR CPF` permanece visível e desabilitado porque não existe contrato backend para associá-lo à Order.

WhatsApp abre campo controlado exclusivamente pelo `NumericKeyboard` touch da aplicação, com máscara visual e teclas `LIMPAR`/`⌫`; não depende de teclado físico ou do sistema operacional. E-mail usa `EmailKeyboard`, em minúsculas, com `@`, `.`, `_`, `-` e atalhos de domínio. Cancelar fecha a entrada e volta ao aprovado sem perder a Order. Validação inválida permanece inline.

O timeout pós-compra é de 45 s (`POST_PURCHASE_TIMEOUT_SECONDS`) e volta à tela inicial como `FINALIZAR`. Enquanto a entrada está aberta ou o worker envia, ele fica pausado. Sucesso ou falha abre feedback humano e preserva as demais ações; falha nunca volta ao pagamento. Todos os targets desta tela e dos teclados foram validados em Qt offscreen no display `1024×600`.

## Marca e movimento

`ui/brand.py` concentra o kit visual: `BrandLogo` (logotipo oficial `logo.png`; pulso suave só na `TelaBemVindos`, estático em ativação, recuperação e cabeçalho do carrinho), `BrandLoader`, `AnimatedCheck` (pagamento aprovado), `flash` (rodapé do total; o card lido tem borda laranja própria de 600 ms), `shake` (ícone da recusa) e `FadeStackedWidget` (troca de página síncrona com fade visual de 250 ms). Nenhuma camada de animação recebe toque ou foco, e `APP247_ANIMATIONS=0` desliga o movimento. Tokens e regras em `docs/design-system.md`.

## Textos das telas

Textos de interface centralizados em `ui/texts.py`. Telas do cliente mostram um título e uma ação; o relógio de sessão só aparece nos últimos 60 s; remover item usa ícone de lixeira (`assets/icons/trash.svg`, 56×56); o vínculo com o App247 é uma linha curta com ícone de QR. Na ativação, o loader ocupa o lugar do QR até o pareamento chegar. Falha de integridade e credencial bloqueada exibem "Terminal indisponível / Chame um atendente." e registram o motivo no log.
