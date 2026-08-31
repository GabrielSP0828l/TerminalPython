import tempfile
import threading
import time
import unittest
from pathlib import Path

import requests

from database.DatabaseProdutos import DatabaseProdutos
from model.Produtos import Produtos
from model.Terminal import Terminal
from service.SyncService import SyncService


SYNC_1 = "2026-08-24T17:00:00.123Z"
SYNC_2 = "2026-08-24T17:05:00.456Z"


def product(product_id="product-1", code="111", price=4.0, active=True):
    return {
        "id": product_id,
        "codigo": code,
        "codigoInterno": f"SKU-{product_id}",
        "codigosBarras": [{
            "codigo": code, "tipo": "EAN", "principal": True, "ativo": True,
        }],
        "nome": f"Produto {code}",
        "descricao": "Descrição",
        "preco": price,
        "unidadeMedida": "UN",
        "categoria": "OUTROS",
        "peso": 1,
        "pesoTolerancia": 0,
        "foto": None,
        "ativo": active,
        "quantidade": 5,
        "createdAt": "2026-08-24T10:00:00Z",
        "updatedAt": "2026-08-24T11:00:00Z",
    }


def upsert(data):
    return {"productId": data["id"], "operation": "UPSERT", "produto": data}


def remove(product_id):
    return {"productId": product_id, "operation": "REMOVE", "produto": None}


def response(sync_at, full_sync, changes):
    return {"syncAt": sync_at, "fullSync": full_sync, "changes": changes}


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code

    def json(self, **kwargs):
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, params, timeout):
        self.calls.append({"url": url, "params": params, "timeout": timeout})
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class FailingRemoveDatabase(DatabaseProdutos):
    def _remove(self, product_id):
        raise RuntimeError("falha simulada no REMOVE")


class BlockingSyncService(SyncService):
    def __init__(self):
        super().__init__(interval_seconds=60)
        self.started = threading.Event()
        self.release = threading.Event()
        self.calls = []
        self.active = 0
        self.max_active = 0
        self._test_lock = threading.Lock()

    def sincronizar_produtos(self, origin="MANUAL"):
        with self._test_lock:
            self.calls.append(origin)
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        if len(self.calls) == 1:
            self.started.set()
            self.release.wait(1)
        with self._test_lock:
            self.active -= 1
        return True


