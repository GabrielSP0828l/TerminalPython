# SQLite e persistência local

Voltar para [o índice](00-index.md). Fluxo detalhado em [[sincronizacao]].

## Paths canônicos

Os paths são derivados de `Path(config.py).resolve().parent`; não dependem mais do diretório de onde `python main.py` foi chamado.

| Path absoluto nesta instalação | Finalidade |
|---|---|
| `/home/jefiro/Documentos/projetos/TerminalPython/db/terminal.db` | cache local de produtos e checkpoint financeiro `active_payment` |
| `/home/jefiro/Documentos/projetos/TerminalPython/db/terminal.json` | identidade/ativação persistente |
| `/home/jefiro/Documentos/projetos/TerminalPython/database/last_sync.txt` | espelho legado do `syncAt`; o cursor transacional fica no SQLite |

O startup registra o path absoluto do SQLite. `FactoryResetService` usa a mesma raiz canônica.

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

`schema_version` registra a versão 2 do catálogo. Ao abrir banco antigo, o migrador transacional converte preços para `TEXT(6)`, quantidades/pesos para `TEXT(3)` e transforma o antigo `produtos.codigo` em barcode principal `LEGACY`. Somente o cache é alterado; UUID/configuração em `db/terminal.json`, orientação e administração são preservados.

## Pagamento ativo

`ActivePaymentStore` cria uma tabela independente da versão do catálogo:

```sql
CREATE TABLE active_payment (
    singleton_id INTEGER PRIMARY KEY CHECK (singleton_id = 1),
    terminal_id TEXT,
    generation TEXT NOT NULL,
    local_attempt_id TEXT NOT NULL,
    cart_id TEXT,
    order_id TEXT,
    payment_id TEXT,
    payment_attempt_id TEXT,
    cancellation_requested INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

Existe no máximo uma pendência por instalação. O registro nasce no primeiro clique válido e é atualizado com os IDs devolvidos. `checkpoint_cart` usa `local_attempt_id` como condição e grava `cart_id` antes do POST financeiro, impedindo worker antigo de sobrescrever uma tentativa nova. No startup o registro restaura apenas correlação/estado; o backend continua fonte de verdade. Resultado terminal ou confirmação HTTP segura remove a linha. Timeout, processo encerrado e queda de energia não removem.

`cancellation_requested=1` preserva `CANCELLING` em reinício ou queda de energia. A coluna é adicionada automaticamente em instalações existentes; ela não representa cancelamento confirmado.

O `UNIQUE(codigo_barras)` local é seguro porque há apenas um tenant no catálogo do Terminal. A regra global continua no backend por empresa.

## Aplicação de alterações

`DatabaseProdutos.aplicar_sync` grava produtos, códigos e cursor na mesma transação. FULL invalida o catálogo/cache de códigos antes dos UPSERTs. Incremental substitui todos os códigos do produto; REMOVE desativa o produto e remove seus códigos escaneáveis.

`buscar_por_codigo` usa JOIN com `produto_codigo_barras` e exige código/produto ativos. Qualquer falha causa rollback completo.

`catalog_sync_state` é criado automaticamente. Instalações anteriores começam com `initialized=0`, mesmo que possuam `last_sync.txt` ou produtos residuais, e executam um FULL de migração. FULL e alterações de produtos atualizam marcador/contagem na mesma transação. Antes de usar cursor, `obter_estado_catalogo` exige marcador e igualdade entre `expected_active_count` e o `COUNT(status=1)` real.

## Cursor de sincronização

`catalog_sync_state.last_sync_at` é a fonte de verdade e participa do commit do catálogo. `last_sync.txt` é somente fallback/espelho legado. Cursor ausente/inválido força FULL SYNC.

A ordem é: validar resposta → `BEGIN` → aplicar produto/barcodes → persistir estado e `syncAt` → `COMMIT` → atualizar espelho legado. Falhas não avançam o cursor.

## Factory reset da aplicação

No reset remoto confirmado e sem pagamento não resolvido, `FactoryResetService` remove o arquivo SQLite como
uma unidade, junto da ativação e dos cursores externos. Isso evita combinações
parciais como catálogo vazio com `initialized=1` ou Point antiga com
`paymentConfigured=true`. A recriação normal começa com
`catalog_sync_state.initialized=0`, sem `last_sync_at`, e força FULL SYNC após a
nova ativação. Wi-Fi, orientação, aplicativo e identidade física não ficam no
SQLite removido e são preservados. Veja [[terminal-lifecycle]].
