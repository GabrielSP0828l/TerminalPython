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

Rollback do `--activate`: antes de gravar qualquer arquivo fora de `releases/`,
o instalador guarda um snapshot temporário de launcher, unit, link de enable,
política de Wi-Fi, ícone, atalhos e autostart. Se algo falhar depois da troca de
`current`, esses caminhos voltam ao estado anterior (ou são removidos, se não
existiam) junto com o symlink, e a unit anterior é recarregada antes do restart.

`systemctl --user stop`, reboot e `poweroff` enviam `SIGTERM`: o Terminal faz o
mesmo encerramento cooperativo do painel administrativo dentro de
`APP247_SHUTDOWN_BUDGET_SECONDS` (padrão 20 s, abaixo de `TimeoutStopSec=30`) e
sai com código 0, sem reinício pelo `Restart=on-failure` (BUG-047).

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

A unit usa `Restart=on-failure`, limite de cinco partidas por minuto e ignora
somente erro de orientação no `ExecStartPre`. O fechamento pelo painel chama
`QApplication.quit()` após parar workers, timers, socket, heartbeat, sync,
telemetria e monitores; `main` retorna `0` para esse caminho intencional. Crash
ou saída não-zero continuam reiniciáveis.
