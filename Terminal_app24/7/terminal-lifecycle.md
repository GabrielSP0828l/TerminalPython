# Lifecycle e factory reset da aplicação

Voltar para [[00-index]]. Transporte em [[websocket]], persistência em
[[sqlite]] e integração HTTP em [[api-backend]].

## Estados confirmados pelo backend

`TerminalLifecycleApi` aceita somente resposta HTTP 200 com um dos estados
`ACTIVE`, `PAYMENT_NOT_CONFIGURED`, `DISABLED`, `RESET_REQUIRED` ou
`UNACTIVATED`. A consulta ocorre no startup, a cada conexão/reconexão do
WebSocket e periodicamente. Timeout, equipamento offline, HTTP 5xx, JSON
inválido ou estado desconhecido retornam “sem decisão” e nunca iniciam reset.

`TERMINAL_FACTORY_RESET_REQUIRED` no WebSocket é somente um aviso para antecipar
essa consulta. A fonte de verdade é
`GET /terminal/{terminalId}/bootstrap`; por isso um Terminal desligado durante
o encerramento da Empresa descobre `RESET_REQUIRED` quando voltar a conectar.

## FACTORY_RESET_APPLICATION

Após confirmação autoritativa, o Terminal:

1. verifica `CompraSession` e adia o reset enquanto houver carrinho/order ou
   pagamento em estado não resolvido;
2. aciona a reconciliação já existente e só prossegue quando a sessão não
   possuir pendência;
3. tenta confirmar `factory-reset/started`;
4. grava atomicamente `db/factory-reset.pending` e encerra a aplicação;
5. no próximo processo, move a configuração/caches para staging, grava o
   recibo de conclusão e elimina o staging remoto;
6. abre a tela padrão “APP 24/7 — Terminal não configurado — ATIVAR TERMINAL”;
7. tenta `factory-reset/completed` até receber resposta 2xx.

O marcador torna o procedimento retomável e idempotente. Duas execuções deixam
o mesmo estado `UNACTIVATED`, sem restaurar dados da Empresa antiga. O reset
administrativo local continua recuperável em `db/reset-backups`; encerramento
remoto da Empresa nunca conserva esse backup de tenant.

## Dados removidos

- `db/terminal.json`: UUID/activation token e Empresa/Condomínio da ativação;
- `db/terminal.db`: produtos, barcodes, promoções projetadas,
  `catalog_sync_state` e cursor transacional;
- `database/last_sync.txt`: espelho legado do cursor;
- `temp_checkout.png`: QR/cache temporário de checkout.

Remover o banco SQLite inteiro mantém produtos, códigos e sync marker
atomicamente coerentes. Na próxima ativação o banco nasce com
`initialized=0`, contagem/cursor vazios e executa o FULL SYNC normal.

## Dados preservados

- Linux, aplicação, versão, autostart e atualizador;
- Wi-Fi do NetworkManager e demais configurações do sistema operacional;
- `.env`, incluindo endereços mínimos necessários à reconexão;
- orientação física em `APP247_DISPLAY_ORIENTATION_PATH` (padrão `data/display_orientation`);
- logs técnicos e código instalado;
- identidade física obtida do serial de hardware ou `/etc/machine-id`.

O UUID removido de `terminal.json` representa a ativação empresarial. A
identidade física não é inventada nem duplicada: o provisionamento existente já
usa serial do equipamento/machine-id, fontes fora dos arquivos removidos. Até a
nova ativação não há telemetria de tenant; logs locais técnicos podem continuar,
sem associação à Empresa encerrada.

`FACTORY_RESET_DEVICE`, capaz de apagar Wi-Fi e configuração adicional, não é
executado automaticamente e fica reservado para uma futura ação física/local.
