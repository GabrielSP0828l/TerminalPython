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

## Diagnóstico de campo no Raspberry (outubro de 2026)

Raspberry Pi 4 Model B Rev 1.5 (`raspberrypi.local`, Raspbian 13 trixie). Chip **BCM4345/6 (CYW43455)** via SDIO, driver `brcmfmac`, firmware `7.45.265` (29/08/2023, `brcmfmac43455-sdio`). Corrupção do sistema em [[auditoria-bugs]] (BUG-045).

**Decisão: economia de energia do Wi-Fi permanece desligada; não reativar.**

### Fatos

| Momento | Fonte | Medição |
|---|---|---|
| 16/10, powersave ligado (relato) | ping gateway | 13/15, 13,3% de perda, RTT méd/máx 164/1264 ms |
| 16/10, powersave ligado (relato) | ping `1.1.1.1` | 13/15, 13,3% de perda, RTT méd/máx 315/1483 ms |
| 16/10, após tentativa de desligar (relato) | ping gateway | 26/30, 13,3% de perda, RTT méd/máx 158/1195 ms |
| 16/10 00:26 (boot) | kernel | `brcmf_cfg80211_set_power_mgmt: power save enabled` |
| 16/10 16:04 | kernel | `power save disabled` (comando manual) |
| 16/10 16:12 | SSH | 30/30, 0% de perda, RTT méd/máx 52/790 ms |
| 17/10 01:40 | SSH | gateway 40/40, 0%, RTT méd/máx **4,4/12,7 ms**; `1.1.1.1` 40/40, 0%, 34,4/37,1 ms; `arping` 20/20 |
| 17/10 01:40 | `iw` | canal 48, 80 MHz (center 5210), sinal -48 dBm, tx 433 Mbit/s, rx 325 Mbit/s, conectado há 11 h sem desassociação |
| 17/10 01:40 | NetworkManager/wpa | nenhum `disconnect`/`deauth`; apenas renovações DHCP a cada 30 min |
| 17/10 01:40 | perfil | `802-11-wireless.powersave = default`; não havia política global em `conf.d` |

### Interpretação

- **Fato:** o powersave **voltava a ligar a cada boot**, porque o perfil está `default` e nada no NetworkManager o desligava; o `iw ... off` manual vale só até o reboot.
- **Fato:** com o powersave desligado, a perda caiu de 13% para 0% e a latência máxima até o gateway caiu de >1 s para 12,7 ms, com o mesmo canal e sinal.
- **Hipótese, não descartada:** a medição de "após tentativa" ainda com 13% de perda pode ter sido feita antes do `off` valer (o kernel registra o desligamento às 16:04) ou refletir instabilidade do roteador. Por isso não se conclui que powersave é a única causa.
- **A acompanhar:** `iw station dump` mostra `tx failed: 72698` contra ~195 mil pacotes TX em 11 h. Os contadores do `brcmfmac` são de firmware e pouco confiáveis; comparar a taxa de crescimento entre medições antes de concluir algo.
- Sem evidência de interferência: a varredura só mostra o próprio SSID no canal 48. Canal e largura do roteador não foram alterados.

### Correção de software

O instalador grava `/etc/NetworkManager/conf.d/app247-wifi-powersave.conf` com `wifi.powersave = 2` (ver [[distribuicao-atualizacao]]). Vale para todo perfil `default`, inclusive redes criadas por esta tela, e persiste entre reconexões e reboot. Não reinicia a rede. Perfis com valor explícito continuam mandando.

### Comandos de comparação (antes/depois)

```bash
# configuração efetiva
iw dev wlan0 get power_save
nmcli -g 802-11-wireless.powersave connection show TUXNET-KATIA_5G
cat /etc/NetworkManager/conf.d/app247-wifi-powersave.conf
journalctl -k -b | grep brcmf_cfg80211_set_power_mgmt

# qualidade do link e contadores (repetir e comparar o crescimento)
iw dev wlan0 link
iw dev wlan0 station dump | grep -E 'signal|tx retries|tx failed|beacon loss|bitrate|connected time'

# perda real x ICMP lento: gateway, internet e ARP (não depende de ICMP)
ping -c 100 -i 0.2 -W 2 192.168.18.1 | tail -2
ping -c 100 -i 0.2 -W 2 1.1.1.1 | tail -2
sudo arping -c 50 -w 60 -I wlan0 192.168.18.1 | tail -3

# eventos de associação/desassociação
journalctl -b -u NetworkManager -u wpa_supplicant | grep -Ei 'disconnect|deauth|reason|CTRL-EVENT'
```

Pendentes: confirmar `power save disabled` no kernel após um reboot com a política instalada; repetir as medições em horário de maior uso; comparar via Ethernet para isolar o rádio.
