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
