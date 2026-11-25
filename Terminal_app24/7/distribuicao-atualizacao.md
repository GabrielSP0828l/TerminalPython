# Distribuição, build e atualização

Voltar para [[00-index]]. Arquitetura de código em [[arquitetura]] e estado em
[[sqlite]].

`app247-terminal.spec` gera PyInstaller `onedir` com assets e dependências
dinâmicas. `scripts/build.sh` não faz cross-compile: o pacote final do Raspberry
Pi 4 precisa ser construído em Linux ARM64/aarch64.

Em `aarch64`, o script detecta o host e usa um venv dedicado criado com
`--system-site-packages`, validando que `PyQt5`/`QtSvg` vêm do
`python3-pyqt5` do Raspberry Pi OS. `requirements-arm64.txt` instala apenas as
dependências restantes e evita tentar obter PyQt5 por pip. O script não chama
`sudo` ou `apt` automaticamente.

Produção separa release (`/opt/app247/releases`), ponteiro ativo
(`/opt/app247/current`), estado (`/var/lib/app247`) e ambiente
(`/etc/app247/terminal.env`). Uma troca de release não alcança SQLite,
identidade ou credencial do dispositivo. A chave pública de atualização fica em
`/etc/app247/update-signing-public-key.pem`, também fora da release.

`scripts/install.sh` não sobrescreve dados/configuração. A primeira execução
prepara uma release imutável e cria `terminal.env` pelo template de produção;
uma segunda execução da mesma versão com `--activate` é aceita sem recopiar o
artefato. A ativação troca o symlink, executa `app247-terminal --check`, restaura
a release anterior se o diagnóstico falhar e só então instala uma unit
`systemd --user` para o usuário gráfico, em vez de executar a GUI como serviço
de sistema. Ela é habilitada para o próximo login e é iniciada/reiniciada quando
o bus da sessão estiver disponível. Usuário, grupo, paths e controle possuem
overrides `APP247_*`; com `APP247_MANAGE_SYSTEMD=false` a unit é instalada sem
operar o daemon do usuário.

O diagnóstico é não destrutivo e valida URLs/placeholders, `terminal.env`,
configuração de segurança, assets, diretório persistente, `PRAGMA
integrity_check`, credencial individual, `GET /terminal/health`, versão e symlink.
SQLite e credencial ainda ausentes são avisos esperados no primeiro boot; erros
bloqueiam a ativação.

`updater/` valida SemVer, manifesto JSON canônico
assinado com Ed25519, chave pública confiável, nome/arquitetura, SHA-256 e plano
de staging/rollback; não baixa, para serviço ou ativa versão. A chave privada
fica somente no cofre do pipeline e nunca no Terminal/repositório.

Antes da automação real ainda são obrigatórios download autenticado, guarda de
pagamento, health-check pós-start, rollback atômico e procedimento de rotação da
trust anchor. A GUI não usa mais um usuário dedicado de serviço: ela sempre roda
na sessão gráfica descoberta, nunca presume `pi` ou UID fixo.

## Pacote oficial standalone

`scripts/package-release.sh <SemVer>` é o único orquestrador local do pacote.
Ele exige que o `onedir` já exista e que sua versão interna seja idêntica à
solicitada. A arquitetura de distribuição usa o nome Debian retornado por
`dpkg --print-architecture` (`armhf`, `arm64` ou `amd64`), com fallback por
`uname`; `file` inspeciona o ELF e qualquer divergência host/binário aborta.

O diagnóstico de build usa `APP247_DIAGNOSTIC_MODE=release`: assets, paths e o
bundle continuam verificados, mas nenhuma credencial real ou chamada ao backend
é exigida. Esse modo não é usado pela ativação de produção.

O tar contém uma única raiz `app247-terminal-<versão>/`, o `app/` PyInstaller
completo, instalador, unit, launcher, template, `VERSION`, `RELEASE_INFO.json` e
a chave pública. A chave pública só viaja no invólucro bootstrap e é instalada
como trust anchor em `/etc/app247`; não entra na release imutável em `/opt`. A
chave privada vem de `APP247_UPDATE_PRIVATE_KEY`, nunca entra no staging e nunca
é copiada para `release/`.

O manifesto schema 1 preserva os campos anteriores e aceita os metadados
assinados opcionais `size` e `signatureAlgorithm=Ed25519`. A assinatura continua
embutida para o updater e é também exportada, sem recalculá-la, no arquivo
`.manifest.json.sig`. `verify-release.sh` reutiliza o verificador Ed25519,
recalcula SHA-256/tamanho, extrai em temporário, compara arquitetura e trust
anchor, rejeita estado/segredos e executa o instalador standalone em sandbox.

## Instalador e sessão gráfica

No pacote, `install.sh` resolve `SCRIPT_DIR`, lê `VERSION` e copia somente
`app/`. Release existente é aceita apenas quando `diff -qr` confirma conteúdo
idêntico; estado parcial/divergente aborta sem sobrescrita. O template só cria
`/etc/app247/terminal.env` quando ausente. `/var/lib/app247` e `/etc/app247`
nunca são removidos; usuário/grupo `app247` são criados em uma máquina nova e
os arquivos operacionais conhecidos permanecem sem leitura pública.

