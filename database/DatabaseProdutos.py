import os
import sqlite3
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from config import DATABASE_PATH


class DatabaseProdutos:
    """Cache local versionado do catálogo; configuração do Terminal fica fora dele."""

    CATALOG_SCHEMA_VERSION = 2
    PRODUCT_COLUMNS = (
        "id, codigo, nome, preco_original, preco, em_promocao, promocao_id, "
        "promocao_nome, quantidade, categoria, unidade_medida, descricao, foto, "
        "peso, peso_tolerancia, created_at, updated_at, ativo, codigo_interno"
    )

    def __init__(self, db_name=DATABASE_PATH):
        db_name = os.fspath(db_name)
        os.makedirs(os.path.dirname(os.path.abspath(db_name)), exist_ok=True)
        self.conn = sqlite3.connect(db_name)
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.cursor = self.conn.cursor()
        self.create_table()

    @staticmethod
    def _now():
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _decimal_text(value, scale):
        if value is None or value == "":
            return None
        quantum = Decimal("1").scaleb(-scale)
        return str(Decimal(str(value)).quantize(quantum, rounding=ROUND_HALF_UP))

    def create_table(self):
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL
            )
        """)
        version_row = self.cursor.execute(
            "SELECT MAX(version) FROM schema_version"
        ).fetchone()
        version = version_row[0] if version_row and version_row[0] is not None else 0

        products_exists = self.cursor.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='produtos'"
        ).fetchone()
        if version < self.CATALOG_SCHEMA_VERSION:
            self._migrate_catalog(products_exists is not None)
        else:
            self._create_catalog_tables()

        self._create_sync_state()
        self.conn.commit()

    def _create_catalog_tables(self):
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS produtos (
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
                ativo INTEGER NOT NULL DEFAULT 1 CHECK (ativo IN (0, 1))
            )
        """)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS produto_codigo_barras (
                produto_id TEXT NOT NULL,
                codigo_barras TEXT NOT NULL,
                tipo TEXT NOT NULL DEFAULT 'INTERNO',
                principal INTEGER NOT NULL DEFAULT 0 CHECK (principal IN (0, 1)),
                ativo INTEGER NOT NULL DEFAULT 1 CHECK (ativo IN (0, 1)),
                updated_at TEXT,
                PRIMARY KEY (produto_id, codigo_barras),
                UNIQUE (codigo_barras),
                FOREIGN KEY (produto_id) REFERENCES produtos(id) ON DELETE CASCADE
            )
        """)
        self.cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_produtos_ativo ON produtos(ativo)"
        )
        self.cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_barcode_produto ON produto_codigo_barras(produto_id, ativo)"
        )

    def _create_sync_state(self):
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS catalog_sync_state (
                singleton_id INTEGER PRIMARY KEY CHECK (singleton_id = 1),
                initialized INTEGER NOT NULL DEFAULT 0,
                expected_active_count INTEGER NOT NULL DEFAULT 0,
                last_sync_at TEXT
            )
        """)
        columns = {
            row[1] for row in self.cursor.execute(
                "PRAGMA table_info(catalog_sync_state)"
            ).fetchall()
        }
        if "last_sync_at" not in columns:
            self.cursor.execute(
                "ALTER TABLE catalog_sync_state ADD COLUMN last_sync_at TEXT"
            )
        self.cursor.execute("""
            INSERT OR IGNORE INTO catalog_sync_state (
                singleton_id, initialized, expected_active_count, last_sync_at
            ) VALUES (1, 0, 0, NULL)
        """)

    def _migrate_catalog(self, products_exists):
        try:
            self.cursor.execute("BEGIN")
            legacy_rows = []
            if products_exists:
                columns = [
                    row[1] for row in self.cursor.execute(
                        "PRAGMA table_info(produtos)"
                    ).fetchall()
                ]
                legacy_rows = [
                    dict(zip(columns, row))
                    for row in self.cursor.execute("SELECT * FROM produtos").fetchall()
                ]
                self.cursor.execute("ALTER TABLE produtos RENAME TO produtos_legacy")

            self._create_catalog_tables()
            for row in legacy_rows:
                product_id = str(row.get("id"))
                legacy_code = row.get("codigo") or row.get("codigo_interno") or product_id
                original = row.get("preco_original", row.get("preco", "0"))
                applied = row.get("preco", original)
                self.cursor.execute("""
                    INSERT INTO produtos (
                        id, codigo_interno, nome, preco_original, preco,
                        em_promocao, promocao_id, promocao_nome, quantidade,
                        categoria, unidade_medida, descricao, foto, peso,
                        peso_tolerancia, created_at, updated_at, ativo
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    product_id, str(legacy_code), row.get("nome") or "Produto",
                    self._decimal_text(original, 6), self._decimal_text(applied, 6),
                    1 if row.get("em_promocao") else 0, row.get("promocao_id"),
                    row.get("promocao_nome"), self._decimal_text(row.get("quantidade"), 3),
                    row.get("categoria"), row.get("unidade_medida"), row.get("descricao"),
                    row.get("foto"), self._decimal_text(row.get("peso"), 3),
                    self._decimal_text(row.get("peso_tolerancia"), 3),
                    row.get("created_at") or row.get("create_at"),
                    row.get("updated_at") or row.get("update_at"),
                    1 if row.get("ativo", row.get("status", 1)) else 0,
                ))
                if legacy_code:
                    self.cursor.execute("""
                        INSERT OR IGNORE INTO produto_codigo_barras (
                            produto_id, codigo_barras, tipo, principal, ativo, updated_at
                        ) VALUES (?, ?, 'LEGACY', 1, 1, ?)
                    """, (product_id, str(legacy_code), self._now()))

            if products_exists:
                self.cursor.execute("DROP TABLE produtos_legacy")
                self._create_catalog_tables()
            self.cursor.execute(
                "INSERT OR REPLACE INTO schema_version(version, applied_at) VALUES (?, ?)",
                (self.CATALOG_SCHEMA_VERSION, self._now()),
            )
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

    def _product_select(self, barcode_expression):
        return f"""
            SELECT p.id, {barcode_expression} AS codigo, p.nome,
                   p.preco_original, p.preco, p.em_promocao, p.promocao_id,
                   p.promocao_nome, p.quantidade, p.categoria, p.unidade_medida,
                   p.descricao, p.foto, p.peso, p.peso_tolerancia,
                   p.created_at, p.updated_at, p.ativo, p.codigo_interno
            FROM produtos p
        """

    def salvar_produto(self, produto):
        try:
            self.cursor.execute("BEGIN")
            self._upsert(produto)
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

    def buscar_por_codigo(self, codigo):
        sql = self._product_select("b.codigo_barras") + """
            JOIN produto_codigo_barras b ON b.produto_id = p.id
            WHERE b.codigo_barras = ? AND b.ativo = 1 AND p.ativo = 1
        """
        return self.cursor.execute(sql, (str(codigo),)).fetchone()

    def listar_produtos(self):
        principal = "COALESCE((SELECT b.codigo_barras FROM produto_codigo_barras b " \
                    "WHERE b.produto_id=p.id AND b.ativo=1 " \
                    "ORDER BY b.principal DESC, b.codigo_barras LIMIT 1), p.codigo_interno)"
        return self.cursor.execute(self._product_select(principal)).fetchall()

    def listar_codigos(self, produto_id=None):
        if produto_id is None:
            return self.cursor.execute("""
                SELECT produto_id, codigo_barras, tipo, principal, ativo
                FROM produto_codigo_barras ORDER BY produto_id, principal DESC, codigo_barras
            """).fetchall()
        return self.cursor.execute("""
            SELECT produto_id, codigo_barras, tipo, principal, ativo
            FROM produto_codigo_barras WHERE produto_id = ?
            ORDER BY principal DESC, codigo_barras
        """, (produto_id,)).fetchall()

    def contar_produtos(self):
        total, ativos = self.cursor.execute(
            "SELECT COUNT(*), COALESCE(SUM(ativo = 1), 0) FROM produtos"
        ).fetchone()
        return {"total": total, "ativos": ativos}

    def obter_estado_catalogo(self):
        counts = self.contar_produtos()
        row = self.cursor.execute("""
            SELECT initialized, expected_active_count, last_sync_at
            FROM catalog_sync_state WHERE singleton_id = 1
        """).fetchone()
        initialized = bool(row and row[0])
        expected = row[1] if row else 0
        last_sync_at = row[2] if row else None
        consistent = initialized and expected == counts["ativos"]
        if not initialized:
            reason = "FULL SYNC ainda não confirmado"
        elif expected != counts["ativos"]:
            reason = (
                f"contagem ativa divergente: esperada={expected} "
                f"encontrada={counts['ativos']}"
            )
        else:
            reason = "cache inicializado e consistente"
        return {
            **counts,
            "initialized": initialized,
            "expected_active_count": expected,
            "last_sync_at": last_sync_at,
            "schema_version": self.CATALOG_SCHEMA_VERSION,
            "consistent": consistent,
            "reason": reason,
        }

    def obter_ultimo_sync(self):
        row = self.cursor.execute(
            "SELECT last_sync_at FROM catalog_sync_state WHERE singleton_id = 1"
        ).fetchone()
        return row[0] if row else None

    def salvar_ou_atualizar(self, produto):
        self.salvar_produto(produto)

    def substituir_catalogo(self, produtos):
        existentes = {row[0] for row in self.cursor.execute("SELECT id FROM produtos")}
        ativos = {row[0] for row in self.cursor.execute(
            "SELECT id FROM produtos WHERE ativo = 1"
        )}
        recebidos = {produto.id for produto in produtos}
        changes = [("UPSERT", produto.id, produto) for produto in produtos]
        self.aplicar_sync(True, changes)
        return {
            "inseridos": len(recebidos - existentes),
            "atualizados": len(recebidos & existentes),
            "desativados": len(ativos - recebidos),
        }

    def aplicar_sync(self, full_sync, changes, sync_at=None):
        try:
            self.cursor.execute("BEGIN")
            if full_sync:
                self.cursor.execute("UPDATE produtos SET ativo = 0")
                self.cursor.execute("DELETE FROM produto_codigo_barras")
            upserts = 0
            removes = 0
            for operation, product_id, produto in changes:
                if operation == "UPSERT":
                    self._upsert(produto)
                    upserts += 1
                elif operation == "REMOVE":
                    self._remove(product_id)
                    removes += 1
                else:
                    raise ValueError(f"Operação desconhecida: {operation}")
            active_count = self.cursor.execute(
                "SELECT COUNT(*) FROM produtos WHERE ativo = 1"
            ).fetchone()[0]
            self.cursor.execute("""
                UPDATE catalog_sync_state
                SET initialized = CASE WHEN ? THEN 1 ELSE initialized END,
                    expected_active_count = ?,
                    last_sync_at = COALESCE(?, last_sync_at)
                WHERE singleton_id = 1
            """, (1 if full_sync else 0, active_count, sync_at))
            self.conn.commit()
            return {
                "upserts": upserts,
                "removes": removes,
                "active_products": active_count,
            }
        except Exception:
            self.conn.rollback()
            raise

    def _remove(self, product_id):
        self.cursor.execute("UPDATE produtos SET ativo = 0 WHERE id = ?", (product_id,))
        self.cursor.execute(
            "DELETE FROM produto_codigo_barras WHERE produto_id = ?", (product_id,)
        )

    def _upsert(self, produto):
        self.cursor.execute("""
            INSERT INTO produtos (
                id, codigo_interno, nome, preco_original, preco, em_promocao,
                promocao_id, promocao_nome, quantidade, categoria,
                unidade_medida, descricao, foto, peso, peso_tolerancia,
                created_at, updated_at, ativo
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                codigo_interno = excluded.codigo_interno,
                nome = excluded.nome,
                preco_original = excluded.preco_original,
                preco = excluded.preco,
                em_promocao = excluded.em_promocao,
                promocao_id = excluded.promocao_id,
                promocao_nome = excluded.promocao_nome,
                quantidade = excluded.quantidade,
                categoria = excluded.categoria,
                unidade_medida = excluded.unidade_medida,
                descricao = excluded.descricao,
                foto = excluded.foto,
                peso = excluded.peso,
                peso_tolerancia = excluded.peso_tolerancia,
                created_at = excluded.created_at,
                updated_at = excluded.updated_at,
                ativo = excluded.ativo
        """, (
            produto.id, produto.codigo_interno, produto.nome,
            str(produto.preco_original), str(produto.preco),
            1 if produto.em_promocao else 0, produto.promocao_id,
            produto.promocao_nome, self._decimal_text(produto.quantidade, 3),
            produto.categoria, produto.unidade_medida, produto.descricao,
            produto.foto, self._decimal_text(produto.peso, 3),
            self._decimal_text(produto.peso_tolerancia, 3), produto.create_at,
            produto.update_at, 1 if produto.status else 0,
        ))
        self.cursor.execute(
            "DELETE FROM produto_codigo_barras WHERE produto_id = ?", (produto.id,)
        )
        codigos = produto.codigos_barras if produto.codigos_barras is not None else ([{
            "codigo": produto.codigo, "tipo": "LEGACY", "principal": True, "ativo": True
        }] if produto.codigo else [])
        for item in codigos:
            codigo = item.get("codigo") if isinstance(item, dict) else str(item)
            if not codigo:
                continue
            self.cursor.execute("""
                INSERT INTO produto_codigo_barras (
                    produto_id, codigo_barras, tipo, principal, ativo, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                produto.id, str(codigo),
                (item.get("tipo") or "INTERNO") if isinstance(item, dict) else "INTERNO",
                1 if isinstance(item, dict) and item.get("principal") else 0,
                0 if isinstance(item, dict) and item.get("ativo") is False else 1,
                produto.update_at,
            ))

    def close(self):
        self.conn.close()
