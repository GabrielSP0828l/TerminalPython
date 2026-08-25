import os
import sqlite3


class DatabaseProdutos:

    def __init__(self, db_name="db/terminal.db"):
        # cria pasta db se não existir
        os.makedirs("db", exist_ok=True)

        self.conn = sqlite3.connect(db_name)

        self.cursor = self.conn.cursor()

        self.create_table()

    def create_table(self):
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS produtos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
        self.conn.commit()

    def salvar_produto(self, produto):
        self.cursor.execute("""
        INSERT OR REPLACE INTO produtos (
            codigo, nome, preco, quantidade, categoria,
            unidade_medida, descricao, foto,
            peso, peso_tolerancia,
            create_at, update_at, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
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

        self.conn.commit()

    def buscar_por_codigo(self, codigo):
        self.cursor.execute(
            "SELECT * FROM produtos WHERE codigo = ?",
            (codigo,)
        )
        return self.cursor.fetchone()

    def listar_produtos(self):
        self.cursor.execute("SELECT * FROM produtos")
        rows = self.cursor.fetchall()

        return rows

    def salvar_ou_atualizar(self, produto):
        self.cursor.execute("""

        INSERT OR REPLACE INTO produtos (

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

        self.conn.commit()