`app247-terminal-launcher` carrega `/etc/app247/terminal.env`, usa o UID efetivo
da sessão — nunca `1000` —, valida `XDG_RUNTIME_DIR`, espera e descobre um socket
Wayland pertencente ao usuário quando necessário, configura Qt/DBus e executa
`/opt/app247/current/app247-terminal`. X11 é fallback somente com socket local
válido. Um lock por sessão impede segunda instância; `--apply-display` não pega
o lock pois é operação CLI isolada.

`--apply-display` é o `ExecStartPre` da unit e tem caminho próprio no launcher:
aceita só esse argumento (outro → código 2), espera a sessão no máximo
`APP247_APPLY_DISPLAY_SESSION_WAIT_SECONDS` (padrão 10 s) e executa
`app247-terminal --apply-display` sob `timeout` de
`APP247_APPLY_DISPLAY_TIMEOUT_SECONDS` (padrão 20 s). O launcher das releases
1.0.0/1.0.1 terminava com `exec "$EXECUTABLE"` e descartava os argumentos: o
pré-start abria a GUI inteira e o systemd o matava após 90 s, em loop (BUG-053).
A GUI nunca é iniciada pelo caminho `--apply-display`.

Units de usuário instaladas antes do marcador `# Managed by App247` são
reconhecidas pela `Description` e pelo `ExecStart` do App247, preservadas como
`app247-terminal.service.legacy-<data>` e substituídas. Unit com o mesmo nome e
sem essas marcas continua recusada. Drop-ins em `app247-terminal.service.d/` que
redefinem `ExecStart`/`ExecStartPre` geram aviso e não são alterados.

No `--activate`, o instalador também grava
`/etc/NetworkManager/conf.d/app247-wifi-powersave.conf` (`wifi.powersave = 2`),
mantendo a economia de energia do Wi-Fi desligada em todo perfil com
`powersave=default`, inclusive redes criadas pela tela Wi-Fi. Não reinicia a
rede; vale na próxima ativação da conexão ou após `nmcli general reload conf`.
`APP247_WIFI_POWERSAVE=keep` desativa a política e arquivo não gerenciado não é
sobrescrito. Ver [[wifi]].

O atalho **Terminal 24/7** e o autostart usam o logo da release: o instalador
copia `_internal/assets/images/logo.png` para
`/usr/local/share/pixmaps/app247-terminal.png` (fora de `releases/`, válido após
rollback) e grava `Icon=` com esse caminho; sem logo, usa `computer`. O atalho
manual das instalações 1.0.0/1.0.1 (`App247 Terminal.desktop`, que chamava o
launcher fora da unit) é movido para `~/.local/share/app247/legacy-desktop/`,
evitando dois atalhos; outros arquivos da área de trabalho não são tocados.

No Raspberry Pi OS o pcmanfm pergunta "Executar / Executar no Terminal" para
todo `.desktop` da área de trabalho. O instalador grava `quick_exec=1` em
`~/.config/libfm/libfm.conf` do usuário gráfico (preservando as outras chaves;
`APP247_DESKTOP_QUICK_EXEC=false` desativa) para o atalho abrir com um toque.
Vale no próximo login ou após `pcmanfm --reconfigure` (BUG-057).

Rollback do `--activate`: antes de gravar qualquer arquivo fora de `releases/`,
o instalador guarda um snapshot temporário de launcher, unit, link de enable,
política de Wi-Fi, ícone, atalhos e autostart. Se algo falhar depois da troca de
`current`, esses caminhos voltam ao estado anterior (ou são removidos, se não
existiam) junto com o symlink, e a unit anterior é recarregada antes do restart.

`systemctl --user stop`, reboot e `poweroff` enviam `SIGTERM`: o Terminal faz o
mesmo encerramento cooperativo do painel administrativo dentro de
`APP247_SHUTDOWN_BUDGET_SECONDS` (padrão 20 s, abaixo de `TimeoutStopSec=30`) e
sai com `128+N` (143 para `SIGTERM`), que `SuccessExitStatus` trata como
sucesso. Parada explícita pelo systemd nunca reinicia (BUG-047, BUG-063).

No `--activate`, o instalador resolve o usuário gráfico por override,
`SUDO_USER` ou uma única sessão local Wayland/X11 ativa no `loginctl`. A unit
vai para `$HOME/.config/systemd/user/app247-terminal.service` e seu enable para
`default.target.wants`, nunca para `/root`. Ele cria o atalho
`Terminal 24-7.desktop`, exibido como **Terminal 24/7**, e a entrada XDG de
autostart; ambos chamam `systemctl --user start --no-block`, sem contornar a
unit. Arquivo preexistente não gerenciado nunca é sobrescrito. Em
provisionamento sem sessão, use `APP247_DESKTOP_USER=<usuario>`.

