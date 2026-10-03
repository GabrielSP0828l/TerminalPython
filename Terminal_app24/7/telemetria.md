# Telemetria do Raspberry e Terminal Python

Voltar para [[00-index]]. Rede em [[wifi]], presença em [[heartbeat]] e contrato em [[api-backend]].

`TelemetryService` roda numa thread daemon depois da ativação, a cada 60 segundos por padrão (`TELEMETRY_INTERVAL_SECONDS`, mínimo 30). Timeout padrão: 5 segundos. Cada falha descarta a amostra e o próximo ciclo tenta novamente; não há fila infinita, popup, bloqueio Qt nem dependência do fluxo de venda.

Os collectors independentes leem `/proc` e `/sys`, disco, load average, `vcgencmd get_throttled`, NetworkManager/`nmcli`, o health HTTP do backend, estados reais de sync/compra/pagamento/socket e a geometria Qt. Bits 0–3 e 16–19 de `get_throttled` distinguem condição atual e ocorrência desde o boot. Métrica indisponível é `null`, nunca zero falso.

Somente saúde do equipamento é enviada. Não há telemetria da Point, dados do cliente, carrinho, produtos, credenciais, senha Wi-Fi, tokens ou arquivos de log. O scanner é HID e não fornece disponibilidade confiável, portanto não recebe uma métrica inventada.

`SyncService` expõe início, conclusão, último sucesso e erro curto. `PaymentListener.connection_state` informa `CONNECTED`, `DISCONNECTED` ou `RECONNECTING`. O backend deriva Empresa/Condomínio pelo UUID provisionado.

Limite: temperatura e energia foram testadas por parser/dublês; validação final de caminhos e firmware exige o Raspberry físico.
