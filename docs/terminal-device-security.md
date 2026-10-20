# Segurança do dispositivo Terminal

Atualizado em 3 de outubro de 2026. Veja [backend-contracts.md](backend-contracts.md).

O `terminalId` é identificador público, não autenticação. A operação usa uma
credential aleatória individual que resolve exatamente um Terminal, Empresa e
Condomínio no backend.

O segredo bruto existe apenas no arquivo apontado por
`APP247_DEVICE_CREDENTIAL_PATH`, criado/substituído atomicamente com permissão
`0600`, sincronização do arquivo e do diretório. Leitura falha fechada para
symlink, arquivo não regular, tamanho/formato inválido ou permissões de
grupo/outros.
Não é gravado em `terminal.json`, SQLite, logs ou Git.

A credential chega pelo pareamento: sem ela, a tela de ativação mostra um código
e um QR (`APP247-PAIR:XXXX-XXXX`). O gestor confirma no app admin e o Terminal
recebe a credential uma única vez em `POST /terminal/pairing/claim`, trocando o
`pairingToken`, que fica só em memória e nunca aparece na tela. O código vale
15 minutos e é renovado sozinho. `scripts/install-device-credential.sh` continua
disponível para instalação manual. A migração por `TERMINAL_INTERNAL_TOKEN` foi
removida em 20/10/2026; não existe fallback legado.

HTTP e WebSocket enviam `X-Terminal-Token`; rotas que exigem correlação também
enviam `X-Terminal-Id`. 401 entra em modo seguro e exige reprovisionamento; 403
preserva o arquivo, mas bloqueia operação. Nenhum dos dois apaga checkpoint
financeiro.

Factory reset remove a credential. No reset remoto, ela é mantida somente até o
ACK autenticado de conclusão. Reset de catálogo não altera identidade.

Provisionamento e rotação local não recebem segredo em argumento nem ambiente.
`scripts/install-device-credential.sh` lê de entrada protegida; o binário oferece
`--install-device-credential`. O valor não é impresso. A rotação continua sendo
emitida/revogada pelos endpoints administrativos existentes no backend; o
Terminal apenas substitui atomicamente o novo `tdc_...`.
