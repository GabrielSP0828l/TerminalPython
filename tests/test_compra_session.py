import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication
from PyQt5.QtTest import QTest

from model.CompraSession import CompraSession


class FakeClock:
    def __init__(self):
        self.value = 100.0

    def __call__(self):
        return self.value


class CompraSessionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.clock = FakeClock()
        self.session = CompraSession(clock=self.clock)

    def test_global_deadline_starts_once_and_is_not_restarted_by_payment(self):
        self.session.start_if_needed()
        started = self.session.started_at
        self.clock.value += 5 * 60
        self.session.begin_payment()
        self.assertEqual(started, self.session.started_at)
        self.assertEqual(5 * 60, self.session.remaining_seconds())

    def test_production_session_is_ten_minutes_and_retry_never_restarts_it(self):
        self.assertEqual(600, self.session.duration_seconds)
        self.session.start_if_needed()
        started = self.session.started_at
        self.clock.value += 601
        self.session.prepare_retry()
        self.assertEqual(started, self.session.started_at)
        self.assertEqual(0, self.session.remaining_seconds())

    def test_duration_is_configurable_for_fast_timeout_tests(self):
        short = CompraSession(clock=self.clock, duration_seconds=10)
        expired = []
        short.expired.connect(expired.append)
        short.start_if_needed()
        self.clock.value += 11
        short._tick()
        self.assertEqual(0, short.remaining_seconds())
        self.assertEqual("TIMEOUT_CHECK", short.state)
        self.assertEqual([short.generation], expired)

    def test_expiration_is_emitted_once_and_stops_checkout_actions(self):
        short = CompraSession(clock=self.clock, duration_seconds=2)
        expired = []
        short.expired.connect(expired.append)
        short.start_if_needed()
        generation = short.generation

        self.clock.value += 3
        short._tick()
        short._tick()

        self.assertEqual([generation], expired)
        self.assertFalse(short.active)
        self.assertFalse(short._timer.isActive())
        self.assertFalse(short.can_accept_checkout_actions())

    def test_qtimer_reaches_zero_and_emits_without_manual_tick(self):
        short = CompraSession(duration_seconds=2)
        remaining = []
        expired = []
        short.remaining_changed.connect(remaining.append)
        short.expired.connect(expired.append)
        short.start_if_needed()
        generation = short.generation

        QTest.qWait(2300)

        self.assertIn(1, remaining)
        self.assertIn(0, remaining)
        self.assertEqual([generation], expired)
        self.assertFalse(short._timer.isActive())

    def test_reset_starts_a_fresh_generation_with_full_deadline(self):
        self.session.start_if_needed()
        first_generation = self.session.generation
        self.clock.value += 601
        self.session._tick()
        self.session.reset()

        self.assertEqual(600, self.session.remaining_seconds())
        self.assertFalse(self.session._expired_emitted)
        self.assertTrue(self.session.start_if_needed())
        self.assertNotEqual(first_generation, self.session.generation)
        self.assertEqual(600, self.session.remaining_seconds())
        self.assertTrue(self.session.active)

    def test_double_click_creates_only_one_active_attempt(self):
        first = self.session.begin_payment()
        second = self.session.begin_payment()
        self.assertIsNotNone(first)
        self.assertIsNone(second)

    def test_processing_waits_and_definitive_failure_preserves_session(self):
        self.session.begin_payment()
        self.session.set_remote_ids(order_id="order-a")
        self.assertEqual("PROCESSING", self.session.apply_status("order-a", "WAITING_PAYMENT"))
        self.assertEqual("FAILED", self.session.apply_status("order-a", "REJECTED"))
        self.assertGreater(self.session.remaining_seconds(), 0)

    def test_old_order_event_cannot_affect_retry(self):
        self.session.begin_payment()
        self.session.set_remote_ids(order_id="order-a")
        self.session.apply_status("order-a", "FAILED")
        self.session.prepare_retry()
        self.session.begin_payment()
        self.session.set_remote_ids(order_id="order-b")
        self.assertEqual("IGNORED", self.session.apply_status("order-a", "APPROVED"))
        self.assertNotEqual("APPROVED", self.session.state)

    def test_approval_wins_while_timeout_is_being_reconciled(self):
        self.session.begin_payment()
        self.session.set_remote_ids(order_id="order-a")
        self.session.mark_timeout_check()
        self.assertEqual("APPROVED", self.session.apply_status("order-a", "APPROVED"))

    def test_event_from_old_payment_attempt_is_ignored(self):
        self.session.start_if_needed()
        self.session.begin_payment()
        self.session.set_remote_ids(
            order_id="order-a", payment_attempt_id="attempt-current"
        )

        self.assertEqual(
            "IGNORED",
            self.session.apply_status("order-a", "APPROVED", "attempt-old"),
        )
        self.assertTrue(self.session.payment_in_flight)
        self.assertEqual("STARTING_PAYMENT", self.session.state)


if __name__ == "__main__":
    unittest.main()
