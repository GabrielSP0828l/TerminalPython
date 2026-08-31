# Rede na telemetria

`NetworkMetricsCollector` reutiliza `WifiService.status()`, uma leitura `nmcli` sem rescan ativo e sem consultar perfis/segredos. Envia interface, SSID permitido, IP local, conexão e percentual do sinal. Os rótulos são: `EXCELENTE` a partir de 75%, `BOM` a partir de 55%, `MEDIO` a partir de 35% e `FRACO` abaixo disso.

Latência mede a API realmente usada pelo Terminal com `GET /terminal/health`; ICMP não é autoridade. Timeout ou falha resulta em `backendReachable=false` e latência `null`. Quando `nmcli`/adaptador não está disponível, o estado Wi-Fi é `null`, não uma desconexão inventada.

Nenhuma senha, PSK, perfil salvo ou credencial de rede é coletado, logado ou enviado. Para configuração administrativa do Wi-Fi, veja [[wifi]].
