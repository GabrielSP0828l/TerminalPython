# Design System — Terminal App 24/7

Voltar para [[00-index]]. Layout portrait em [[layout-vertical]] e inventário em [[telas]].

Esta é a única referência visual do Terminal. A fonte de verdade executável está em `src/app247_terminal/ui/styles/tokens.py` e `src/app247_terminal/ui/styles/theme.py`; telas não mantêm QSS próprios. O padrão foi extraído das telas históricas mais maduras (boas-vindas e carrinho) e consolidado com os estados Point já funcionais.

## Princípios

- interface de totem/touchscreen, não desktop;
- portrait-first, fullscreen e expansível;
- uma ação dominante por etapa;
- feedback imediato antes de qualquer operação remota;
- estado expresso por ícone, texto e cor;
- texto curto, legível à distância e com quebra de linha;
- regra de negócio e estado da compra permanecem fora do estilo.

## Paleta

| Papel | Token | Valor |
|---|---|---|
| fundo | `BACKGROUND_PRIMARY` | `#08111F` |
| fundo profundo | `BACKGROUND_SECONDARY` | `#03111F` |
| card | `SURFACE` | `#071C33` |
| card elevado | `SURFACE_ELEVATED` | `#0D253F` |
| ação principal | `PRIMARY` | `#169DFF` |
| informação | `SECONDARY` / `INFO` | `#62C8FF` |
| texto principal | `TEXT_PRIMARY` | `#FFFFFF` |
| texto secundário | `TEXT_SECONDARY` | `#8DD4FF` |
| borda | `BORDER` | `#17324D` |
| sucesso | `SUCCESS` | `#00D084` |
| atenção/processamento | `WARNING` | `#E0B54A` |
| erro/offline | `ERROR` | `#FF4D4D` |
| sucesso fullscreen | `PAYMENT_SUCCESS_BACKGROUND` | `#087A4F` |
| atenção fullscreen | `PAYMENT_ATTENTION_BACKGROUND` | `#C44D0A` |
| falha fullscreen | `PAYMENT_ERROR_BACKGROUND` | `#D92D20` |

## Tipografia

Família: `Segoe UI`, fallback `DejaVu Sans`. Dados técnicos usam `Consolas`/`DejaVu Sans Mono`.

| Estilo | px | Uso |
|---|---:|---|
| Display | 52 | total e resultado excepcional |
| H1 | 38 | título principal |
| H2 | 30 | seção |
| H3 | 26 | preço e status |
| Body | 22 | texto normal |
| Label | 20 | rótulo |
| Small | 18 | texto auxiliar |
| Caption | 16 | metadado técnico não essencial |
| Button | 22 | botão |

Na compra em `1024×600`, os tokens especializados são: nome 26 px, preço 34 px, quantidade 22 px, valor total 46 px e ação principal 26 px. Na confirmação: título 40 px, nome 26 px, detalhe 24 px, total 48 px e ações 26 px. O loading usa 32 px.

Informação operacional importante não usa 12–16 px. Em área pequena, o layout reflui ou ganha scroll antes de reduzir texto.

## Toque, espaçamento e raios

- alvo mínimo: 56 px;
- input: 60 px;
- botão secundário: 60 px;
- ação principal: 72 px;
- ícone de ação: cerca de 32 px;
- espaçamento: 4, 8, 12, 16, 24, 32 e 48 px;
- raios: 8 px compacto, 12 px input/botão, 18 px card, 24 px modal.

## Componentes semânticos

`Theme.component_stylesheet()` fornece:

- `QPushButton[variant="primary|secondary|danger|ghost|remove"]`;
- `QPushButton[primaryAction="true"]`;
- `QLineEdit[role="input"]`;
- `QFrame[role="card|information"]`;
- `QLabel[role="pageTitle|pageSubtitle|sectionTitle"]`;
- `QLabel[state="success|warning|error|info|loading"]`;
- scroll vertical com indicador largo.

