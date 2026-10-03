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
restaura o alvo anterior em caso de erro e, quando aprovado, instala a unidade,
faz `daemon-reload`, habilita e inicia/reinicia o serviço. O override
`APP247_MANAGE_SYSTEMD=false` gera a unidade sem operar o daemon.

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

O exemplo systemd está em `packaging/systemd/app247-terminal.service`, usa
`Restart=always`, `RestartSec=3`, rede online e usuário dedicado configurável.
