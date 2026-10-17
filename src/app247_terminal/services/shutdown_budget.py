"""Prazo único para o encerramento cooperativo do Terminal.

O systemd envia ``SIGTERM`` em ``systemctl stop``/``poweroff`` e mata o processo
após ``TimeoutStopSec`` (30 s na unit). Fora de um encerramento, cada espera de
worker mantém seu limite próprio; durante o encerramento, todas consomem o
mesmo orçamento para que a soma nunca ultrapasse esse prazo.
"""

from __future__ import annotations

import threading
import time

from app247_terminal.config.settings import SHUTDOWN_BUDGET_SECONDS

_lock = threading.Lock()
_deadline = None
_clock = time.monotonic


def begin_shutdown(seconds=None, clock=None):
    """Inicia o orçamento; chamadas repetidas mantêm o primeiro prazo."""
    global _deadline, _clock
    with _lock:
        if clock is not None:
            _clock = clock
        if _deadline is None:
            budget = SHUTDOWN_BUDGET_SECONDS if seconds is None else seconds
            _deadline = _clock() + max(0.0, float(budget))


def shutdown_active():
    with _lock:
        return _deadline is not None


def remaining_seconds():
    with _lock:
        if _deadline is None:
            return None
        return max(0.0, _deadline - _clock())


def wait_ms(cap_ms):
    """Limite de ``QThread.wait`` respeitando o orçamento, se ativo."""
    remaining = remaining_seconds()
    if remaining is None:
        return int(cap_ms)
    return max(0, min(int(cap_ms), int(remaining * 1000)))


def wait_seconds(cap_seconds):
    """Limite de ``Thread.join`` respeitando o orçamento, se ativo."""
    remaining = remaining_seconds()
    if remaining is None:
        return cap_seconds
    return max(0.0, min(float(cap_seconds), remaining))


def reset_for_tests():
    global _deadline, _clock
    with _lock:
        _deadline = None
        _clock = time.monotonic
