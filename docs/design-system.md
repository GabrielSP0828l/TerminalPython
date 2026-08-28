# Design System — Terminal App 24/7

Voltar para [[00-index]]. Layout portrait em [[layout-vertical]] e inventário em [[telas]].

Esta é a única referência visual do Terminal. A fonte de verdade executável está em `styles/tokens.py` e `styles/theme.py`; telas não mantêm QSS próprios. O padrão foi extraído das telas históricas mais maduras (boas-vindas e carrinho) e consolidado com os estados Point já funcionais.

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

## Estados de pagamento

Os resultados financeiros ocupam 100% da página; não usam card central:

| Semântica | Composição | Uso |
|---|---|---|
| `PAYMENT ATTENTION` | laranja `#C44D0A`, `alert.svg` branco, instrução H1 | cobrança aceita pela Point e ação necessária do cliente |
| `PAYMENT ERROR` | vermelho `#D92D20`, `error.svg` branco, título + motivo H2, ação inferior | somente falha financeira definitiva |
| `PAYMENT SUCCESS` | verde `#087A4F`, `checked.svg` branco, total e ações | somente aprovação definitiva |

`ColoredSvgLabel`/`render_colored_svg` renderizam os SVGs monocromáticos como máscara em memória. Isso cobre `fill`, `stroke` e preto implícito, resolve o path por `PROJECT_ROOT/icon` e não altera nem duplica os assets.

Loading/preparação permanece no fundo neutro com indicador imediato. `PENDING`, `WAITING_PAYMENT` e `PROCESSING` nunca recebem a tela vermelha. Offline também não é recusa financeira.

Na tela verde, `FINALIZAR` é a ação primária clara; CPF, e-mail e WhatsApp são secundárias. Todos os alvos medem pelo menos 60 px. O resultado não possui reset automático: somente `FINALIZAR` chama o reset central.

Hover é um refinamento para desenvolvimento; `pressed`, `disabled`, texto e contraste funcionam sem hover.

## Estrutura

A única `MainWindow` chama `showFullScreen()`. Páginas vivem no mesmo `QStackedWidget`, usam layouts e `QSizePolicy.Expanding`. Lista de produtos e resumo usam `QScrollArea`; total e ações ficam fora do scroll. Tamanho fixo só é aceito no botão compacto de remover (56 × 56), cuja área de toque é deliberadamente estável.

Validação mínima: `768x1360` portrait e `1024x600`/`800x480` landscape de desenvolvimento.
