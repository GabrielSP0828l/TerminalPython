# Wi-Fi administrativo

Voltar para [[00-index]]. Acesso em [[menu-administrativo]], telas em [[telas]] e lifecycle em [[arquitetura]].

## Arquitetura executável

```text
AdminAuthScreen
  -> ConfiguracaoScreen / CONFIGURAR WI-FI
      -> WifiScreen
          -> WifiWorker (QThread)
              -> WifiService
                  -> NetworkManager / nmcli
```

O painel administrativo existente foi reutilizado. `WifiService` concentra status, scan, perfis salvos, conexão, desconexão, rádio e IPv4; a UI não executa comandos Linux. As operações usam argv, sem `shell=True`/`sudo`, e possuem timeout de 3 a 18 segundos.

SSID é argumento isolado. Senha de rede protegida é entregue ao `nmcli --ask` por `stdin`, nunca em argv, não é armazenada pelo Terminal e não entra nos logs. NetworkManager continua responsável pelo perfil persistente e reconexão após boot.

A tela `1024×600` mostra conexão atual, sinal `Excelente/Bom/Médio/Fraco`, percentual, IP, cards de rede com 76 px e ordem conectada→sinal→nome. SSIDs duplicados são consolidados. Redes abertas não pedem senha; redes protegidas usam `QLineEdit.Password`, mostrar/ocultar e teclado virtual alfanumérico com símbolos.

Loading reutiliza `icon/tube-spinner.svg`. Timeout, autenticação, rede desaparecida, permissão, adaptador ou serviço ausente recebem mensagem amigável e retry/voltar. Alterar rede durante pagamento mostra aviso e não cancela a cobrança. WebSocket, sync e heartbeat não são duplicados: retomam pelo lifecycle existente quando o backend volta.

`OfflineOverlay` possui acesso a `CONFIGURAR WI-FI`, ainda protegido pela mesma senha administrativa.

## Auditoria e limite físico

No host Ubuntu 24.04 auditado, NetworkManager estava ativo; `nmcli` e `wpa_cli` existiam; `iwctl` não; as permissões polkit do usuário permitiam scan/controle/modificação sem sudo. O host não tinha interface Wi-Fi física, portanto não representa o Raspberry final.

Testes com doubles cobrem scan assíncrono, rede aberta/salva/protegida, senha errada, ausência do `nmcli`, timeout e SSID/senha com espaço, `-`, `_`, `@`, `#` e `!`. No Raspberry ainda devem ser validados adaptador real, troca A→B, retorno do backend/socket/sync/heartbeat e reconexão após reboot, sem cobrança real.
