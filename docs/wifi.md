# Gerenciamento de Wi-Fi

Voltar para [[00-index]]. Acesso em [[menu-administrativo]], composição visual em [[telas]] e arquitetura em [[arquitetura]].

## Fluxo

```text
toque longo no logotipo
  -> senha administrativa
      -> CONFIGURAR WI-FI
          -> WifiScreen
              -> WifiWorker / QThread
                  -> WifiService
                      -> NetworkManager / nmcli
```

Não existe painel paralelo. `WifiScreen` é uma subpágina da `ConfiguracaoScreen` já autenticada; `VOLTAR` retorna ao menu sem pedir a senha novamente. Ao sair inteiramente da administração, a autorização é descartada.

Quando o backend está inacessível, `OfflineOverlay` oferece `CONFIGURAR WI-FI`, mas a ação continua passando por `AdminAuthScreen`. Durante essa manutenção o overlay é ocultado para permitir operar a página e volta a acompanhar `InternetMonitor` ao sair.

## Serviço e segurança

`service/WifiService.py` é o único adaptador de rede. Ele detecta `nmcli`, o rádio e a interface Wi-Fi; obtém estado, SSID, sinal, IPv4 e perfis salvos; faz scan, conecta, desconecta e pode ativar o rádio. A UI não contém comandos Linux.

Todos os subprocessos usam lista de argumentos, `shell=False` implícito e timeout. SSID permanece como um argumento isolado. Para rede protegida nova, `nmcli --ask` recebe a senha por `stdin`; o segredo não aparece na linha do processo, não é salvo pelo Terminal e nunca é registrado. O NetworkManager continua responsável por persistir/reconectar perfis após reboot.

Limites atuais:

- status e IP: 3 s;
- scan: 12 s;
- conexão: 18 s, com espera interna do `nmcli` limitada a 12 s;
- desconexão/ativação: 12 s;
- nenhuma chamada usa `sudo` ou senha Linux hardcoded;
- perfis salvos com o nome padrão do SSID são reutilizados sem pedir senha;
- SSID oculto e perfil manual renomeado não fazem parte desta primeira etapa.

Falhas técnicas são convertidas em códigos internos (`TIMEOUT`, `AUTH_FAILED`, `NETWORK_UNAVAILABLE`, `PERMISSION_DENIED`, `NO_ADAPTER`, `SERVICE_UNAVAILABLE`) e mensagens em português. A saída bruta do NetworkManager fica somente no diagnóstico técnico; a senha não entra nesse log.

## Interface touchscreen

A página mostra conexão atual, qualidade humana (`Excelente`, `Bom`, `Médio`, `Fraco`), percentual e IP quando disponível. Redes são deduplicadas por SSID e ordenadas por conectada, intensidade e nome. Cada card possui ao menos 76 px de altura.

Rede protegida abre campo `QLineEdit.Password`, botão mostrar/ocultar e o `VirtualKeyboard` compartilhado em modo alfanumérico/símbolos. Rede aberta conecta sem campo de senha. Scan, conexão, desconexão e ativação usam `WifiWorker`, feedback imediato, spinner `icon/tube-spinner.svg`, timeout e retorno seguro.

Trocar ou desconectar a rede durante pagamento exibe aviso forte e não cancela/reset a cobrança. A página não cria heartbeat, socket ou sync: depois da mudança, os serviços existentes detectam a conectividade e retomam o fluxo normal.

## Ambiente auditado e validação física

O host de desenvolvimento auditado é Ubuntu 24.04 x86_64, não o Raspberry final. Nele, NetworkManager estava ativo, `nmcli` e `wpa_cli` existiam, `iwctl` não existia, o usuário possuía permissões NetworkManager para scan/controle/modificação e não havia interface Wi-Fi física — somente Ethernet. Portanto a integração e a UI foram validadas com doubles automatizados, sem alterar a rede do host.

No Raspberry deve-se confirmar: interface real (`wlan0` ou equivalente), scan, rede protegida/aberta, senha incorreta, troca A→B, recuperação do backend/WebSocket/sync/heartbeat e reconexão após reboot. Nenhuma cobrança real deve ser iniciada nesse ensaio.
