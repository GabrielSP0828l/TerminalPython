import sqlite3
import tempfile
import unittest
from pathlib import Path

from database.DatabaseProdutos import DatabaseProdutos
from model.Produtos import Produtos


class DatabaseProductsTest(unittest.TestCase):
    def test_migrates_integer_ids_and_accepts_backend_uuid(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "terminal.db"
            connection = sqlite3.connect(db_path)
            connection.execute("""
                CREATE TABLE produtos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, codigo TEXT UNIQUE,
                    nome TEXT, preco REAL, quantidade INTEGER, categoria TEXT,
                    unidade_medida TEXT, descricao TEXT, foto TEXT, peso REAL,
                    peso_tolerancia REAL, create_at TEXT, update_at TEXT, status INTEGER
                )
            """)
            connection.commit()
            connection.close()

            database = DatabaseProdutos(str(db_path))
            product = Produtos(
                id="7e1b9415-b145-4d66-8a69-03dd435188aa", codigo="789",
                nome="Leite", quantidade=2, preco=5.0, categoria="ALIMENTOS",
                status=True,
            )
            database.substituir_catalogo([product])
            self.assertEqual(product.id, database.buscar_por_codigo("789")[0])
            database.close()

    def test_snapshot_updates_fields_and_deactivates_missing_product(self):
        with tempfile.TemporaryDirectory() as directory:
            database = DatabaseProdutos(Path(directory) / "terminal.db")
            old = Produtos(
                id="product-1", codigo="111", nome="Antigo", quantidade=3,
                preco=4.0, categoria="OUTROS", status=True,
            )
            removed = Produtos(
                id="product-2", codigo="222", nome="Removido", quantidade=1,
                preco=2.0, categoria="OUTROS", status=True,
            )
            database.substituir_catalogo([old, removed])

            changed = Produtos(
                id="product-1", codigo="111", nome="Atualizado", quantidade=8,
                preco=9.5, categoria="ALIMENTOS", status=True,
            )
            new = Produtos(
                id="product-3", codigo="333", nome="Novo", quantidade=2,
                preco=1.5, categoria="OUTROS", status=True,
            )
            stats = database.substituir_catalogo([changed, new])

            self.assertEqual("Atualizado", database.buscar_por_codigo("111")[2])
            self.assertEqual(9.5, database.buscar_por_codigo("111")[3])
            self.assertIsNone(database.buscar_por_codigo("222"))
            self.assertIsNotNone(database.buscar_por_codigo("333"))
            self.assertEqual(
                {"inseridos": 1, "atualizados": 1, "desativados": 1}, stats
            )
            database.close()


if __name__ == "__main__":
    unittest.main()
