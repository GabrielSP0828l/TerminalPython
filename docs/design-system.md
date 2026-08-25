# Design System — Terminal App 24/7

Voltar para [o índice](00-index.md).

Este documento é a referência oficial para novas telas e alterações visuais do Terminal Python. O padrão foi extraído das interfaces existentes mais maduras; não substitui a identidade atual. A implementação central está em `styles/tokens.py` e `styles/theme.py`.

## Telas de referência

- **TerminalScreen:** controles de toque, tipografia Segoe UI, azul de ação `#169DFF`, texto informativo azul-claro e raios compactos.
- **TelaBemVindos:** composição fullscreen, página/card expansíveis, fundo azul-marinho e conteúdo centralizado.
- **CadastroTerminalScreen:** referência estrutural responsiva após a correção para `1024x600`, `800x480` e retrato; é a primeira tela integralmente migrada ao tema.

As telas de pagamento e PIX foram analisadas, mas não são referência integral por ainda possuírem QSS local e cores de estado divergentes.

## Auditoria visual do estado anterior

A inspeção de todas as telas e folhas em `css/` encontrou 143 ocorrências de cores literais no recorte de arquivos Python/CSS. As inconsistências principais são:

- famílias próximas de azul-marinho usadas sem um papel semântico definido;
- três vermelhos e múltiplos verdes para o mesmo tipo de feedback;
- fontes Segoe UI, DejaVu Sans e Consolas escolhidas localmente, sem fallback uniforme;
- QSS de botões repetido em telas e também sobrescrito por widget;
- raios de botão entre 8 e 16 px e de card entre 18 e 28 px;
- margens, paddings e tamanhos de fonte sem escala compartilhada;
- inputs de login/teclado com foco, erro e disabled diferentes;
- telas de confirmação, PIX, pagamento e overlay com estados equivalentes representados de maneiras distintas;
- ícones misturando imagens e símbolos Unicode sem regra de tamanho/alinhamento;
- QSS inline que dificulta corrigir contraste ou identidade sem editar várias classes.

Esses estilos legados não foram removidos nesta etapa. A migração gradual evita alterar de uma vez telas operacionais já estáveis.

## Paleta oficial

| Token | Cor | Uso |
| --- | --- | --- |
| `BACKGROUND_PRIMARY` | `#08111F` | Fundo principal das páginas |
| `BACKGROUND_SECONDARY` | `#03111F` | Fundo profundo e gradientes existentes |
| `SURFACE` | `#071C33` | Cards e painéis |
| `SURFACE_ELEVATED` | `#0D253F` | Superfícies destacadas/modais |
| `SURFACE_HOVER` | `#102748` | Hover em superfícies interativas |
| `PRIMARY` | `#169DFF` | Ação principal e foco |
| `PRIMARY_HOVER` | `#39B8FF` | Hover da ação principal |
| `PRIMARY_PRESSED` | `#0D8CFF` | Ação principal pressionada |
| `SECONDARY` / `INFO` | `#62C8FF` | Ações secundárias e informação |
| `TEXT_PRIMARY` | `#FFFFFF` | Texto de maior hierarquia |
| `TEXT_SECONDARY` | `#8DD4FF` | Subtítulos e texto auxiliar destacado |
| `TEXT_MUTED` | `#8B949E` | Metadados e legendas |
| `TEXT_DISABLED` | `#7F97B7` | Conteúdo desabilitado |
| `TEXT_ON_PRIMARY` | `#03111F` | Texto sobre fundos claros/primários |
| `BORDER` | `#17324D` | Bordas de cards e controles |
| `DIVIDER` | `#30363D` | Separadores discretos |
| `SUCCESS` | `#00D084` | Aprovação, online e conclusão |
| `WARNING` | `#E0B54A` | Atenção, processamento e cancelamento |
| `ERROR` | `#FF4D4D` | Recusa, offline e falha |

Cor nunca é a única informação de estado: texto, ícone e contexto continuam obrigatórios.

## Tipografia

A família preferencial é `Segoe UI`, com fallback `DejaVu Sans`, disponível normalmente no Raspberry Pi/Linux. Identificadores técnicos usam `Consolas`, com fallback `DejaVu Sans Mono`. Não há dependência de fonte externa.

| Estilo | Tamanho | Peso | Uso |
| --- | ---: | ---: | --- |
| Display | 48 px | 700 | Número/resultado excepcional |
| H1 | 32 px | 700 | Título principal da tela |
| H2 | 28 px | 700 | Título de seção ou card |
| H3 | 22 px | 600 | Subseção |
| Body | 18 px | 400 | Texto normal |
| Label | 16 px | 600 | Rótulo de campo |
| Small | 14 px | 400 | Texto auxiliar |
| Caption | 13 px | 400 | Metadados compactos |
| Button | 18 px | 700 | Texto de botão |

Em resoluções menores, prefira reflow e redução de espaços antes de reduzir o texto essencial.

## Espaçamento e raios

Escala de espaçamento: `XS=4`, `SM=8`, `MD=12`, `LG=16`, `XL=24`, `XXL=32` e `XXXL=48` px. Margens, padding e distância entre widgets devem usar esses valores sempre que possível.

