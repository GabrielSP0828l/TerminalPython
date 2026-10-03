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
  -> UPSERT produto + substituição integral de barcodes / REMOVE
  -> grava exatamente syncAt no catalog_sync_state
  -> COMMIT
  -> espelha cursor legado em melhor esforço
  -> se sync_pending: executa mais uma vez
```

O WebSocket é aviso; HTTP é a fonte dos dados; SQLite é cache; `syncAt` do backend é o cursor. O intervalo de segurança padrão é 300 segundos (`PRODUCT_SYNC_INTERVAL_SECONDS`), além das chamadas no startup, evento e conexão/reconexão.

## Contrato

Primeira chamada — inclusive a migração de instalações que já possuíam cursor, mas não marcador — omite `lastSync`; o backend retorna `fullSync=true` e o estado completo vendável do condomínio derivado pelo UUID do Terminal. Chamadas seguintes só enviam o último `syncAt` quando `catalog_sync_state` confirma que o cache foi inicializado e sua contagem ativa continua consistente.

- `UPSERT`: contém `productId`, `operation` e produto completo com `codigoInterno`, `codigosBarras[]`, preço/promoção e disponibilidade; substitui atomicamente os códigos daquele produto.
- `REMOVE`: contém `productId` e `produto=null`; desativa localmente e remove os códigos escaneáveis, de modo idempotente.
- FULL: desativa o catálogo local atual e aplica todos os UPSERTs na mesma transação.
- INCREMENTAL: não toca em produtos ausentes de `changes`.

## Cursor e falhas

`catalog_sync_state.last_sync_at` persiste exatamente o `syncAt` do servidor dentro da transação. `database/last_sync.txt` é um espelho legado; o relógio local nunca gera cursor. Cursor ausente/sem timezone provoca FULL SYNC.

`catalog_sync_state.initialized` só vira `1` dentro do commit de um FULL SYNC válido. `expected_active_count` é atualizado atomicamente a cada lote e comparado à contagem ativa real antes da próxima chamada. Marcador ausente ou divergência força FULL e impede que um incremental vazio avance um cache não confiável. Um FULL confirmado com zero produtos é válido: grava `initialized=1` e contagem esperada zero, pois condomínio sem associações é um estado legítimo.

Resposta inválida é rejeitada antes da escrita. Falha HTTP preserva cache e cursor. Falha SQLite executa rollback completo e também preserva cursor, permitindo repetir o mesmo intervalo.

## Concorrência e UI

`request_sync` protege `sync_in_progress` e `sync_pending` com `threading.Lock`. Há apenas um worker HTTP/SQLite. Um ou vários eventos recebidos durante uma execução produzem exatamente uma nova execução `PENDING`, nunca concorrente. O callback Qt apenas solicita trabalho, portanto não bloqueia a interface.

O scanner consulta `produto_codigo_barras JOIN produtos` em cada leitura e filtra código/produto ativos. Novos códigos, remoções e troca de barcode valem sem reiniciar. O carrinho agrupa por UUID do produto (dois barcodes da mesma mercadoria não criam dois CartItems) e conserva o snapshot já capturado durante a compra.

## Validação de 24 de agosto de 2026

A suíte cobre também `SQLite vazio + lastSync`, FULL vazio confirmado e adulteração da contagem local. Na validação real, o Terminal tinha zero produtos e cursor avançado; a primeira execução corrigida omitiu o cursor e recebeu `fullSync=true, changes=[]`. O backend possui um produto na empresa, mas zero associações `EstoqueCondominio` no condomínio deste Terminal; por isso zero é o catálogo correto. A execução seguinte foi incremental vazia com cache já marcado consistente.
