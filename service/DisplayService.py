import argparse
import logging
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from PyQt5.QtCore import QThread, pyqtSignal

from config import DISPLAY_ORIENTATION_PATH


logger = logging.getLogger(__name__)


class DisplayServiceError(RuntimeError):
    def __init__(self, code, user_message, technical_message=""):
        super().__init__(user_message)
        self.code = code
        self.user_message = user_message
        self.technical_message = technical_message


@dataclass(frozen=True)
class DisplayStatus:
    backend: str
    output: str
    orientation: str
    transform: str


class DisplayService:
    COMMAND_TIMEOUT_SECONDS = 8
    VALID_ORIENTATIONS = {"horizontal", "vertical"}

    def __init__(self, config_path=DISPLAY_ORIENTATION_PATH, runner=None, which=None, environ=None):
        self.config_path = Path(config_path)
        self._runner = runner or subprocess.run
        self._which = which or shutil.which
        self._environ = environ if environ is not None else os.environ

    def current_status(self):
        backend = self._detect_backend()
        if backend == "wlr-randr":
            return self._wlr_status()
        return self._xrandr_status()

    def apply_orientation(self, orientation, persist=True):
        orientation = str(orientation or "").strip().lower()
        if orientation not in self.VALID_ORIENTATIONS:
            raise DisplayServiceError(
                "INVALID_ORIENTATION",
                "A orientação selecionada não é válida.",
            )
        status = self.current_status()
        configured_vertical = self._environ.get("DISPLAY_TRANSFORM", "90").strip()
        if configured_vertical not in {"90", "270"}:
            configured_vertical = "90"
        transform = (
            status.transform
            if orientation == "vertical" and status.transform in {"90", "270"}
            else configured_vertical if orientation == "vertical" else "normal"
        )
        logger.info("[DISPLAY] output detectado=%s", status.output)
        logger.info("[DISPLAY] orientação atual=%s", status.transform)
        logger.info("[DISPLAY] alterando orientação=%s", transform)

        if status.backend == "wlr-randr":
            command = [
                self._which("wlr-randr"), "--output", status.output,
                "--transform", transform,
            ]
        else:
            rotation = (
                "left" if transform == "270"
                else "right" if orientation == "vertical"
                else "normal"
            )
            command = [self._which("xrandr"), "--output", status.output, "--rotate", rotation]
        self._run(command)
        if persist:
            self._persist(orientation)
        logger.info("[DISPLAY] orientação alterada")
        return DisplayStatus(status.backend, status.output, orientation, transform)

    def saved_orientation(self):
        try:
            value = self.config_path.read_text(encoding="utf-8").strip().lower()
        except FileNotFoundError:
            return None
        except OSError as error:
            raise DisplayServiceError(
                "CONFIG_READ_FAILED",
                "Não foi possível ler a orientação salva.",
                str(error),
            ) from error
        return value if value in self.VALID_ORIENTATIONS else None

    def apply_saved(self):
        orientation = self.saved_orientation()
        if orientation is None:
            return None
        return self.apply_orientation(orientation, persist=False)

    def _detect_backend(self):
        session_type = self._environ.get("XDG_SESSION_TYPE", "").lower()
        wayland = bool(self._environ.get("WAYLAND_DISPLAY")) or session_type == "wayland"
        if wayland:
            if self._which("wlr-randr"):
                return "wlr-randr"
            raise DisplayServiceError(
                "TOOL_UNAVAILABLE",
                "Não foi possível alterar a orientação nesta sessão gráfica.",
                "sessão Wayland sem wlr-randr",
            )
        if self._environ.get("DISPLAY") and self._which("xrandr"):
            return "xrandr"
        raise DisplayServiceError(
            "TOOL_UNAVAILABLE",
            "Não foi possível acessar o controle de orientação da tela.",
            "wlr-randr/xrandr indisponível para a sessão",
        )

    def _wlr_status(self):
        result = self._run([self._which("wlr-randr")])
        outputs = []
        current = None
        for line in result.stdout.splitlines():
            if line and not line[0].isspace():
                current = {"name": line.split()[0], "enabled": False, "transform": "normal"}
                outputs.append(current)
            elif current is not None:
                stripped = line.strip()
                if stripped.lower() == "enabled: yes":
                    current["enabled"] = True
                elif stripped.lower().startswith("transform:"):
                    current["transform"] = stripped.split(":", 1)[1].strip().lower()
        selected = self._select_output(outputs)
        transform = selected["transform"]
        orientation = "vertical" if transform in {"90", "270"} else "horizontal"
        return DisplayStatus("wlr-randr", selected["name"], orientation, transform)

    def _xrandr_status(self):
        result = self._run([self._which("xrandr"), "--query"])
        outputs = []
        pattern = re.compile(
            r"^(?P<name>\S+)\s+connected(?:\s+primary)?\s+"
            r"(?P<geometry>\d+x\d+[+-]\d+[+-]\d+)"
            r"(?:\s+(?P<rotation>normal|left|right|inverted))?"
        )
        for line in result.stdout.splitlines():
            match = pattern.match(line)
            if match:
                outputs.append({
                    "name": match.group("name"),
                    "enabled": True,
                    "transform": match.group("rotation") or "normal",
                })
        selected = self._select_output(outputs)
        transform = selected["transform"]
        orientation = "vertical" if transform in {"left", "right"} else "horizontal"
        return DisplayStatus("xrandr", selected["name"], orientation, transform)

    def _select_output(self, outputs):
        active = [output for output in outputs if output.get("enabled")]
        requested = self._environ.get("DISPLAY_OUTPUT", "").strip()
        if requested:
            selected = next((output for output in active if output["name"] == requested), None)
            if selected is None:
                raise DisplayServiceError(
                    "OUTPUT_NOT_FOUND",
                    "A saída de vídeo configurada não está ativa.",
                    f"output solicitado não encontrado: {requested}",
                )
            return selected
        if not active:
            raise DisplayServiceError(
                "OUTPUT_NOT_FOUND",
                "Nenhuma tela ativa foi encontrada.",
            )
        return active[0]

    def _run(self, command):
        try:
            result = self._runner(
                command,
                text=True,
                capture_output=True,
                timeout=self.COMMAND_TIMEOUT_SECONDS,
                check=False,
            )
        except subprocess.TimeoutExpired as error:
            raise DisplayServiceError(
                "TIMEOUT",
                "A alteração da orientação demorou demais.",
                "timeout do comando de display",
            ) from error
        except OSError as error:
            raise DisplayServiceError(
                "TOOL_UNAVAILABLE",
                "Não foi possível acessar o controle de orientação da tela.",
                str(error),
            ) from error
        if result.returncode != 0:
            raise DisplayServiceError(
                "COMMAND_FAILED",
                "Não foi possível alterar a orientação da tela.",
                "comando de display retornou erro",
            )
        return result

    def _persist(self, orientation):
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.config_path.with_suffix(".tmp")
            temporary.write_text(f"{orientation}\n", encoding="utf-8")
            os.replace(temporary, self.config_path)
        except OSError as error:
            raise DisplayServiceError(
                "CONFIG_WRITE_FAILED",
                "A tela foi alterada, mas não foi possível salvar a orientação.",
                str(error),
            ) from error


