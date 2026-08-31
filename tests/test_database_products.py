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
            self.assertEqual(2, database.obter_estado_catalogo()["schema_version"])
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
            row = database.buscar_por_codigo("111")
            self.assertEqual("9.500000", row[3])
            self.assertEqual("9.500000", row[4])
            self.assertEqual("text", database.cursor.execute(
                "SELECT typeof(preco) FROM produtos WHERE id = 'product-1'"
            ).fetchone()[0])
            self.assertIsNone(database.buscar_por_codigo("222"))
            self.assertIsNotNone(database.buscar_por_codigo("333"))
            self.assertEqual(
                {"inseridos": 1, "atualizados": 1, "desativados": 1}, stats
            )
            database.close()

    def test_multiple_barcodes_point_to_same_product_and_config_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            db_path = root / "terminal.db"
            config_path = root / "terminal.json"
            config_path.write_text('{"terminalId":"terminal-a"}', encoding="utf-8")
            database = DatabaseProdutos(db_path)
            product = Produtos(
                id="product-1", codigo="111", codigo_interno="SKU-1",
                codigos_barras=[
                    {"codigo": "111", "tipo": "EAN", "principal": True, "ativo": True},
                    {"codigo": "222", "tipo": "EAN", "principal": False, "ativo": True},
                ],
                nome="Produto", quantidade="0.350", preco="10.165750",
                categoria="OUTROS", peso="0.350", peso_tolerancia="0.005",
            )
            database.salvar_produto(product)

            self.assertEqual("product-1", database.buscar_por_codigo("111")[0])
            self.assertEqual("product-1", database.buscar_por_codigo("222")[0])
            self.assertEqual("10.165750", database.buscar_por_codigo("222")[4])
            self.assertEqual("0.350", database.buscar_por_codigo("222")[8])
            self.assertEqual("text", database.cursor.execute(
                "SELECT typeof(peso) FROM produtos WHERE id='product-1'"
            ).fetchone()[0])
            database.close()
            self.assertEqual('{"terminalId":"terminal-a"}', config_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
