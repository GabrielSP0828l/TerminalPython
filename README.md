# Terminal App247

Cliente de autoatendimento PyQt5 do backend Spring Boot do App247. O backend
continua sendo a fonte de verdade para Terminal, Empresa, Condomínio, estoque,
carrinho persistido, Order e pagamento.

## Arquitetura

```text
src/app247_terminal/
├── main.py                 entrypoint mínimo
├── application.py          composição, navegação e lifecycle Qt
├── config/settings.py      ambiente e paths persistentes
├── database/connection.py  conexão SQLite compartilhada
├── models/                 modelos e estado da compra
├── repositories/           cache/checkpoints SQLite
├── services/               HTTP, WebSocket, sync, pagamento e hardware
└── ui/                     telas e design system
updater/                    validação/staging futuro, fora do app
assets/                     imagens e SVGs empacotados
scripts/                    build, instalação e validação de update
packaging/systemd/          unidade de serviço de exemplo
tests/
```

As telas mantêm a navegação e o comportamento existentes. A leitura do
catálogo segue `UI -> CatalogService -> repository -> SQLite`; integrações
HTTP/WebSocket continuam em `services/` e fora da thread principal quando o
fluxo já usava workers.

## Desenvolvimento

Requer Python compatível com PyQt5 5.15 e bibliotecas nativas do Qt.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
./start.sh
```

Execução direta equivalente:

```bash
PYTHONPATH=src .venv/bin/python -m app247_terminal
```

Testes e sintaxe:

```bash
.venv/bin/python -m compileall -q src updater tests
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q
```

## Configuração e estado persistente

Variáveis principais:

| Variável | Desenvolvimento | Produção recomendada |
|---|---|---|
| `APP247_ENV` | `development` | `production` |
| `APP247_API_URL` | URL local/homologação | URL HTTPS do backend |
| `APP247_WS_URL` | URL WS local | URL WSS do backend |
| `APP247_DATA_DIR` | `./data` | `/var/lib/app247` |
| `APP247_DB_PATH` | `./data/terminal.db` | `/var/lib/app247/terminal.db` |
| `APP247_DEVICE_CREDENTIAL_PATH` | `./data/device-credential` | `/var/lib/app247/device-credential` |
| `APP247_UPDATE_PUBLIC_KEY_PATH` | `/etc/app247/update-signing-public-key.pem` | `/etc/app247/update-signing-public-key.pem` |
| `APP247_VERSION` | opcional | opcional; padrão empacotado |

Veja todas as chaves sem segredos em `.env.example`. Nomes antigos (`API_URL`,
`WS_URL`, `APP_ENV`) continuam aceitos durante a migração.

Na primeira execução pelo novo layout, arquivos legados em `db/` e
`database/last_sync.txt` são copiados somente se o destino novo não existir.
Os arquivos de origem não são apagados e um destino existente nunca é
sobrescrito.

## Build PyInstaller

O build usa `--onedir` por meio de `app247-terminal.spec`:

```bash
.venv/bin/pip install -r requirements-build.txt
./scripts/build.sh
```

Saída:

```text
dist/app247-terminal/app247-terminal
```

PyInstaller gera binários para a arquitetura do host. O artefato final para
Raspberry Pi 4 ARM64 deve ser construído em Linux `aarch64` (Raspberry, VM/runner
ARM64 ou pipeline nativo compatível). Para impedir engano em pipeline, use
`APP247_TARGET_ARCH=aarch64`; o script falha se o host tiver outra arquitetura.

No Raspberry/aarch64, o script evita instalar a wheel PyQt5 por pip. Ele exige o
PyQt5 do Raspberry Pi OS e cria automaticamente `.venv-build-aarch64` com
`--system-site-packages`; nesse ambiente instala apenas as demais dependências:

```bash
sudo apt install python3-venv python3-pyqt5 python3-pyqt5.qtsvg
APP247_TARGET_ARCH=aarch64 ./scripts/build.sh
```

`APP247_SYSTEM_PYTHON` e `APP247_ARM64_BUILD_VENV` permitem ajustar os caminhos.
`PYTHON_BIN` continua sendo override explícito, mas em ARM64 precisa importar o
mesmo PyQt5 do Python do sistema.

## Instalação no Raspberry

Layout esperado:

```text
/opt/app247/
├── current -> releases/1.0.0
└── releases/1.0.0/
/var/lib/app247/terminal.db e demais estados persistentes
/etc/app247/terminal.env
```

O instalador não sobrescreve banco ou configuração. A primeira chamada prepara
a release e cria `/etc/app247/terminal.env` a partir do template de produção:

```bash
sudo APP247_INSTALL_VERSION=1.0.0 \
  APP247_UPDATE_PUBLIC_KEY_SOURCE=/caminho/confiavel/update-public.pem \
  ./scripts/install.sh
