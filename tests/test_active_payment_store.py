import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication

from database.ActivePaymentStore import ActivePaymentStore
from model.CompraSession import CompraSession


class ActivePaymentStoreTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = ActivePaymentStore(Path(self.temp.name) / "terminal.db")

    def tearDown(self):
        self.temp.cleanup()

    def test_restart_restores_unresolved_attempt_with_all_correlation_ids(self):
        first = CompraSession(
            payment_store=self.store,
            terminal_id_provider=lambda: "terminal-a",
        )
        local_attempt = first.begin_payment()
        first.set_remote_ids(
            cart_id="cart-a", order_id="order-a", payment_id="transaction-a",
            payment_attempt_id="attempt-a",
        )
        first.mark_waiting()
        first.mark_cancelling()
        first.stop()

        restarted = CompraSession(payment_store=self.store)

        self.assertTrue(restarted.restore_pending_payment("terminal-a"))
        self.assertTrue(restarted.payment_in_flight)
        self.assertEqual(local_attempt, restarted.attempt_id)
        self.assertEqual("cart-a", restarted.cart_id)
        self.assertEqual("order-a", restarted.order_id)
        self.assertEqual("attempt-a", restarted.payment_attempt_id)
        self.assertEqual("CANCELLING", restarted.state)
        self.assertTrue(restarted.cancellation_requested)

    def test_cart_checkpoint_is_conditional_on_current_local_attempt(self):
        session = CompraSession(payment_store=self.store)
        attempt = session.begin_payment()

        self.assertFalse(self.store.checkpoint_cart("old-attempt", "cart-old"))
        self.assertTrue(session.persist_cart_checkpoint(attempt, "cart-current"))
        self.assertEqual("cart-current", self.store.load()["cart_id"])

    def test_terminal_result_removes_active_checkpoint_and_allows_retry(self):
        session = CompraSession(payment_store=self.store)
        session.begin_payment()
        session.set_remote_ids(order_id="order-a")

        self.assertEqual("FAILED", session.apply_status("order-a", "EXPIRED"))
        self.assertIsNone(self.store.load())
        self.assertIsNotNone(session.begin_payment())

    def test_initial_checkpoint_failure_blocks_worker_state_fail_closed(self):
        class BrokenStore:
            def save(self, _snapshot):
                raise OSError("disco indisponível")

            def clear(self):
                pass

        session = CompraSession(payment_store=BrokenStore())

        with self.assertRaises(OSError):
            session.begin_payment()

        self.assertFalse(session.payment_in_flight)
        self.assertIsNone(session.attempt_id)

    def test_failed_update_keeps_previous_financial_snapshot_atomic(self):
        self.store.save({
            "terminal_id": "terminal-a",
            "generation": "generation-a",
            "local_attempt_id": "local-a",
            "order_id": "order-a",
            "payment_attempt_id": "attempt-a",
            "status": "PROCESSING",
        })

        with self.assertRaises(KeyError):
            self.store.save({"terminal_id": "terminal-a"})

        recovered = self.store.load("terminal-a")
        self.assertEqual("order-a", recovered["order_id"])
        self.assertEqual("attempt-a", recovered["payment_attempt_id"])
        self.assertEqual("PROCESSING", recovered["status"])


if __name__ == "__main__":
    unittest.main()