Temas de página (`cart_stylesheet`, `purchase_confirmation_stylesheet`, `payment_stylesheet`, `confirmation_stylesheet`, `activation_stylesheet`, `welcome_stylesheet`, `settings_stylesheet`, `keyboard_stylesheet`, `app_payment_stylesheet` e `offline_stylesheet`) apenas especializam esses componentes. Os antigos arquivos `.css` duplicados foram removidos após todas as telas deixarem de referenciá-los.

`admin_stylesheet()` combina card, campo protegido, mensagem de erro e o mesmo teclado de `keyboard_stylesheet()`, incluindo alternância `ABC/abc`. A autenticação administrativa ocupa a página fullscreen em portrait; não usa diálogo pequeno. O valor digitado permanece mascarado. Confirmações destrutivas usam botões touchscreen com textos explícitos `CANCELAR`, `RESETAR` ou `ENCERRAR`.

`wifi_stylesheet()` e `display_stylesheet()` derivam dos mesmos tokens. Em `1024×600`, o menu usa botões de 60–72 px, cards de rede usam no mínimo 76 px, títulos ficam na faixa H1/H2 e texto operacional nunca cai para fonte desktop pequena. Estado atual fica em card de alto contraste; conectado/sucesso, atenção e erro usam cor mais texto, nunca apenas cor. A senha Wi-Fi permanece mascarada e o teclado compartilhado possui página de símbolos (`@`, `#`, `!`, hífen, sublinhado e demais caracteres usuais).

Loading de pagamento, Wi-Fi, orientação e offline usa `BrandLoader` (ver Marca e movimento), sempre acompanhado de texto e timeout. Erros retornam ações `TENTAR NOVAMENTE`/`VOLTAR`; nenhum spinner é um estado terminal.

## Textos

Os textos de interface ficam em `src/app247_terminal/ui/texts.py` (constantes simples, sem tradução). Regra das telas do cliente: um título e uma ação; detalhe técnico vai para telas de administrador ou para o log. Linhas de apoio vazias são ocultadas em vez de ocupar espaço.

- `SessionTimerLabel` fica oculto e só aparece nos últimos 60 s, com "Sessão prestes a encerrar". Deitado fica no cabeçalho; em pé (`follow_orientation`) ganha linha própria na largura toda, abaixo do cabeçalho ou do título, para não cortar o texto.
- Valores em reais vêm sempre de `format_brl` (`models/money.py`): `R$ 1.299,90`, com ponto no milhar e vírgula nos centavos. As telas não reformatam o texto devolvido.
- Inatividade na lista e na confirmação: "Ainda está aí?", "A compra será cancelada em N s" e `CONTINUAR` (`INACTIVITY_*`).
- Na tela da maquininha, a explicação sobre trocar a forma de pagamento só aparece em "PAGAMENTO AINDA NÃO CONCLUÍDO".
- Na recusa, o motivo só é exibido quando acrescenta algo ao título (cancelado, tempo esgotado, estornado).
- Falha de integridade e credencial bloqueada mostram "Terminal indisponível / Chame um atendente."; o motivo fica no log.

## Card de produto do carrinho

`ProductCard` (`ui/screens/terminal.py`), 280 px de altura, conteúdo alinhado à esquerda com 16 px de distância visual da borda nos quatro lados.

Identidade ("destaque de topo"): fundo `SURFACE_ELEVATED`, raio `Radius.CARD`, borda de 2 px em `CARD_BORDER_BRAND` (azul do logo a 70/255) e filete de 3 px no topo, azul `BRAND_BLUE` em 72% da largura e laranja `BRAND_ORANGE` no trecho final, lembrando as setas do logotipo. Filete e borda do recém-bipado são pintados no `paintEvent` do card, sem efeitos gráficos.


