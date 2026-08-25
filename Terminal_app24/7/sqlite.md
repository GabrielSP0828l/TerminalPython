# SQLite e persistência local

Voltar para [o índice](00-index.md). Fluxo detalhado em [[sincronizacao]].

## Paths canônicos

Os paths são derivados de `Path(config.py).resolve().parent`; não dependem mais do diretório de onde `python main.py` foi chamado.

| Path absoluto nesta instalação | Finalidade |
|---|---|
| `/home/jefiro/Documentos/projetos/TerminalPython/db/terminal.db` | cache local de produtos |
| `/home/jefiro/Documentos/projetos/TerminalPython/db/terminal.json` | identidade/ativação persistente |
| `/home/jefiro/Documentos/projetos/TerminalPython/database/last_sync.txt` | último `syncAt` do backend aplicado com sucesso |

O startup registra o path absoluto do SQLite. `FactoryResetService` usa a mesma raiz canônica.

## Schema de produtos

```sql
CREATE TABLE produtos (
    id TEXT PRIMARY KEY,
    codigo TEXT UNIQUE,
    nome TEXT,
    preco REAL,
    quantidade INTEGER,
    categoria TEXT,
    unidade_medida TEXT,
    descricao TEXT,
    foto TEXT,
    peso REAL,
    peso_tolerancia REAL,
    create_at TEXT,
    update_at TEXT,
    status INTEGER
);

CREATE TABLE catalog_sync_state (
    singleton_id INTEGER PRIMARY KEY CHECK (singleton_id = 1),
    initialized INTEGER NOT NULL DEFAULT 0,
    expected_active_count INTEGER NOT NULL DEFAULT 0
);
```

Instalações antigas com `id INTEGER` são migradas para `TEXT` ao abrir o banco. Os UUIDs do backend são preservados.

## Aplicação de alterações

`DatabaseProdutos.aplicar_sync` executa todo o lote em uma única transação. Em `fullSync=true`, primeiro marca todos os registros como inativos e então aplica os `UPSERT`; assim, ausentes no estado completo deixam de ser vendáveis. Em sync incremental, modifica somente os IDs listados: `UPSERT` usa `INSERT ... ON CONFLICT(id) DO UPDATE` e `REMOVE` define `status=0`.

`buscar_por_codigo` só devolve `status=1`. Qualquer falha no meio de UPSERT/REMOVE causa `ROLLBACK` de todo o lote; nenhum estado parcial chega ao scanner.

`catalog_sync_state` é criado automaticamente. Instalações anteriores começam com `initialized=0`, mesmo que possuam `last_sync.txt` ou produtos residuais, e executam um FULL de migração. FULL e alterações de produtos atualizam marcador/contagem na mesma transação. Antes de usar cursor, `obter_estado_catalogo` exige marcador e igualdade entre `expected_active_count` e o `COUNT(status=1)` real.

## `last_sync.txt`

O arquivo contém exatamente o `syncAt` devolvido pelo backend, sem conversão para horário local. Ausência ou cursor legado sem timezone fazem a próxima requisição omitir `lastSync`, provocando FULL SYNC seguro. Após sucesso, o cursor legado é substituído pelo valor atual.

A ordem é: validar resposta → `BEGIN` → aplicar todas as operações → `COMMIT` → gravar `syncAt` por substituição atômica do arquivo. Falha HTTP, JSON inválido, DTO inválido ou rollback não avançam o cursor.

## Estado verificado em 24 de agosto de 2026

Antes da correção, o banco canônico possuía zero produtos, nenhuma tabela de estado e cursor válido, logo solicitava incremental vazio. A migração real executou FULL vazio, marcou `initialized=1`, `expected_active_count=0` e somente então salvou o novo `syncAt`. Isso representa corretamente o condomínio sem associações.
