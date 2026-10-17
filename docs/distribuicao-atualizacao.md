# Distribuição, build e atualização

Voltar para [[00-index]]. Arquitetura de código em [[arquitetura]] e estado em
[[sqlite]].

## PyInstaller

`app247-terminal.spec` gera um bundle `onedir`, inclui `assets/`, Qt SVG,
websocket-client e módulos dinâmicos do qrcode. A saída é
`dist/app247-terminal/app247-terminal`.

`scripts/build.sh` limpa somente `build/` e `dist/`, verifica o Python e o
PyInstaller, registra a arquitetura do host e rejeita cross-compile solicitado.
O artefato ARM64 deve ser gerado em Linux `aarch64` ou runner nativo compatível.

Em `aarch64`, o build valida `/usr/bin/python3` e `PyQt5.QtSvg`, cria o venv
dedicado `.venv-build-aarch64` com `--system-site-packages` e confirma que o
PyQt5 carregado é exatamente o `python3-pyqt5` do sistema. As dependências pip
desse ambiente vêm de `requirements-arm64.txt`, que deliberadamente não contém
PyQt5 nem `pyqt5_sip`. O script nunca executa `apt`/`sudo`; se necessário, o
operador instala `python3-venv`, `python3-pyqt5` e `python3-pyqt5.qtsvg`.

## Layout do Raspberry

```text
/opt/app247/current -> releases/<versão>
/opt/app247/releases/<versão>/
/var/lib/app247/terminal.db
/var/lib/app247/terminal.json
/var/lib/app247/device-credential
/etc/app247/terminal.env
/etc/app247/update-signing-public-key.pem
```

`scripts/install.sh` recusa sobrescrever uma release durante a preparação, mas
permite ativar a mesma versão já preparada sem recopiar o artefato. Com
`--activate`, troca o symlink `current`, executa o diagnóstico da instalação,
restaura o alvo anterior em caso de erro e, quando aprovado, instala a unit do
usuário gráfico em `~/.config/systemd/user`, habilita-a offline e faz
`daemon-reload`/start somente quando o bus da sessão existe. O override
`APP247_MANAGE_SYSTEMD=false` mantém a instalação da unit sem operar o daemon.

`app247-terminal --check` valida configuração, paths, assets, SQLite,
credencial individual, health HTTP e release ativa. Ausência inicial de banco
ou credencial é aviso; inconsistências que tornam a instalação inoperante
retornam exit code diferente de zero.

## Updater e rollback

`updater/` valida SemVer, manifesto estrito assinado com Ed25519, nome e
arquitetura do pacote e seu SHA-256 antes de montar o plano. A assinatura cobre
o JSON canônico sem `signature`: `schemaVersion`, `version`, `sha256`,
`architecture` e `package`. A extração aceita somente uma release nova e
rejeita path traversal e links. A base atual não baixa, não ativa e não
substitui o processo em execução.

A chave pública é trust anchor fora da release, deve ser arquivo regular não
gravável por grupo/outros e, ao rodar como root, pertencer ao root.
`APP247_UPDATE_PUBLIC_KEY_SOURCE` a instala somente quando ainda não existe; a
rotação nunca é implícita. A chave privada fica apenas no cofre do pipeline.

Pendências antes de automação real:

1. download autenticado e retomável;
2. supervisor externo com privilégios mínimos;
3. parada ordenada respeitando pagamento incerto;
4. health-check pós-start e janela de confirmação;
5. troca atômica para a release anterior quando o health-check falhar;
6. retenção controlada de releases antigas;
7. procedimento auditável de rotação da chave pública.

O exemplo systemd está em `packaging/systemd/app247-terminal.service` e é uma
**unit de usuário**, não uma unit de sistema. Ela chama somente o launcher,
usa `Restart=on-failure`, `RestartSec=3`, `StartLimitIntervalSec=60` e
`StartLimitBurst=5`. O `ExecStartPre=-... --apply-display` torna indisponibilidade
de orientação um aviso, sem impedir a GUI de iniciar.
O launcher trata `--apply-display` em caminho próprio, limitado por tempo e sem
abrir a GUI; o instalador migra units legadas sem marcador e grava a política de
Wi-Fi sem economia de energia. Detalhes em
`Terminal_app24/7/distribuicao-atualizacao.md`.

## Release distribuível

O fluxo oficial local é `build.sh` seguido de
`package-release.sh <SemVer>`. O empacotador confirma versão interna, diagnóstico
isolado, arquitetura Debian do host e arquitetura ELF por `file`; copia todo o
`onedir`; monta uma raiz versionada; cria tar determinístico por commit/
`SOURCE_DATE_EPOCH`; calcula SHA-256; chama o assinador Ed25519 existente; e
chama imediatamente `verify-release.sh` antes de mover os quatro resultados
para `release/`. Artefatos da mesma versão nunca são sobrescritos.

O manifesto schema 1 ganhou `size` e `signatureAlgorithm` opcionais e assinados,
sem invalidar documentos antigos. A assinatura embutida continua sendo a fonte
do updater; o `.sig` é a mesma assinatura Base64 destacada para distribuição.

O arquivo compactado contém somente `app/`, `install.sh`, unit, launcher,
template, chave pública, `VERSION` e `RELEASE_INFO.json`. O verificador rejeita
`.env`, chaves privadas, banco/identidade/credencial, fontes/testes/caches,
links que escapem da raiz, arquitetura divergente e instalador acoplado ao
checkout. A chave privada é lida apenas do path externo informado ao build.

O `install.sh` detecta tanto o checkout legado quanto o pacote standalone. No
standalone ele lê `VERSION`, usa `app/` e fontes adjacentes, reconhece uma
release existente somente quando idêntica e instala a chave pública fora de
`/opt/app247/releases`. Em host novo cria o usuário/grupo `app247`, preserva
configuração/estado e instala o launcher gráfico sem UID hardcoded.

Durante `--activate`, o usuário gráfico é obtido de `APP247_DESKTOP_USER`,
`SUDO_USER` ou de uma única sessão local Wayland/X11 ativa encontrada com
`loginctl`. A unit é instalada em
`$HOME/.config/systemd/user/app247-terminal.service`, nunca em `/root`; seu
enable é o link `default.target.wants`. O atalho `Terminal 24-7.desktop` (nome
visível `Terminal 24/7`) e `~/.config/autostart/app247-terminal.desktop` chamam
`systemctl --user start --no-block`, portanto usam a mesma infraestrutura e não
executam o binário diretamente. Arquivos existentes não gerenciados pelo App247
não são sobrescritos. `APP247_DESKTOP_HOME`, `APP247_DESKTOP_DIR`,
`APP247_AUTOSTART_DIR` e `APP247_USER_SYSTEMD_DIR` existem para
provisionamento/teste.

O usuário gráfico é associado ao grupo `app247`. O diretório persistente usa
`2770 app247:app247`, setgid, e os arquivos compartilhados usam `0660`; launcher
e unit usam `umask 0007`. A credencial individual é exceção deliberada:
`0600`, proprietária do usuário gráfico e grupo `app247`; o runtime rejeita
qualquer credencial de outro UID ou com leitura de grupo/outros. A associação de
grupo passa a valer no próximo login/reboot. O launcher prefere Wayland com
socket verificado, espera a sessão por até 30 segundos e mantém lock por sessão;
X11 só é aceito com socket local válido.
