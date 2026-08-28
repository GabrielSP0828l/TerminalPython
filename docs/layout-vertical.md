# Layout vertical e rotação do display

Voltar para [[00-index]]. Componentes em [[design-system]] e páginas em [[telas]].

## Responsabilidades

O sistema/compositor gira o display físico. O PyQt mantém `showFullScreen()` e organiza a área que recebe, por exemplo `QSize(768, 1360)`. Alterar `setFixedSize()` ou girar widgets não substitui a rotação do monitor.

## Inicialização opcional

Quando existe `db/display_orientation`, `start.sh` reaplica a escolha administrativa antes de iniciar o PyQt. Para sobrescrever somente uma execução:

```bash
DISPLAY_ORIENTATION=vertical ./start.sh
```

`DisplayService` usa `wlr-randr` em Wayland/wlroots e `xrandr` somente em X11. A primeira saída ativa é detectada, sem hardcode de `HDMI-A-2`. Ambientes com múltiplas saídas devem explicitar:

```bash
DISPLAY_ORIENTATION=vertical DISPLAY_OUTPUT=HDMI-A-2 DISPLAY_TRANSFORM=90 ./start.sh
```

`DISPLAY_TRANSFORM=270` pode ser usado quando o sentido físico exigir. Falha de detecção/rotação gera aviso e o Terminal inicia normalmente. Cada comando tem timeout de oito segundos. `PYTHON_BIN` permite selecionar o Python/venv. A escolha também pode ser feita por touchscreen em [[display]].

## Comportamento da UI

- prioridade: `768x1360` portrait;
- fallback testado: `1024x600` e `800x480` landscape;
- conteúdo principal em `QVBoxLayout`;
- listas em scroll; total e ação fora do scroll;
- cards/QR redimensionados no `resizeEvent` quando necessário;
- nenhuma página usa `setGeometry()` ou `move()`;
- único tamanho fixo deliberado: remover produto 56 × 56.

## Validação

Testes offscreen instanciam boas-vindas, ativação, configuração, carrinho, confirmação, pagamento, aprovado, erro, login legado, teclado, pagamento no app e offline em `768x1360`. O display físico ainda deve ser validado para confirmar nome da saída, sentido 90/270, escala e calibração touch.