class DisplayWorker(QThread):
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str, str)

    def __init__(self, service, operation, parameters=None, parent=None):
        super().__init__(parent)
        self.service = service
        self.operation = operation
        self.parameters = dict(parameters or {})

    def run(self):
        try:
            result = getattr(self.service, self.operation)(**self.parameters)
            if not self.isInterruptionRequested():
                self.succeeded.emit(result)
        except DisplayServiceError as error:
            logger.warning(
                "[DISPLAY] operação=%s falhou reason=%s technical=%s",
                self.operation, error.code, error.technical_message,
            )
            if not self.isInterruptionRequested():
                self.failed.emit(error.code, error.user_message)
        except Exception:
            logger.exception("[DISPLAY] falha inesperada operação=%s", self.operation)
            if not self.isInterruptionRequested():
                self.failed.emit(
                    "COMMAND_FAILED",
                    "Não foi possível alterar a orientação da tela.",
                )


def _main():
    parser = argparse.ArgumentParser(description="Aplica orientação do display do Terminal")
    parser.add_argument("--apply", choices=sorted(DisplayService.VALID_ORIENTATIONS))
    parser.add_argument("--apply-saved", action="store_true")
    parser.add_argument("--no-persist", action="store_true")
    arguments = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    service = DisplayService()
    try:
        if arguments.apply:
            service.apply_orientation(arguments.apply, persist=not arguments.no_persist)
        elif arguments.apply_saved:
            service.apply_saved()
    except DisplayServiceError as error:
        logger.warning("[DISPLAY] startup falhou reason=%s technical=%s", error.code, error.technical_message)
        raise SystemExit(1)


if __name__ == "__main__":
    _main()