- topo: nome em `PRODUCT_NAME` (26 px), até três linhas com reticências na última, medido no `resizeEvent`. Com duas linhas o nome ocupa 68 px; a terceira usa o espaço livre acima do preço;
- centro: preço total da linha em `PRODUCT_PRICE` (34 px); só quando o valor não cabe na largura útil a fonte desce, 1 px por vez, até `PRODUCT_PRICE_MIN` (22 px). Em pé, até "R$ 1.299,90" fica em 34 px; "R$ 12.999,90" vai a 31 px e "R$ 123.456,78" a 28 px. Em promoção, o preço original fica acima, em `SMALL` (18 px), riscado e em `PRICE_ORIGINAL` (cinza-azulado, 5,2:1), e o preço atual passa para `BRAND_ORANGE_LIGHT`. Sem prefixos "De"/"Por". Com Qtd > 1, a linha "3 × R$ 3,76" (`CART_UNIT_PRICE`) mostra o preço unitário abaixo, em `SMALL` e `TEXT_SECONDARY`;
- selo no canto superior direito, `BRAND_ORANGE` com texto escuro: percentual de desconto arredondado para baixo ("-50%"; 33,7% vira "-33%"), para nunca anunciar mais desconto que o real. Sem percentual calculável, nome da promoção em maiúsculas, limitado a 40% da largura com reticências. A primeira linha do nome desconta a largura do selo;
- rodapé: "Qtd: N" em pílula (`QUANTITY_PILL`, azul do logo a 64/255, texto branco em `PRODUCT_QUANTITY`) à esquerda, centralizado com o botão de remover à direita. O botão tem área de toque de 56 px e contorno visível de 44 px (`TouchSize.REMOVE_VISUAL`), borda `ERROR`, fundo transparente e lixeira de 24 px; pressionado, fundo `PAYMENT_ACTION_DANGER`;
- leitura: o card lido recebe borda laranja de 3 px que some em `Motion.CARD_HIGHLIGHT` (600 ms), via `QVariantAnimation` (`ProductCard.highlight`). `APP247_ANIMATIONS=0` desliga.

## Marca e movimento

O kit fica em `src/app247_terminal/ui/brand.py`; cores e durações em `tokens.py`.

| Token | Valor | Uso |
|---|---|---|
| `Colors.BRAND_BLUE` / `BRAND_BLUE_DARK` | `#0073D5` / `#0A5FC4` | azul do logotipo (mediana dos pixels de `logo.png`) |
| `Colors.BRAND_ORANGE` / `BRAND_ORANGE_LIGHT` | `#FF8402` / `#FFB21C` | laranja do logotipo (mediana dos pixels de `logo.png`); destaque de marca e feedback de leitura |
| `Colors.CARD_BORDER_BRAND` / `QUANTITY_PILL` | `BRAND_BLUE` a 70 e 64/255 | borda do card do carrinho e pílula da quantidade |
| `Motion.CARD_HIGHLIGHT` | 600 ms | borda laranja do card recém-bipado |
| `Motion.FAST` / `BASE` / `SLOW` | 150 / 250 / 400 ms | microinteração / transição / confirmação |

Curva padrão: `QEasingCurve.OutCubic`. O laranja da marca marca a ação dominante de cada etapa (`variant="primary"` com `primaryAction="true"`), o valor do total no carrinho, a borda do total no resumo e o subtítulo de boas-vindas. `PRIMARY` azul segue nos demais botões primários, foco e bordas; o laranja não substitui os estados semânticos de pagamento.

- `BrandLogo` desenha o logotipo oficial `assets/images/logo.png`, recortado da margem transparente e decodificado uma única vez. Com `animated=True` ele respira num pulso de 5% a cada 2,4 s; só a tela de boas-vindas usa esse modo e ele para no `hideEvent`. Ativação, recuperação e cabeçalho do carrinho usam a versão estática.
- `BrandLoader` (dois arcos azul/laranja) substitui o spinner genérico e só roda enquanto visível.
- `AnimatedCheck` desenha o check da tela de pagamento aprovado.
- `flash(widget)` contorna em laranja o rodapé do total quando um item é lido (o card lido usa a borda própria, ver acima); `shake(widget)` balança o ícone da recusa.
- `FadeStackedWidget` troca a página de forma síncrona (índice, foco e toque imediatos) e esmaece por cima uma captura da página anterior.

Regras: nada de `QGraphicsEffect`; nenhuma camada de animação recebe toque ou foco; o valor do total nunca é animado, porque o texto do label é lido ao iniciar o pagamento. `APP247_ANIMATIONS=0` desliga todo o movimento.

