# Telas e navegação

Voltar para [o índice](00-index.md).

## Padrão visual obrigatório

Novas telas e alterações visuais devem seguir o [Design System](design-system.md). Cores, tipografia, espaçamentos e raios são definidos em `styles/tokens.py`; variantes reutilizáveis de componentes são fornecidas por `styles/theme.py`. Hexadecimais e QSS completos não devem ser duplicados dentro das telas quando já existir um token ou uma variante semântica.

A adoção é gradual. Nesta etapa, `CadastroTerminalScreen` é a primeira tela integralmente ligada ao tema oficial. As demais telas continuam preservadas até migrações isoladas e testadas.

`PagamentoScreen` e `ConfirmacaoScreen` também adotam o tema oficial nos novos estados Point.

## Container principal e fullscreen

A aplicação possui uma única janela de nível superior: `MainWindow(QMainWindow)`, em `main.py`. Seu `centralWidget` contém um `QStackedWidget` dentro de `QVBoxLayout` sem margins ou spacing. O stacked usa `QSizePolicy.Expanding` nos dois eixos.

Todas as telas são páginas `QWidget` adicionadas ao mesmo `QStackedWidget`. Portanto nenhuma página chama `show()`, `showFullScreen()` ou cria janela própria. A navegação troca somente `setCurrentWidget()` e preserva o estado fullscreen da janela principal.

No entrypoint, a janela é aberta uma única vez com:

```python
window.showFullScreen()
```

O `window.show()` redundante que existia depois dessa chamada foi removido para deixar um único mecanismo de exibição.

## Resolução e adaptação

Não existe arquivo versionado de configuração de vídeo do Raspberry Pi que fixe a resolução. O código contém referência histórica a `1024x600`, e essa resolução foi adotada como validação mínima em paisagem. Também é validado o modo retrato `600x1024`.

Scaling explícito no startup:

```text
QT_AUTO_SCREEN_SCALE_FACTOR=0
QT_SCALE_FACTOR=1
```

O cadastro não fixa tamanho próprio. Ele herda a área disponível do stacked e reorganiza o conteúdo conforme a largura.

## CadastroTerminalScreen

- **Arquivo:** `telas/CadastroTerminalScreen.py`.
- **Classe:** `CadastroTerminalScreen(QWidget)`.
- **Abertura:** criada por `MainWindow`; selecionada como primeira página quando `Terminal.is_activated()` é falso.
- **Pai:** `MainWindow` durante construção; depois gerenciada pelo `QStackedWidget`.
- **Política:** `QSizePolicy.Expanding` horizontal e vertical.
- **Layout raiz:** `QVBoxLayout`, sem constraint fixa, margins de 24 px e card com stretch.
- **Card:** `QFrame#activationCard`, expansível nos dois eixos.
- **Conteúdo:** título e subtítulo no topo; corpo em `QGridLayout` responsivo.

### Comportamento responsivo

Para largura igual ou superior a 760 px:

```text
Título / subtítulo
QR Code | identificação + status
```

Para largura inferior a 760 px:

```text
Título / subtítulo
QR Code
identificação + status
```

O QR mantém proporção e é recalculado no `resizeEvent`; não possui tamanho fixo. O limite considera largura e altura disponíveis para evitar corte em `1024x600`, `800x480` e orientação retrato.

## Referências visuais

### TelaBemVindos

Usada como referência de:

- página e card expansíveis;
- navegação como página do stacked;
- fundo azul-escuro;
- centralização e espaçamento;
- ausência de geometry fixa na página.

### TerminalScreen

Usada como referência de:

- tipografia `Segoe UI`;
- gradiente `#071c33` → `#03111f`;
- azul `#169dff` e texto secundário `#8dd4ff`;
- border-radius entre 12 e 18 px;
- aproveitamento integral do container.

O cadastro não introduz uma identidade visual independente.

## Componentes do cadastro

- título e subtítulo com alinhamento central;
- QR em label expansível, com fundo/borda branca;
- identificação em fonte monoespaçada;
- status expansível e com variante visual de erro;
- não existem inputs ou botões nessa página: o cadastro administrativo ocorre pelo QR e a ativação é detectada por polling.
- o stylesheet vem de `Theme.activation_stylesheet()`; estados de status usam a propriedade dinâmica `state` (`info`, `loading`, `success` ou `error`).

## Navegação

```text
Aplicação
  -> reset pendente (se existir)
  -> valida terminal.json
      -> não ativado: CadastroTerminalScreen
      -> ativado: TelaBemVindos

CadastroTerminalScreen
  -> backend responde activated=true
  -> persiste terminal
  -> inicia operação
  -> TelaBemVindos
```

## Fluxo de compra

```text
TelaBemVindos
  -> TerminalScreen (scanner e lista)
      -> PAGAR AGORA: PagamentoScreen
          -> loading
          -> aguardando maquininha/confirmação
          -> aprovado: ConfirmacaoScreen -> reset -> TelaBemVindos
          -> não confirmado: TerminalScreen com itens preservados
      -> PAGAR NO APP: AppPaymentScreen -> TerminalScreen ao cancelar
```

### TerminalScreen

Quantidade é incrementada somente por scans repetidos. Os controles manuais `+` e `-` foram removidos. `x` remove a linha inteira. O primeiro scan inicia o prazo global.

### PagamentoScreen

A antiga seleção Crédito/Débito/PIX foi removida. A classe é agora uma única página fullscreen de preparação e espera Point. Exibe loading, instrução física para a maquininha, countdown global e mensagem de falha segura. Não há janela independente.

### ConfirmacaoScreen

Tela existente reutilizada para “Pagamento aprovado / Compra concluída”. Usa o design system, permanece cinco segundos e chama `MainWindow.reset_compra()` antes de liberar uma nova compra.

### AppPaymentScreen

Preservada para “Pagar no App”. A rede usa worker Qt, o QR é aplicado na UI thread e o countdown compartilha `CompraSession`.

A troca de página não altera o window state. Se o cadastro voltar a ser primeira tela após reset, ele ocupa novamente toda a área do stacked.

## Testes de layout

`tests/test_cadastro_layout.py` cobre:

- expansão em `1024x600`;
- reflow em `600x1024`;
- reflow após resize em runtime;
- política expansível da página/card;
- título, subtítulo, QR, identificação e status dentro dos limites visíveis.

Um smoke test adicional instancia `MainWindow` não ativada, aplica fullscreen e confirma que o cadastro é a página atual e que o stacked acompanha o `centralWidget`.
