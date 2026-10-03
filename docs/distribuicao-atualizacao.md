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

`scripts/install.sh` recusa sobrescrever uma release. Sem `--activate`, apenas
prepara o diretório. Com a opção explícita, troca somente o symlink `current` e
registra o alvo anterior; não reinicia systemd nem remove estado.

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
