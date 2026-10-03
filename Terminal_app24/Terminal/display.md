# Orientação do display

Voltar para [[00-index]]. Acesso em [[menu-administrativo]], telas em [[telas]] e lifecycle em [[arquitetura]].

## Arquitetura executável

```text
ConfiguracaoScreen / ORIENTAÇÃO DA TELA
  -> DisplayScreen
      -> DisplayWorker (QThread)
          -> DisplayService
              -> wlr-randr em Wayland/wlroots
              -> xrandr somente em X11
```

O painel expõe `HORIZONTAL` e `VERTICAL`. Não gira widgets nem simula orientação por tamanho fixo. `DisplayService` detecta sessão, ferramenta e primeira saída ativa; `DISPLAY_OUTPUT` resolve instalações com múltiplas saídas. Não existe output hardcoded.

Vertical usa `90` por padrão e aceita `DISPLAY_TRANSFORM=270`. Todos os comandos usam argv, sem shell, com timeout de oito segundos. Wayland sem `wlr-randr` falha de forma segura e não usa `xrandr` através de XWayland. Ferramenta/saída ausente ou falha retornam mensagem amigável.

Compra ou pagamento ativo bloqueia a mudança. Após sucesso, `MainWindow` reaplica fullscreen/geometry para os layouts responderem à área do compositor.

## Persistência

A escolha é gravada atomicamente em `db/display_orientation`. `start.sh` chama `python -m service.DisplayService --apply-saved` antes de `main.py`; erro gera aviso e não impede o Terminal de iniciar. `DISPLAY_ORIENTATION` pode sobrescrever uma execução.

O host auditado era Wayland/GNOME sem `wlr-randr`, e o serviço recusou corretamente o `xrandr` virtual. Testes simulam `HDMI-A-2`, 90/normal, X11, ferramenta ausente, timeout e reapply no boot. No Raspberry/labwc ainda é obrigatório validar output real, sentido 90/270, geometria Qt, calibração touch e reboot.
