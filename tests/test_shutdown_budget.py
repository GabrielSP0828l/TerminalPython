"""BUG-047: SIGTERM cooperativo dentro do TimeoutStopSec da unit."""

import os
import signal
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

from app247_terminal.services import shutdown_budget


class FakeClock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now


class HungWorker:
    """QThread que nunca termina; ``wait`` consome o tempo concedido."""

    def __init__(self, clock, calls):
        self.clock = clock
        self.calls = calls

    def isRunning(self):
        return True

    def requestInterruption(self):
        pass

    def wait(self, ms):
        self.calls.append(ms)
        self.clock.now += ms / 1000
        return False


class ShutdownBudgetTest(unittest.TestCase):
    def tearDown(self):
        shutdown_budget.reset_for_tests()

    def test_inactive_budget_keeps_each_original_limit(self):
        self.assertFalse(shutdown_budget.shutdown_active())
        self.assertEqual(50000, shutdown_budget.wait_ms(50000))
        self.assertEqual(2, shutdown_budget.wait_seconds(2))

    def test_active_budget_is_shared_and_first_deadline_wins(self):
        clock = FakeClock()
        shutdown_budget.begin_shutdown(10, clock=clock)
        shutdown_budget.begin_shutdown(60, clock=clock)

        self.assertEqual(500, shutdown_budget.wait_ms(500))
        self.assertEqual(10000, shutdown_budget.wait_ms(50000))
        clock.now += 7
        self.assertEqual(3000, shutdown_budget.wait_ms(25000))
        self.assertEqual(3.0, shutdown_budget.wait_seconds(5))
        clock.now += 10
        self.assertEqual(0, shutdown_budget.wait_ms(25000))
        self.assertEqual(0.0, shutdown_budget.wait_seconds(2))

    def test_hung_payment_workers_never_exceed_budget(self):
        from app247_terminal.ui.screens.payment import PagamentoScreen

        clock = FakeClock()
        calls = []
        attributes = (
            "point_worker", "status_worker", "resume_worker",
            "active_recovery_worker", "cancel_worker",
        )
        screen = SimpleNamespace(parar_espera=lambda: None)
        for attribute in attributes:
            setattr(screen, attribute, HungWorker(clock, calls))

        shutdown_budget.begin_shutdown(20, clock=clock)
        started = clock.now
        PagamentoScreen.parar_workers(screen)

        # Antes: 5 × 25 s = 125 s, muito acima do TimeoutStopSec=30.
        self.assertEqual(5, len(calls))
        self.assertLessEqual(clock.now - started, 20.0)
        self.assertEqual(20000, calls[0])
        self.assertEqual([0, 0, 0, 0], calls[1:])


class SigtermEndToEndTest(unittest.TestCase):
    def test_sigterm_runs_cooperative_shutdown_and_exits_zero(self):
        project_root = Path(__file__).resolve().parents[1]
        script = textwrap.dedent("""
            import sys, time
            from unittest.mock import patch
            from PyQt5.QtCore import QThread
            from PyQt5.QtWidgets import QApplication
            import app247_terminal.application as application
            from app247_terminal import main
            from app247_terminal.services import shutdown_budget

            class Hung(QThread):
                def run(self):
                    time.sleep(30)

            class Window:
                def __init__(self):
                    self.shutdown_was_requested = False
                    self.worker = Hung()
                    self.worker.start()
                    print("READY", flush=True)

                def encerrar_por_sinal(self, name):
                    print("SIGNAL", name, flush=True)
                    shutdown_budget.begin_shutdown(1)
                    self.worker.requestInterruption()
                    self.worker.wait(shutdown_budget.wait_ms(25000))
                    self.shutdown_was_requested = True
                    QApplication.instance().quit()

            with patch.object(application, "MainWindow", Window), \\
                    patch("app247_terminal.runtime.prepare_runtime_layout"), \\
                    patch.object(application, "present_main_window"):
                sys.exit(main.run([]))
        """)
        with tempfile.TemporaryDirectory() as directory:
            environment = {
                key: value for key, value in os.environ.items()
                if not key.startswith("APP247_")
            }
            environment.update({
                "APP247_CONFIG_FILE": str(Path(directory) / "missing.env"),
                "APP247_ENV": "test",
                "APP247_DATA_DIR": directory,
                "APP247_API_URL": "",
                "APP247_WS_URL": "",
                "QT_QPA_PLATFORM": "offscreen",
                "PYTHONPATH": str(project_root / "src"),
            })
            process = subprocess.Popen(
                [sys.executable, "-c", script],
                cwd=directory,
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            try:
                line = process.stdout.readline()
                if line.strip() != "READY":
                    process.kill()
                    self.fail(process.communicate(timeout=10)[1])
                time.sleep(0.3)
                started = time.monotonic()
                process.send_signal(signal.SIGTERM)
                stdout, stderr = process.communicate(timeout=15)
            finally:
                if process.poll() is None:
                    process.kill()
            elapsed = time.monotonic() - started

        self.assertEqual(0, process.returncode, stderr)
        self.assertIn("SIGNAL SIGTERM", stdout)
        self.assertNotIn("Destroyed while thread", stderr)
        self.assertLess(elapsed, 5)


if __name__ == "__main__":
    unittest.main()
