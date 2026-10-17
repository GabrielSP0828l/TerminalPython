import logging
import os
import sys

from app247_terminal.version import APP_VERSION


def _apply_display() -> int:
    """Executa somente a operação CLI de orientação, sem iniciar a GUI."""
    from app247_terminal.services.display_service import (
        DisplayService,
        DisplayServiceError,
    )

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    orientation = os.getenv("DISPLAY_ORIENTATION", "").strip()
    service = DisplayService()
    try:
        if orientation:
            service.apply_orientation(orientation, persist=False)
        else:
            service.apply_saved()
    except DisplayServiceError as error:
        logging.getLogger(__name__).warning(
            "[DISPLAY] aplicação automática falhou reason=%s technical=%s",
            error.code,
            error.technical_message,
        )
        print(f"Não foi possível aplicar a orientação: {error.user_message}", file=sys.stderr)
        return 1
    return 0


def _run_gui(arguments: list[str]) -> int:
    """Inicializa o lifecycle completo somente para a execução gráfica normal."""
    from PyQt5.QtCore import Qt
    from PyQt5.QtWidgets import QApplication

    from app247_terminal.application import MainWindow, present_main_window
    from app247_terminal.config.settings import API_URL, DATABASE_PATH
    from app247_terminal.models.terminal import Terminal
    from app247_terminal.runtime import prepare_runtime_layout

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    prepare_runtime_layout()
    logger = logging.getLogger(__name__)
    logger.info("[API] Backend: %s", API_URL or "não configurado")
    logger.info("[SYNC] SQLite path: %s", DATABASE_PATH.resolve())
    try:
        Terminal.quarantine_if_corrupted()
    except OSError:
        # Sem conseguir preservar o arquivo, ele permanece; as leituras abaixo
        # tratam a identidade como ausente em vez de encerrar a GUI.
        logger.exception("[TERMINAL] não foi possível preservar terminal.json ilegível")
    terminal = Terminal.load_or_none()
    if terminal is not None:
        logger.info("[TERMINAL] UUID carregado: %s", terminal.terminalId)

    app = QApplication([sys.argv[0], *arguments])
    window = MainWindow()
    signal_handler = getattr(window, "encerrar_por_sinal", None)
    if signal_handler is not None:
        install_termination_bridge(app, signal_handler)
    app.setOverrideCursor(Qt.BlankCursor)
    present_main_window(window)
    exit_code = app.exec_()
    code = _gui_exit_code(
        exit_code, shutdown_was_requested=window.shutdown_was_requested
    )
    if window.shutdown_was_requested:
        # Serviços já foram parados dentro do orçamento. Um QThread que ainda
        # não terminou faria o Qt abortar ao destruir a janela; sair direto
        # evita core dump e código de falha num desligamento normal.
        logger.info("[LIFECYCLE] encerramento cooperativo concluído code=%s", code)
        logging.shutdown()
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(code)
    return code


TERMINATION_SIGNALS = ("SIGTERM", "SIGINT", "SIGHUP")


def install_termination_bridge(app, on_signal):
    """Entrega sinais de término ao loop Qt.

    Um handler Python puro só roda quando o interpretador volta a executar
    bytecode, o que não acontece enquanto ``exec_`` está bloqueado em C++. O
    ``set_wakeup_fd`` escreve o número do sinal num socketpair observado por um
    ``QSocketNotifier``, que acorda o loop e chama ``on_signal(nome)``.
    """
    import signal
    import socket

    from PyQt5.QtCore import QSocketNotifier

    reader, writer = socket.socketpair()
    reader.setblocking(False)
    writer.setblocking(False)
    previous_fd = signal.set_wakeup_fd(writer.fileno())
    names = {}
    for name in TERMINATION_SIGNALS:
        number = getattr(signal, name, None)
        if number is None:
            continue
        names[int(number)] = name
        # Handler não-padrão impede o término imediato; o trabalho real é
        # feito no slot do notifier, na thread da GUI.
        signal.signal(number, lambda *_args: None)

    notifier = QSocketNotifier(reader.fileno(), QSocketNotifier.Read, app)

    def _drain():
        try:
            data = reader.recv(64)
        except (BlockingIOError, InterruptedError):
            return
        for number in data:
            name = names.get(number)
            if name:
                on_signal(name)

    notifier.activated.connect(_drain)

    def restore():
        notifier.setEnabled(False)
        signal.set_wakeup_fd(previous_fd)
        reader.close()
        writer.close()

    # Mantém referências vivas pelo tempo da aplicação.
    app._app247_termination_bridge = (reader, writer, notifier, restore)
    return restore


def _gui_exit_code(exit_code: int, *, shutdown_was_requested: bool) -> int:
    """Mantém um encerramento administrativo como sucesso para systemd --user."""
    # O painel administrativo solicita um encerramento cooperativo. Qt retorna
    # normalmente 0 para quit(), e esta normalização mantém o contrato explícito
    # para Restart=on-failure da unit de usuário.
    if shutdown_was_requested:
        return 0
    return exit_code


def run(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if "--install-device-credential" in arguments:
        from app247_terminal.services.terminal_auth import install_credential_from_stdin

        install_credential_from_stdin()
        print("Credencial individual instalada com segurança.")
        return 0
    if "--version" in arguments:
        print(APP_VERSION)
        return 0
    if "--check" in arguments:
        from app247_terminal.diagnostics import check_installation

        print(f"app247-terminal {APP_VERSION}: diagnóstico da instalação")
        return check_installation()
    if "--apply-display" in arguments:
        return _apply_display()
    return _run_gui(arguments)


if __name__ == "__main__":
    raise SystemExit(run())
