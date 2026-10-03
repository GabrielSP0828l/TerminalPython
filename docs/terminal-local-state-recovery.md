# Estado local e recuperação financeira

Atualizado em 27 de setembro de 2026. Relacionados: [[sqlite]], [[fluxo-compra]], [[terminal-device-security]] e [[auditoria-bugs]].

## Classificação

Recriáveis: catálogo (`produtos`, barcodes, cursor de sync), imagens temporárias e cache visual.

Críticos: `terminal.json`, linha singleton de `active_payment`, `generation`, `local_attempt_id`, `cart_id`, `order_id`, `payment_id`, `payment_attempt_id`, intenção de cancelamento e último status.

## Atomicidade

Cada snapshot de `active_payment` é escrito por uma única transação SQLite/UPSERT. IDs remotos e status não são persistidos em commits independentes. O cart é atualizado condicionalmente pelo `local_attempt_id`, rejeitando worker obsoleto. Falha de checkpoint inicial impede o worker financeiro de iniciar.

## Startup

```text
abrir SQLite
  -> PRAGMA integrity_check
  -> aplicar reset pendente somente se não existir active_payment
  -> ler active_payment
  -> identidade válida: restaurar sessão e reconciliar
  -> identidade ausente/corrompida + checkpoint: tela exclusiva de recovery
       -> consultar backend com terminal_id persistido
       -> intermediário/erro: manter bloqueio e repetir
       -> terminal/ausência autoritativa: liberar reativação
```

Nova compra nunca é aberta enquanto há checkpoint não terminal. O backend continua sendo a fonte de verdade financeira.

## Corrupção

Falha no `integrity_check` não remove, renomeia ou recria o banco. O Terminal entra em modo de recuperação, bloqueia operação comercial e orienta intervenção administrativa. Um marcador de reset também permanece pendente quando o estado financeiro não pode ser verificado.

## Reset

Reset administrativo exige autenticação local e confirmação explícita. `STARTING_PAYMENT`, `PENDING`, `WAITING_PAYMENT`, `PROCESSING`, `UNKNOWN`, `TIMEOUT_CHECK`, `RECONCILIATION_PENDING`, `CANCELLING`, IDs remotos ou qualquer linha `active_payment` bloqueiam com `RESET_BLOCKED_ACTIVE_PAYMENT`.

Após resultado definitivo e finalização da experiência (`IDLE`, sem IDs/checkpoint), o reset pode prosseguir. Limpar catálogo não é desativar Terminal; factory reset remove identidade/cache apenas depois da guarda. Revogação remota é uma operação distinta.

## Schema

Catálogo usa `schema_version` v2 e migração transacional. `active_payment` possui migração aditiva compatível para `cancellation_requested`. Um versionamento unificado de todo o banco continua pendente; não foi introduzido framework de migração novo nesta etapa.