class ProductSyncTest(unittest.TestCase):
    def make_service(self, root, responses, database_factory=DatabaseProdutos):
        terminal_path = root / "db" / "terminal.json"
        Terminal.from_dict({
            "terminalId": "terminal-a",
            "ativo": True,
            "activated": True,
        }).save(terminal_path)
        return SyncService(
            api_url="http://backend",
            db_path=root / "db" / "terminal.db",
            last_sync_path=root / "database" / "last_sync.txt",
            terminal_path=terminal_path,
            interval_seconds=0.02,
            session=FakeSession(responses),
            database_factory=database_factory,
        )

    def test_first_sync_uses_new_endpoint_and_backend_cursor(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload = response(SYNC_1, True, [upsert(product())])
            service = self.make_service(root, [FakeResponse(payload)])
            self.assertIsNone(service.get_last_sync())

            self.assertTrue(service.sincronizar_produtos("STARTUP"))

            database = DatabaseProdutos(root / "db" / "terminal.db")
            self.assertIsNotNone(database.buscar_por_codigo("111"))
            database.close()
            self.assertEqual(SYNC_1, service.get_last_sync())
            call = service.session.calls[0]
            self.assertEqual("http://backend/produtos/sync", call["url"])
            self.assertEqual({"uuidTerminal": "terminal-a"}, call["params"])
            self.assertEqual(10, call["timeout"])

    def test_incremental_updates_adds_and_removes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initial = response(SYNC_1, True, [
                upsert(product()), upsert(product("product-2", "222")),
            ])
            incremental = response(SYNC_2, False, [
                upsert(product(price=9.5)),
                remove("product-2"),
                upsert(product("product-3", "333")),
            ])
            service = self.make_service(
                root, [FakeResponse(initial), FakeResponse(incremental)]
            )
            self.assertTrue(service.sincronizar_produtos())
            self.assertTrue(service.sincronizar_produtos())

            database = DatabaseProdutos(root / "db" / "terminal.db")
            self.assertEqual("9.500000", database.buscar_por_codigo("111")[4])
            self.assertIsNone(database.buscar_por_codigo("222"))
            self.assertIsNotNone(database.buscar_por_codigo("333"))
            database.close()
            self.assertEqual(SYNC_2, service.get_last_sync())
            self.assertEqual(SYNC_1, service.session.calls[1]["params"]["lastSync"])

    def test_incremental_replaces_all_barcodes_atomically(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initial_product = product(code="111")
            initial_product["codigosBarras"].append({
                "codigo": "112", "tipo": "EAN", "principal": False, "ativo": True,
            })
            changed_product = product(code="222")
            changed_product["codigosBarras"] = [{
                "codigo": "222", "tipo": "EAN", "principal": True, "ativo": True,
            }]
            service = self.make_service(root, [
                FakeResponse(response(SYNC_1, True, [upsert(initial_product)])),
                FakeResponse(response(SYNC_2, False, [upsert(changed_product)])),
            ])

            self.assertTrue(service.sincronizar_produtos())
            database = DatabaseProdutos(root / "db" / "terminal.db")
            self.assertIsNotNone(database.buscar_por_codigo("111"))
            self.assertIsNotNone(database.buscar_por_codigo("112"))
            database.close()

            self.assertTrue(service.sincronizar_produtos())
            database = DatabaseProdutos(root / "db" / "terminal.db")
            self.assertIsNone(database.buscar_por_codigo("111"))
            self.assertIsNone(database.buscar_por_codigo("112"))
            self.assertEqual("product-1", database.buscar_por_codigo("222")[0])
            self.assertEqual(1, len(database.listar_codigos("product-1")))
            database.close()

    def test_full_sync_deactivates_products_absent_from_complete_state(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = DatabaseProdutos(root / "db" / "terminal.db")
            database.salvar_produto(SyncService._map_product(product("old", "999")))
            database.close()
            payload = response(SYNC_1, True, [upsert(product())])
            service = self.make_service(root, [FakeResponse(payload)])

            self.assertTrue(service.sincronizar_produtos())

            database = DatabaseProdutos(root / "db" / "terminal.db")
            self.assertIsNone(database.buscar_por_codigo("999"))
            self.assertIsNotNone(database.buscar_por_codigo("111"))
            database.close()

    def test_legacy_cursor_is_ignored_and_replaced_by_sync_at(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            service = self.make_service(
                root, [FakeResponse(response(SYNC_1, True, []))]
            )
            service.last_sync_path.parent.mkdir(parents=True)
            service.last_sync_path.write_text("2026-08-24 14:00:00", encoding="utf-8")

            self.assertIsNone(service.get_last_sync())
            self.assertTrue(service.sincronizar_produtos())
            self.assertNotIn("lastSync", service.session.calls[0]["params"])
            self.assertEqual(SYNC_1, service.last_sync_path.read_text(encoding="utf-8"))

    def test_empty_sqlite_with_existing_cursor_forces_full_sync(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            service = self.make_service(
                root, [FakeResponse(response(SYNC_2, True, [upsert(product())]))]
            )
            service.save_last_sync(SYNC_1)

            self.assertTrue(service.sincronizar_produtos("STARTUP"))

            self.assertNotIn("lastSync", service.session.calls[0]["params"])
            database = DatabaseProdutos(root / "db" / "terminal.db")
            state = database.obter_estado_catalogo()
            self.assertTrue(state["initialized"])
            self.assertTrue(state["consistent"])
            self.assertEqual(1, state["expected_active_count"])
            database.close()
            self.assertEqual(SYNC_2, service.get_last_sync())

    def test_confirmed_empty_full_sync_is_valid_for_next_incremental(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            service = self.make_service(root, [
                FakeResponse(response(SYNC_1, True, [])),
                FakeResponse(response(SYNC_2, False, [])),
            ])

            self.assertTrue(service.sincronizar_produtos())
            self.assertTrue(service.sincronizar_produtos())

            self.assertNotIn("lastSync", service.session.calls[0]["params"])
            self.assertEqual(SYNC_1, service.session.calls[1]["params"]["lastSync"])
            database = DatabaseProdutos(root / "db" / "terminal.db")
            state = database.obter_estado_catalogo()
            self.assertTrue(state["consistent"])
            self.assertEqual(0, state["expected_active_count"])
            database.close()

    def test_inconsistent_local_count_forces_recovery_full_sync(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            service = self.make_service(root, [
                FakeResponse(response(SYNC_1, True, [
                    upsert(product()), upsert(product("product-2", "222")),
                ])),
                FakeResponse(response(SYNC_2, True, [upsert(product())])),
            ])
            self.assertTrue(service.sincronizar_produtos())
            database = DatabaseProdutos(root / "db" / "terminal.db")
            database.cursor.execute("DELETE FROM produtos WHERE id = ?", ("product-2",))
            database.conn.commit()
            self.assertFalse(database.obter_estado_catalogo()["consistent"])
            database.close()

            self.assertTrue(service.sincronizar_produtos())

            self.assertNotIn("lastSync", service.session.calls[1]["params"])
            database = DatabaseProdutos(root / "db" / "terminal.db")
            self.assertTrue(database.obter_estado_catalogo()["consistent"])
            database.close()

    def test_offline_or_invalid_response_preserves_cache_and_cursor(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            service = self.make_service(root, [
                FakeResponse(response(SYNC_1, True, [upsert(product())])),
                requests.ConnectionError("offline"),
                FakeResponse({"syncAt": SYNC_2, "fullSync": False}),
                FakeResponse(ValueError("json inválido")),
            ])
            self.assertTrue(service.sincronizar_produtos())

            for _ in range(3):
                self.assertFalse(service.sincronizar_produtos())
                self.assertEqual(SYNC_1, service.get_last_sync())

            database = DatabaseProdutos(root / "db" / "terminal.db")
            self.assertIsNotNone(database.buscar_por_codigo("111"))
            database.close()

    def test_sqlite_failure_rolls_back_all_changes_and_does_not_advance_cursor(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            db_path = root / "db" / "terminal.db"
            initial = response(SYNC_1, True, [
                upsert(product(price=10)),
                upsert(product("product-2", "222", 5)),
            ])
            incremental = response(SYNC_2, False, [
                upsert(product(price=12)),
                upsert(product("product-3", "333", 7)),
                remove("product-2"),
            ])
            service = self.make_service(
                root,
                [FakeResponse(initial), FakeResponse(incremental)],
                FailingRemoveDatabase,
            )
            self.assertTrue(service.sincronizar_produtos())

            self.assertFalse(service.sincronizar_produtos())

            database = DatabaseProdutos(db_path)
            self.assertEqual("10.000000", database.buscar_por_codigo("111")[4])
            self.assertIsNotNone(database.buscar_por_codigo("222"))
            self.assertIsNone(database.buscar_por_codigo("333"))
            database.close()
            self.assertEqual(SYNC_1, service.get_last_sync())

    def test_events_while_sync_runs_are_coalesced_into_one_pending_sync(self):
        service = BlockingSyncService()
        self.assertTrue(service.request_sync("STARTUP"))
        self.assertTrue(service.started.wait(1))

        self.assertFalse(service.request_sync("WEBSOCKET_EVENT"))
        self.assertFalse(service.request_sync("WEBSOCKET_EVENT"))
        self.assertFalse(service.request_sync("WEBSOCKET_RECONNECT"))
        self.assertTrue(service.sync_pending)
        service.release.set()

        deadline = time.monotonic() + 1
        while service.sync_in_progress and time.monotonic() < deadline:
            time.sleep(0.005)
        self.assertEqual(["STARTUP", "PENDING"], service.calls)
        self.assertEqual(1, service.max_active)
        self.assertFalse(service.sync_in_progress)
        self.assertFalse(service.sync_pending)

    def test_periodic_service_refreshes_catalog_without_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            service = self.make_service(root, [
                FakeResponse(response(SYNC_1, True, [upsert(product(price=4))])),
                FakeResponse(response(SYNC_2, False, [upsert(product(price=7))])),
            ])
            service.iniciar_sync_em_thread()
            deadline = time.monotonic() + 1
            while len(service.session.calls) < 2 and time.monotonic() < deadline:
                time.sleep(0.005)
            service.stop()

            database = DatabaseProdutos(root / "db" / "terminal.db")
            self.assertEqual("7.000000", database.buscar_por_codigo("111")[4])
            database.close()


if __name__ == "__main__":
    unittest.main()