| Token | Valor | Uso |
| --- | ---: | --- |
| `SMALL_RADIUS` | 8 px | Tags e elementos compactos |
| `INPUT_RADIUS` | 12 px | Inputs |
| `BUTTON_RADIUS` | 12 px | Botões |
| `CARD_RADIUS` | 18 px | Cards e painéis |
| `MODAL_RADIUS` | 24 px | Modal/overlay elevado |

## Botões

Botões de toque usam altura mínima de 48 px, padding horizontal de 24 px, fonte Button e raio de 12 px.

- **Primary:** fundo `PRIMARY`; ação dominante da página.
- **Secondary:** superfície elevada, borda `SECONDARY`; ação alternativa.
- **Danger:** fundo `ERROR`; operação destrutiva ou irreversível.
- **Ghost/Text:** fundo transparente, texto `TEXT_SECONDARY`; voltar, fechar ou ação de baixa ênfase.

Cada variante possui hover, pressed e disabled. O disabled usa `DISABLED_BACKGROUND` e `TEXT_DISABLED`, não apenas menor opacidade. Em código, aplique `button.setProperty("variant", "primary")` (ou `secondary`, `danger`, `ghost`) e use o stylesheet central.

## Inputs

Inputs usam altura mínima de 48 px, fundo de input, borda de 2 px, padding horizontal de 16 px e raio de 12 px. Placeholder usa `INPUT_PLACEHOLDER`; foco usa borda `PRIMARY`; erro usa borda `ERROR`; disabled/read-only usam fundo e texto desabilitados.

Use `input.setProperty("role", "input")`. Para erro, aplique `input.setProperty("state", "error")`, repolindo o widget se a propriedade mudar após sua exibição. A mensagem de erro deve permanecer textual e próxima ao campo.

## Cards, containers e modal

- **Card:** `SURFACE`, borda `BORDER`, raio 18 px, padding recomendado 24 px.
- **Painel de informação:** `SURFACE_ELEVATED`, borda `BORDER`, raio 12–18 px.
- **Modal:** superfície elevada, raio 24 px, overlay escuro; deve manter ação clara de saída.
- **Resumo do carrinho:** card com linhas separadas por `DIVIDER`, total com hierarquia H2/H3.

Use `QFrame` com propriedade `role="card"` ou `role="information"`. Sombras devem ser discretas e não substituir bordas/contraste.

## Estados do sistema

| Estado funcional | Token visual | Apresentação |
| --- | --- | --- |
| `APPROVED`, online | `SUCCESS` | ícone + texto de confirmação |
| `PROCESSING`, loading | `INFO` ou `WARNING` | mensagem de espera + indicador ativo |
| `REJECTED` | `ERROR` | ícone + explicação e próxima ação |
| `CANCELLED` | `WARNING` | texto explícito de cancelamento |
| offline/falha | `ERROR` | texto de indisponibilidade e recuperação |

Labels reutilizáveis usam a propriedade `state`: `success`, `warning`, `error`, `info` ou `loading`. Loading não deve bloquear a UI; combine texto e indicador visual. Componentes desabilitados não devem responder a toque nem parecer ativos.

## Estrutura fullscreen

A aplicação mantém uma única `MainWindow` fullscreen e páginas dentro de um `QStackedWidget` expansível. As páginas não devem abrir janelas próprias nem chamar `showFullScreen()` individualmente.

Estrutura recomendada:

```text
Página expansível
├── header (título, estado global ou navegação)
├── conteúdo com stretch/reflow
└── footer/actions, quando necessário
```

Use layouts Qt, `QSizePolicy.Expanding` onde o conteúdo deve crescer e stretches para distribuição. Evite `setGeometry`, `move`, tamanhos fixos e margins grandes que excedam `1024x600`. Scroll só é apropriado quando o conteúdo é genuinamente maior que a área disponível. O mínimo de validação visual é `1024x600`, `800x480`, `600x1024` e resize em runtime.

## Ícones

O projeto usa imagens existentes e símbolos Unicode; nenhuma biblioteca nova é necessária. Ícones de ação devem ficar normalmente entre 20 e 24 px, alinhados ao texto e com espaçamento `SM`. Ícones centrais de estado podem crescer conforme o layout, mas devem manter proporção. Use significado consistente para voltar, carrinho, pagamento, sucesso e erro e sempre forneça texto acessível junto ao símbolo.

## Reutilização e adoção

`styles/tokens.py` é a fonte de verdade visual. `styles/theme.py` produz o QSS comum e estilos específicos de páginas durante a adoção gradual. Não replique hexadecimal em telas; crie um token semântico somente quando houver uso estável e distinto.

Situação atual:

- cadastro/ativação: migrado para `Theme.activation_stylesheet()`;
- componentes comuns: variantes de botão, input, card e estado disponíveis;
- demais telas: preservadas, aguardando migração individual com teste visual e funcional.

Uma migração futura não deve alterar navegação, chamadas HTTP, carrinho, pagamento ou qualquer regra de negócio.
