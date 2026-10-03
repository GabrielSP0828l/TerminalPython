# SQLite e persistência local

Voltar para [o índice](00-index.md). Fluxo detalhado em [[sincronizacao]].

## Paths canônicos

Os paths são centralizados em `src/app247_terminal/config/settings.py` e não
dependem do diretório corrente nem da release ativa.

| Path padrão de desenvolvimento | Produção recomendada | Finalidade |
|---|---|---|
| `./data/terminal.db` | `/var/lib/app247/terminal.db` | cache e checkpoints locais |
| `./data/terminal.json` | `/var/lib/app247/terminal.json` | identidade/ativação |
| `./data/last_sync.txt` | `/var/lib/app247/last_sync.txt` | espelho legado do `syncAt` |

`APP247_DB_PATH` sobrescreve o banco e `APP247_DATA_DIR` define os demais
estados. Na primeira execução, o startup copia arquivos legados somente quando
o novo destino não existe; não move, apaga ou sobrescreve dados. Todas as
conexões passam por `database/connection.py`.

## Schema de produtos

```sql
CREATE TABLE produtos (
    id TEXT PRIMARY KEY,
    codigo_interno TEXT NOT NULL,
    nome TEXT NOT NULL,
    preco_original TEXT NOT NULL,
    preco TEXT NOT NULL,
    em_promocao INTEGER NOT NULL DEFAULT 0,
    promocao_id TEXT,
    promocao_nome TEXT,
    quantidade TEXT,
    categoria TEXT,
    unidade_medida TEXT,
    descricao TEXT,
    foto TEXT,
    peso TEXT,
    peso_tolerancia TEXT,
    created_at TEXT,
    updated_at TEXT,
    ativo INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE produto_codigo_barras (
    produto_id TEXT NOT NULL,
    codigo_barras TEXT NOT NULL UNIQUE,
    tipo TEXT NOT NULL,
    principal INTEGER NOT NULL,
    ativo INTEGER NOT NULL,
    updated_at TEXT,
    PRIMARY KEY (produto_id, codigo_barras),
    FOREIGN KEY (produto_id) REFERENCES produtos(id) ON DELETE CASCADE
);

CREATE TABLE catalog_sync_state (
    singleton_id INTEGER PRIMARY KEY CHECK (singleton_id = 1),
    initialized INTEGER NOT NULL DEFAULT 0,
    expected_active_count INTEGER NOT NULL DEFAULT 0,
    last_sync_at TEXT
);
```

`schema_version` registra a versão 2 do catálogo. Ao abrir uma instalação antiga, o migrador transacional copia produtos, converte preço para `TEXT(6)`, quantidade/peso para `TEXT(3)` e transforma o antigo `produtos.codigo` em código principal `LEGACY`. Somente as tabelas de cache são reconstruídas; `db/terminal.json`, orientação, credenciais administrativas e demais configurações não são apagadas.

O `UNIQUE(codigo_barras)` local é intencional: esse arquivo contém o catálogo de um único Terminal/tenant. A garantia multi-tenant global permanece no MySQL como `UNIQUE(empresa_id, codigo_barras)`.

## Aplicação de alterações

`DatabaseProdutos.aplicar_sync` executa produtos, lista completa de barcodes e `last_sync_at` em uma única transação. Em `fullSync=true`, desativa o catálogo e limpa os barcodes antes dos `UPSERT`. No incremental, cada UPSERT substitui todos os códigos daquele produto. `REMOVE` define `ativo=0` e apaga os códigos escaneáveis.

`buscar_por_codigo` faz `JOIN produto_codigo_barras -> produtos` e exige ambos ativos. Qualquer falha causa `ROLLBACK`; nunca há produto novo com códigos antigos, nem cursor avançado sobre cache parcial.

`catalog_sync_state` é criado automaticamente. Instalações anteriores começam com `initialized=0`, mesmo que possuam `last_sync.txt` ou produtos residuais, e executam um FULL de migração. FULL e alterações de produtos atualizam marcador/contagem na mesma transação. Antes de usar cursor, `obter_estado_catalogo` exige marcador e igualdade entre `expected_active_count` e o `COUNT(status=1)` real.

## Cursor de sincronização

`catalog_sync_state.last_sync_at` é a fonte de verdade e participa do mesmo commit do catálogo. O arquivo `last_sync.txt` continua apenas como fallback/espelho para compatibilidade. Ausência ou cursor sem timezone provocam FULL SYNC seguro.

A ordem é: validar resposta → `BEGIN` → aplicar produtos e barcodes → gravar estado/cursor → `COMMIT` → atualizar o espelho legado em melhor esforço. Falha HTTP, JSON/DTO inválido ou rollback preservam cache e cursor anteriores.
# Hardening de integridade e recovery (27/09/2026)

O startup executa `PRAGMA integrity_check`; falha bloqueia operação/reset e nunca apaga automaticamente o banco. A linha `active_payment` é crítica, atômica e impede factory reset. Identidade ausente com checkpoint usa `terminal_id` persistido para reconciliação antes de permitir reativação. Veja [[terminal-local-state-recovery]].
