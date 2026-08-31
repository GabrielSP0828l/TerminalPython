# Telemetria do Raspberry e Terminal Python

Voltar para [o índice](00-index.md). Este fluxo não monitora a Point Mercado Pago.

`TelemetryService` inicia após ativação e executa em uma thread daemon. O padrão é uma amostra a cada 60 segundos, configurável por `TELEMETRY_INTERVAL_SECONDS` com mínimo de 30 segundos. O POST usa `TELEMETRY_TIMEOUT_SECONDS`, padrão 5 segundos. Falha de sensor, API ou timeout descarta apenas a amostra; não existe fila offline e a aplicação tenta novamente no próximo ciclo sem popup nem bloqueio da UI, scanner, compra ou pagamento.

Collectors:

- `SystemMetricsCollector`: `/proc/stat`, `/proc/meminfo`, `/proc/uptime`, `os.getloadavg`, `shutil.disk_usage`, `/sys/class/thermal/thermal_zone0/temp` e `vcgencmd get_throttled` com timeout;
- `NetworkMetricsCollector`: status leve do NetworkManager/`nmcli`, SSID/interface/IP/sinal e latência de `GET /terminal/health`;
- `ApplicationMetricsCollector`: referências do `SyncService`, `CompraSession` e `PaymentListener.connection_state`;
- `DisplayMetricsCollector`: geometria real de `QApplication.primaryScreen()`.

O parser de `get_throttled` interpreta bits atuais 0–3 e históricos 16–19 para subtensão, frequência limitada, throttling e soft temperature limit. O hexadecimal bruto é mantido. Sem `vcgencmd` ou sensor térmico, envia `null`; nunca inventa 0 °C ou estado saudável.

O payload contém somente estado do equipamento: UUID, versão, timestamps, métricas, compra/pagamento como booleanos e display. Não contém empresa/condomínio, cliente, carrinho, CPF, e-mail, telefone, dados de pagamento, JWT, credenciais, senha/PSK Wi-Fi ou logs. Scanner HID não expõe saúde confiável e não gera `scannerAvailable` falso.

O `SyncService` agora mantém em memória início, conclusão, último sucesso e erro sanitizado de até 300 caracteres. `PaymentListener` diferencia `CONNECTED`, `DISCONNECTED` e `RECONNECTING`. Esses estados já existentes são lidos; a telemetria não cria uma segunda máquina de estados.

Configuração em `.env`:

```text
TELEMETRY_INTERVAL_SECONDS=60
TELEMETRY_TIMEOUT_SECONDS=5
APP_VERSION=1.0.0
```

Limite operacional: temperatura/energia precisam de validação final no Raspberry físico. `vcgencmd` não existe no computador de desenvolvimento, cenário coberto pelos testes.
