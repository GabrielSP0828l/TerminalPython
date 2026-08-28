# Orientação do display

Voltar para [[00-index]]. Acesso em [[menu-administrativo]], regras de layout em [[layout-vertical]] e arquitetura em [[arquitetura]].

## Fluxo

```text
menu administrativo autenticado
  -> ORIENTAÇÃO DA TELA
      -> DisplayScreen
          -> DisplayWorker / QThread
              -> DisplayService
                  -> wlr-randr (Wayland/wlroots)
                  -> xrandr (somente sessão X11)
```

O administrador escolhe `HORIZONTAL` ou `VERTICAL`; nomes técnicos como transform `90`/`270` não são apresentados. Widgets não são girados e a janela não simula a orientação com tamanho fixo. O compositor altera a saída e `MainWindow` reaplica fullscreen/geometry para que os layouts Qt respondam à nova área.

## Detecção e aplicação

`service/DisplayService.py` detecta a sessão gráfica, a ferramenta compatível e a primeira saída ativa. `DISPLAY_OUTPUT` pode selecionar explicitamente uma saída em instalação com múltiplos monitores. Não existe `HDMI-A-2` hardcoded.

- Wayland requer `wlr-randr`; `xrandr` visto através de XWayland não é usado como fallback inseguro.
- X11 pode usar `xrandr`.
- vertical usa transform `90` por padrão; `DISPLAY_TRANSFORM=270` atende montagem física oposta.
- comandos usam lista de argumentos, sem `shell=True`, e timeout de 8 s.
- ferramenta/saída ausente e timeout geram mensagem amigável sem derrubar a aplicação.

Uma compra ou pagamento ativo bloqueia a alteração. Isso evita modificar a geometria no meio do carrinho e preserva qualquer cobrança já enviada.

## Persistência e boot

Após aplicação bem-sucedida, a escolha semântica é gravada atomicamente em `db/display_orientation` (`horizontal` ou `vertical`). Esse arquivo operacional está ignorado pelo Git.

`start.sh` seleciona o Python e, antes de iniciar `main.py`, chama `python -m service.DisplayService --apply-saved`. A orientação também pode ser sobrescrita para uma execução com `DISPLAY_ORIENTATION`. Se o comando falhar, o script registra aviso e inicia o Terminal; não há loop nem bloqueio infinito.

## Ambiente auditado e validação física

O host de desenvolvimento estava em Wayland/GNOME, sem `wlr-randr`; `xrandr` enxergava apenas uma saída virtual XWayland. O serviço recusou corretamente essa combinação. Detecção `HDMI-A-2`, transforms, persistência e fallback X11 foram testados com subprocessos simulados.

No Raspberry/labwc ainda é obrigatório validar a saída real, sentido físico 90/270, atualização da geometria PyQt, calibração do touchscreen e persistência após reboot.
