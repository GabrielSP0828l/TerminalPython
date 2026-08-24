import os
import sqlite3

from config import DATABASE_PATH


class DatabaseProdutos:

    def __init__(self, db_name=DATABASE_PATH):
        db_name = os.fspath(db_name)
        os.makedirs(os.path.dirname(os.path.abspath(db_name)), exist_ok=True)

        self.conn = sqlite3.connect(db_name)

        self.cursor = self.conn.cursor()

        self.create_table()

    def create_table(self):
        current = self.cursor.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='produtos'"
        ).fetchone()
        if current and "ID INTEGER" in (current[0] or "").upper():
            self._migrate_product_id_to_text()
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS produtos (
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
        )
        """)
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS catalog_sync_state (
            singleton_id INTEGER PRIMARY KEY CHECK (singleton_id = 1),
            initialized INTEGER NOT NULL DEFAULT 0,
            expected_active_count INTEGER NOT NULL DEFAULT 0
        )
        """)
        self.cursor.execute("""
        INSERT OR IGNORE INTO catalog_sync_state (
            singleton_id, initialized, expected_active_count
        ) VALUES (1, 0, 0)
        """)
        self.conn.commit()

    def _migrate_product_id_to_text(self):
        self.cursor.execute("BEGIN")
        self.cursor.execute("ALTER TABLE produtos RENAME TO produtos_legacy")
        self.cursor.execute("""
            CREATE TABLE produtos (
                id TEXT PRIMARY KEY, codigo TEXT UNIQUE, nome TEXT, preco REAL,
                quantidade REAL, categoria TEXT, unidade_medida TEXT, descricao TEXT,
                foto TEXT, peso REAL, peso_tolerancia REAL, create_at TEXT,
                update_at TEXT, status INTEGER
            )
        """)
        self.cursor.execute("""
            INSERT INTO produtos
            SELECT CAST(id AS TEXT), codigo, nome, preco, quantidade, categoria,
                   unidade_medida, descricao, foto, peso, peso_tolerancia,
                   create_at, update_at, status
            FROM produtos_legacy
        """)
        self.cursor.execute("DROP TABLE produtos_legacy")
        self.conn.commit()

    def salvar_produto(self, produto):
        self._upsert(produto)
        self.conn.commit()

    def buscar_por_codigo(self, codigo):
        self.cursor.execute(
            "SELECT * FROM produtos WHERE codigo = ? AND status = 1",
            (codigo,)
        )
        return self.cursor.fetchone()

    def listar_produtos(self):
        self.cursor.execute("SELECT * FROM produtos")
        rows = self.cursor.fetchall()

        return rows

    def contar_produtos(self):
        total, ativos = self.cursor.execute(
            "SELECT COUNT(*), COALESCE(SUM(status = 1), 0) FROM produtos"
        ).fetchone()
        return {"total": total, "ativos": ativos}

    def obter_estado_catalogo(self):
        counts = self.contar_produtos()
        row = self.cursor.execute(
            "SELECT initialized, expected_active_count "
            "FROM catalog_sync_state WHERE singleton_id = 1"
        ).fetchone()
        initialized = bool(row and row[0])
        expected = row[1] if row else 0
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
            "consistent": consistent,
            "reason": reason,
        }

    def salvar_ou_atualizar(self, produto):
        self._upsert(produto)
        self.conn.commit()

    def substituir_catalogo(self, produtos):
        try:
            self.cursor.execute("BEGIN")
            existentes = {
                row[0]: row for row in self.cursor.execute(
                    "SELECT id, codigo, nome, preco, quantidade, categoria, "
                    "unidade_medida, descricao, foto, peso, peso_tolerancia, "
                    "create_at, update_at, status FROM produtos"
                ).fetchall()
            }
            ids_recebidos = {produto.id for produto in produtos}
            inseridos = sum(produto.id not in existentes for produto in produtos)
            atualizados = len(produtos) - inseridos
            desativados = sum(
                row[13] == 1 and product_id not in ids_recebidos
                for product_id, row in existentes.items()
            )
            self.cursor.execute("UPDATE produtos SET status = 0")
            for produto in produtos:
                self._upsert(produto)
            self.conn.commit()
            return {
                "inseridos": inseridos,
                "atualizados": atualizados,
                "desativados": desativados,
            }
        except Exception:
            self.conn.rollback()
            raise

    def aplicar_sync(self, full_sync, changes):
        try:
            self.cursor.execute("BEGIN")
            if full_sync:
                self.cursor.execute("UPDATE produtos SET status = 0")
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
                "SELECT COUNT(*) FROM produtos WHERE status = 1"
            ).fetchone()[0]
            if full_sync:
                self.cursor.execute(
                    "UPDATE catalog_sync_state "
                    "SET initialized = 1, expected_active_count = ? "
                    "WHERE singleton_id = 1",
                    (active_count,),
                )
            else:
                self.cursor.execute(
                    "UPDATE catalog_sync_state SET expected_active_count = ? "
                    "WHERE singleton_id = 1 AND initialized = 1",
                    (active_count,),
                )
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
        self.cursor.execute(
            "UPDATE produtos SET status = 0 WHERE id = ?",
            (product_id,),
        )

    def _upsert(self, produto):
        self.cursor.execute("""

        INSERT INTO produtos (

            id,
            codigo,
            nome,
            preco,
            quantidade,
            categoria,
            unidade_medida,
            descricao,
            foto,
            peso,
            peso_tolerancia,
            create_at,
            update_at,
            status

        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            codigo = excluded.codigo,
            nome = excluded.nome,
            preco = excluded.preco,
            quantidade = excluded.quantidade,
            categoria = excluded.categoria,
            unidade_medida = excluded.unidade_medida,
            descricao = excluded.descricao,
            foto = excluded.foto,
            peso = excluded.peso,
            peso_tolerancia = excluded.peso_tolerancia,
            create_at = excluded.create_at,
            update_at = excluded.update_at,
            status = excluded.status

        """, (

            produto.id,
            produto.codigo,
            produto.nome,
            produto.preco,
            produto.quantidade,
            produto.categoria,
            produto.unidade_medida,
            produto.descricao,
            produto.foto,
            produto.peso,
            produto.peso_tolerancia,
            produto.create_at,
            produto.update_at,
            1 if produto.status else 0

        ))

    def close(self):
        self.conn.close()
