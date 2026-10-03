# Modo kiosk

Atualizado em 27 de setembro de 2026. Relacionados: [[telas]], [[display]] e [[wifi]].

## Ambientes

- `APP_ENV=development`: janela normal fixa em `1024x600`; `fullscreen=False`.
- `APP_ENV=production`: `showFullScreen()` real; `fullscreen=True`.
- valor ausente ou inválido assume `development`, evitando kiosk acidental em estação de desenvolvimento.

`refresh_display_geometry` preserva o modo: não promove desenvolvimento para fullscreen e não rebaixa produção para janela normal.

## Saída

`ESC` é consumido. `Alt+F4` e `closeEvent` acidental são recusados enquanto `_shutdown_authorized` é falso. A saída legítima passa por senha administrativa, confirmação e `encerrar_terminal`, que autoriza o fechamento e encerra serviços.

## Pré-ativação

A tela de ativação oferece `CONFIGURAR WI-FI`. Esse caminho abre diretamente somente `WifiScreen`; `show_menu` continua bloqueado sem autenticação, portanto display, reset e saída administrativa não são expostos. `WifiService` usa `subprocess` com argv separado, senha via stdin, timeout e mensagens sanitizadas; a senha não vai ao SQLite nem ao log.

Os testes offscreen validam ambos os modos e geometria `1024x600`. Compositor, touch, `Alt+F4` real e fullscreen no Raspberry ainda exigem validação física.
