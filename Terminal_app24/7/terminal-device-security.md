# Segurança da credencial do Terminal

Voltar para [[00-index]]. Contratos relacionados em [[api-backend]] e
[[websocket]].

O `terminalId` é identificador e correlação, não segredo. O backend emite uma
credencial individual `tdc_...`, armazena apenas seu hash e continua sendo a
fonte de verdade para vínculo, rotação e revogação. Nenhum endpoint, header ou
formato WebSocket foi alterado.

No Raspberry, o segredo bruto fica exclusivamente no caminho configurado por
`APP247_DEVICE_CREDENTIAL_PATH` (produção:
`/var/lib/app247/device-credential`). O arquivo deve ser regular, nunca symlink,
ter permissão `0600`, tamanho limitado e formato válido. A leitura falha fechada
se essas condições não forem atendidas.

Instalação e rotação local usam arquivo temporário exclusivo, `fsync`, troca
atômica e sincronização do diretório. `scripts/install-device-credential.sh` e
`app247-terminal --install-device-credential` leem o valor sem colocá-lo em
argumentos ou variáveis de ambiente e não o imprimem. Execute como o mesmo
usuário dedicado do serviço.

`TERMINAL_INTERNAL_TOKEN` não é fallback operacional: permanece limitado à
migração legado explicitamente habilitada. HTTP e WebSocket continuam usando
`X-Terminal-Token`; quando exigido pelo contrato, `X-Terminal-Id` mantém a
correlação.