O usuário gráfico entra no grupo `app247` e deve relogar/reiniciar para receber
a associação. Estado persistente usa `2770 app247:app247`, setgid e arquivos
compartilhados `0660`; launcher e unit usam `umask 0007`. A credencial é a
exceção: pertence ao usuário gráfico, grupo `app247`, modo `0600`, e o runtime
recusa UID diferente ou qualquer leitura de grupo/outros. Assim SQLite,
identidade, sync e orientação são compartilhados sem tornar segredos públicos.

A unit usa `Restart=always` com `RestartPreventExitStatus=0`, limite de cinco
partidas por minuto, e ignora somente erro de orientação no `ExecStartPre`.
**Só o painel administrativo fecha o Terminal de vez:** "Fechar Terminal" (e a
restauração local/remota) chama `QApplication.quit()` após parar workers,
timers, socket, heartbeat, sync, telemetria e monitores, e `main` retorna `0`,
o único código que não reabre. Sinal vindo de fora do systemd (`pkill`,
Ctrl+C, `SIGHUP` de fim de sessão) sai com `128+N` e o systemd reabre em 3 s;
crash ou qualquer outra saída também reabrem. A janela ignora `closeEvent` sem
autorização (Alt+F4, fechar pela barra de tarefas) e a tecla Esc (BUG-063).

No labwc, o instalador grava em `~/.config/labwc/rc.xml` do usuário gráfico
uma regra (bloco `app247:kiosk-rule`, substituído a cada instalação) que tira a
barra de título e a entrada na barra de tarefas das janelas `app_id
app247-terminal`, inclusive dos avisos. Assim o toque não alcança o botão de
minimizar (BUG-064). `APP247_LABWC_KIOSK_RULE=false` desliga a regra.

## Release 1.0.8

Preparada em 25 de novembro de 2026 sobre a 1.0.7, para levar ao campo o
registro do tamanho da janela (BUG-066): linhas `[WINDOW]` no log a cada
mudança de tamanho, de estado ou da tela, e warning se a janela do kiosk
continuar diferente da tela. Sem outras mudanças de comportamento, de
instalação ou de dados. A 1.0.7 já instalada impede reinstalar com a mesma
versão (`install.sh` recusa release divergente), por isso a nova versão.

Passos iguais aos da 1.0.7, com `1.0.8`. Validação de campo pendente: BUG-066
(conferir as linhas `[WINDOW]` em `/var/lib/app247/logs/terminal.log`), além
das pendências da 1.0.7.

## Release 1.0.7

Preparada em 25 de novembro de 2026 sobre `v1.0.6`. É a primeira release em
que o pacote instalado no campo deve sair de uma tag: a 1.0.6 do Raspberry foi
um build local feito sobre `f94afa9`, diferente da tag `v1.0.6` (`a38bba1`).

Mudanças desde `v1.0.6`:

- identidade visual 24/7, textos enxutos, card do carrinho, aviso de
  inatividade e leitura do QR na tela inicial (`f94afa9`);
- card de status do Wi-Fi empilha em retrato e não alarga a janela (BUG-062);
- só o painel administrativo fecha o Terminal de vez; `pkill`, Ctrl+C e
  `SIGHUP` saem com `128+N` e o systemd reabre (BUG-063);
- janelas sem barra do labwc, sem minimizar no quiosque (BUG-064);
- ping/pong no socket de pagamento detecta conexão meio-aberta (BUG-049);
- log rotativo em `/var/lib/app247/logs/terminal.log` (BUG-050);
- Terminal sem maquininha não fica mais preso em "Confirmando pagamento";
  o pagamento é recusado antes de criar carrinho, e uma tentativa já presa é
  liberada sozinha depois da atualização (BUG-065).

Na instalação, BUG-063 e BUG-064 dependem do `install.sh` desta versão: ele
reinstala a unit e grava a regra do labwc. O diretório de logs é criado pelo
próprio app. Nenhuma migração de SQLite ou de `terminal.json`.

Passos, numa máquina ARM com a mesma arquitetura do Terminal (o host amd64 não
gera o pacote do Raspberry):

1. checkout do commit `chore(release): versão 1.0.7`;
2. `scripts/build.sh`;
3. `APP247_UPDATE_PRIVATE_KEY=<chave> scripts/package-release.sh 1.0.7`;
4. `scripts/verify-release.sh` com o `.tar.gz`, o manifesto e o `.sig`;
5. no Terminal: `install.sh` e depois `install.sh --activate`; relogar se o
   instalador avisar mudança de grupo;
6. criar a tag anotada `v1.0.7` nesse commit com o SHA-256 do pacote na
   mensagem, como na `v1.0.3`.

Validação de campo pendente desta versão: BUG-049, BUG-050, BUG-063, BUG-064
e BUG-065.
Build de verificação amd64 em 25/11/2026: `--version` retorna `1.0.7`, a GUI
sobe offscreen e grava o log persistente até o encerramento por `SIGTERM`.