sudoedit /etc/app247/terminal.env
sudo APP247_INSTALL_VERSION=1.0.0 ./scripts/install.sh --activate
```

Crie antes um usuário/grupo de serviço dedicado (`app247` por padrão) ou
informe `APP247_SERVICE_USER` e `APP247_SERVICE_GROUP`. O script não cria
contas automaticamente.

Sem `--activate`, a release é apenas copiada. A ativação aceita essa mesma
release preparada, troca atomicamente o symlink, executa o diagnóstico, instala
a unidade com o usuário/grupo configurados, faz `daemon-reload`, habilita e
inicia/reinicia o serviço. Falha no diagnóstico restaura o link anterior e não
inicia a nova versão. Para preparar uma imagem sem controlar o daemon, use
`APP247_MANAGE_SYSTEMD=false`; a unidade ainda será gerada no diretório indicado.

O diagnóstico também pode ser executado manualmente, como o usuário do serviço:

```bash
sudo -u app247 /opt/app247/current/app247-terminal --check
```

Ele valida URLs e placeholders, proteção do arquivo de ambiente, senha
administrativa, modo legado, assets, acesso ao diretório de dados, integridade
SQLite, formato/permissões da credencial individual, `GET /terminal/health` e o
symlink da release. SQLite e credencial ausentes são avisos na primeira ativação;
os demais erros retornam exit code diferente de zero.

## Atualização e rollback

`updater/` implementa a base segura: SemVer, manifesto JSON canônico assinado
com Ed25519, SHA-256 do pacote, arquitetura/nome do artefato, destino de nova
release e plano de rollback. O manifesto só é aceito após validação com a chave
pública confiável instalada fora da release. A chave privada nunca pertence ao
Terminal ou ao repositório; deve ficar no cofre do pipeline de release.
Ele não baixa pacotes, não para o serviço e não troca `current` enquanto o
Terminal está executando.

Validação manual de um pacote futuro:

```bash
./scripts/sign-update-manifest.sh release.tar.gz --version 1.1.0 \
  --architecture aarch64 --private-key /cofre/update-private.pem \
  --output manifest.json
./scripts/update.sh release.tar.gz manifest.json /etc/app247/update-signing-public-key.pem
```

Para completar atualização automática ainda será necessário um supervisor
externo privilegiado com download autenticado, política de parada,
health-check, troca atômica do link e rollback para o alvo
registrado em `/var/lib/app247/previous-release`.

## Credencial individual do Terminal

O contrato existente `X-Terminal-Token: tdc_...` foi preservado. A credencial
bruta fica somente no arquivo `0600`, recusado se for symlink, tipo inválido ou
acessível por grupo/outros. Instalação e rotação local usam escrita atômica e
`fsync`, sem passar o segredo por argumento ou variável de ambiente:

```bash
./scripts/install-device-credential.sh
sudo -u app247 /opt/app247/current/app247-terminal --install-device-credential
```

## Administração local

Na tela inicial, mantenha o logotipo pressionado por dois segundos. O factory
reset continua bloqueado diante de pagamento incerto e atua somente sobre o
estado operacional configurado; `/etc/app247/terminal.env` e releases não são
apagados.
