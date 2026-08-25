# Sincronização de produtos

Voltar para [o índice](00-index.md). Persistência em [[sqlite]], API em [[api-backend]] e aviso em [[websocket]].

## Fluxo implementado

```text
STARTUP / PRODUCT_SYNC_REQUIRED / WEBSOCKET_RECONNECT / PERIODIC
  -> request_sync(origem)
  -> sync_in_progress?
       sim: sync_pending=true
       não: worker único
  -> valida catalog_sync_state + contagem ativa
  -> cache não inicializado/inconsistente: omite lastSync
  -> GET /produtos/sync?uuidTerminal=...&lastSync=...
  -> valida {syncAt, fullSync, changes}
  -> SQLite BEGIN
  -> UPSERT / REMOVE
  -> COMMIT
  -> grava exatamente syncAt
  -> se sync_pending: executa mais uma vez
```

O WebSocket é aviso; HTTP é a fonte dos dados; SQLite é cache; `syncAt` do backend é o cursor. O intervalo de segurança padrão é 300 segundos (`PRODUCT_SYNC_INTERVAL_SECONDS`), além das chamadas no startup, evento e conexão/reconexão.

## Contrato

Primeira chamada — inclusive a migração de instalações que já possuíam cursor, mas não marcador — omite `lastSync`; o backend retorna `fullSync=true` e o estado completo vendável do condomínio derivado pelo UUID do Terminal. Chamadas seguintes só enviam o último `syncAt` quando `catalog_sync_state` confirma que o cache foi inicializado e sua contagem ativa continua consistente.

- `UPSERT`: contém `productId`, `operation` e `produto` completo; insere ou atualiza todos os campos.
- `REMOVE`: contém `productId` e `produto=null`; desativa localmente, de modo idempotente.
- FULL: desativa o catálogo local atual e aplica todos os UPSERTs na mesma transação.
- INCREMENTAL: não toca em produtos ausentes de `changes`.

## Cursor e falhas

`database/last_sync.txt` persiste exatamente o `syncAt` do servidor. `datetime.now()`/`utcnow()` não geram cursor. Arquivo ausente ou formato legado sem timezone é ignorado para provocar FULL SYNC; ele só é substituído depois do commit.

`catalog_sync_state.initialized` só vira `1` dentro do commit de um FULL SYNC válido. `expected_active_count` é atualizado atomicamente a cada lote e comparado à contagem ativa real antes da próxima chamada. Marcador ausente ou divergência força FULL e impede que um incremental vazio avance um cache não confiável. Um FULL confirmado com zero produtos é válido: grava `initialized=1` e contagem esperada zero, pois condomínio sem associações é um estado legítimo.

Resposta inválida é rejeitada antes da escrita. Falha HTTP preserva cache e cursor. Falha SQLite executa rollback completo e também preserva cursor, permitindo repetir o mesmo intervalo.

## Concorrência e UI

`request_sync` protege `sync_in_progress` e `sync_pending` com `threading.Lock`. Há apenas um worker HTTP/SQLite. Um ou vários eventos recebidos durante uma execução produzem exatamente uma nova execução `PENDING`, nunca concorrente. O callback Qt apenas solicita trabalho, portanto não bloqueia a interface.

O scanner consulta `DatabaseProdutos.buscar_por_codigo` em cada leitura e filtra `status=1`; novos produtos e remoções passam a valer sem reiniciar. O carrinho ativo conserva seus objetos já capturados, evitando alteração silenciosa de preço/item no meio da compra.

## Validação de 24 de agosto de 2026

A suíte cobre também `SQLite vazio + lastSync`, FULL vazio confirmado e adulteração da contagem local. Na validação real, o Terminal tinha zero produtos e cursor avançado; a primeira execução corrigida omitiu o cursor e recebeu `fullSync=true, changes=[]`. O backend possui um produto na empresa, mas zero associações `EstoqueCondominio` no condomínio deste Terminal; por isso zero é o catálogo correto. A execução seguinte foi incremental vazia com cache já marcado consistente.
