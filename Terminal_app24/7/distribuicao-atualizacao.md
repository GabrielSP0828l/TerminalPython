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
a release anterior se o diagnóstico falhar e só então instala a unidade systemd,
executa `daemon-reload`, habilita e inicia/reinicia o serviço. Usuário, grupo,
paths da unidade e controle do systemd possuem overrides `APP247_*`; com
`APP247_MANAGE_SYSTEMD=false` a unidade é gerada sem operar o daemon.

O diagnóstico é não destrutivo e valida URLs/placeholders, `terminal.env`,
configuração de segurança, assets, diretório persistente, `PRAGMA
integrity_check`, credencial individual, `GET /terminal/health`, versão e symlink.
SQLite e credencial ainda ausentes são avisos esperados no primeiro boot; erros
bloqueiam a ativação.

`updater/` valida SemVer, manifesto JSON canônico
assinado com Ed25519, chave pública confiável, nome/arquitetura, SHA-256 e plano
de staging/rollback; não baixa, para serviço ou ativa versão. A chave privada
fica somente no cofre do pipeline e nunca no Terminal/repositório.

Antes da automação real ainda são obrigatórios download autenticado, supervisor
externo, guarda de pagamento, health-check, rollback atômico e procedimento de
rotação da trust anchor. O exemplo systemd usa usuário dedicado configurável,
nunca presume `pi`.

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
da sessão — nunca `1000` —, valida `XDG_RUNTIME_DIR`, descobre um socket Wayland
pertencente ao usuário quando necessário e executa
`/opt/app247/current/app247-terminal`. Se o serviço systemd já estiver ativo, o
launcher não abre uma segunda instância. A unit instalada conserva os paths de
ambiente, dados, pre-start de orientação e executável ativo já estabelecidos.