## Aviso de inatividade

`InactivityPrompt` (`ui/inactivity.py`, estilo `Theme.inactivity_prompt_stylesheet()`) é o único aviso sobreposto das telas da compra:

- cobre só a área de conteúdo da tela (lista de produtos ou resumo) com `Colors.OVERLAY`; cabeçalho, relógio da sessão, total e botões de ação ficam fora dele;
- cartão `SURFACE_ELEVATED`, borda de 2 px `WARNING` e `Radius.MODAL`;
- título em H1, contagem em H3 na cor `WARNING`, `CONTINUAR` como ação primária laranja de 72 px;
- em pé (perfil compacto) empilha texto e botão, com no máximo 560 px; deitado põe o botão ao lado do texto, numa linha, com no máximo 880 px;
- o véu absorve o toque sobre o conteúdo: um toque só confirma presença e nunca aciona o item por baixo.

## Tempos da compra

Ficam no topo de `src/app247_terminal/models/purchase_session.py`:

| Constante | Valor | Uso |
|---|---:|---|
| `SESSION_LIMIT_SECONDS` | 600 s | teto da compra |
| `SESSION_WARNING_SECONDS` / `SESSION_CRITICAL_SECONDS` | 60 s / 30 s | relógio visível / crítico |
| `INACTIVITY_PROMPT_AFTER_SECONDS` | 90 s | "Ainda está aí?" na lista e na confirmação |
| `INACTIVITY_COUNTDOWN_SECONDS` | 20 s | contagem do aviso |
| `POST_PURCHASE_TIMEOUT_SECONDS` | 45 s | pagamento aprovado |
| `APP_PAYMENT_TIMEOUT_SECONDS` | 300 s | pagamento pelo aplicativo, limitado pelo teto |

## Estados de pagamento

Os resultados financeiros ocupam 100% da página; não usam card central:

| Semântica | Composição | Uso |
|---|---|---|
| `PAYMENT ATTENTION` | laranja `#C44D0A`, `alert.svg` branco, instrução H1 | cobrança aceita pela Point e ação necessária do cliente |
| `PAYMENT ERROR` | vermelho `#D92D20`, `error.svg` branco, título + motivo H2, ação inferior | somente falha financeira definitiva |
| `PAYMENT SUCCESS` | verde `#087A4F`, `checked.svg` branco, total e ações | somente aprovação definitiva |

`ColoredSvgLabel`/`render_colored_svg` renderizam os SVGs monocromáticos como máscara em memória. Isso cobre `fill`, `stroke` e preto implícito, resolve o path por `PROJECT_ROOT/icon` e não altera nem duplica os assets.

Loading/preparação permanece no fundo neutro com indicador imediato. `PENDING`, `WAITING_PAYMENT` e `PROCESSING` nunca recebem a tela vermelha. Offline também não é recusa financeira.

Na tela verde, `FINALIZAR` é a ação primária clara; CPF, e-mail e WhatsApp são secundárias. Todos os alvos medem pelo menos 60 px. Sem toque, a tela finaliza sozinha em 45 s ("Finalizando em mm:ss"), pausando enquanto o comprovante é digitado ou enviado.

Hover é um refinamento para desenvolvimento; `pressed`, `disabled`, texto e contraste funcionam sem hover.

## Estrutura

A única `MainWindow` chama `showFullScreen()`. Páginas vivem no mesmo `QStackedWidget`, usam layouts e `QSizePolicy.Expanding`. Lista de produtos e resumo usam `QScrollArea`; total e ações ficam fora do scroll. Tamanho fixo só é aceito no botão compacto de remover (56 × 56), cuja área de toque é deliberadamente estável.

Validação mínima: display físico prioritário de 7 polegadas em `1024×600`, além de `768x1360` portrait e `800x480` landscape de desenvolvimento. Em `1024×600`, o carrinho usa três cards de `292×224` por linha e scroll somente vertical. Menu administrativo, lista Wi-Fi, senha/teclado e orientação foram renderizados e inspecionados offscreen nessa resolução.
