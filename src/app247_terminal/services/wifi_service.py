import logging
import os
import shutil
import subprocess
from dataclasses import dataclass

from PyQt5.QtCore import QThread, pyqtSignal


logger = logging.getLogger(__name__)


class WifiServiceError(RuntimeError):
    def __init__(self, code, user_message, technical_message=""):
        super().__init__(user_message)
        self.code = code
        self.user_message = user_message
        self.technical_message = technical_message


@dataclass(frozen=True)
class WifiNetwork:
    ssid: str
    signal: int
    security: str
    connected: bool = False
    profile_name: str = ""

    @property
    def protected(self):
        return self.security.strip().upper() not in {"", "--", "NONE"}

    @property
    def known(self):
        return bool(self.profile_name)

    @property
    def signal_label(self):
        if self.signal >= 75:
            return "Excelente"
        if self.signal >= 55:
            return "Bom"
        if self.signal >= 35:
            return "Médio"
        return "Fraco"


@dataclass(frozen=True)
class WifiStatus:
    enabled: bool
    connected: bool
    interface: str = ""
    ssid: str = ""
    signal: int = 0
    ip_address: str = ""

    @property
    def signal_label(self):
        return WifiNetwork(self.ssid, self.signal, "").signal_label


@dataclass(frozen=True)
class WifiSnapshot:
    status: WifiStatus
    networks: tuple


class WifiService:
    """Adapter seguro para o NetworkManager; nenhuma regra de UI vive aqui."""

    SCAN_TIMEOUT_SECONDS = 12
    STATUS_TIMEOUT_SECONDS = 3
    CONNECT_TIMEOUT_SECONDS = 18
    DISCONNECT_TIMEOUT_SECONDS = 12

    def __init__(self, runner=None, which=None, nmcli_path=None):
        self._runner = runner or subprocess.run
        self._which = which or shutil.which
        self.nmcli_path = nmcli_path or self._which("nmcli")

    def snapshot(self):
        self._ensure_available()
        enabled = self._wifi_enabled()
        interface = self._wifi_interface()
        if not enabled:
            return WifiSnapshot(WifiStatus(False, False, interface), tuple())

        logger.info("[WIFI] scan iniciado")
        profiles = self._saved_wifi_profiles()
        networks = self._scan(interface, profiles, rescan=True)
        current = next((network for network in networks if network.connected), None)
        ip_address = self._ip_address(interface) if current else ""
        status = WifiStatus(
            enabled=True,
            connected=current is not None,
            interface=interface,
            ssid=current.ssid if current else "",
            signal=current.signal if current else 0,
            ip_address=ip_address,
        )
        logger.info("[WIFI] redes encontradas=%s", len(networks))
        return WifiSnapshot(status, tuple(networks))

    def status(self):
        """Leitura leve para telemetria, sem scan ativo nem acesso a segredos."""
        self._ensure_available()
        enabled = self._wifi_enabled()
        interface = self._wifi_interface()
        if not enabled:
            return WifiStatus(False, False, interface)
        return self._status_for(interface)

    def connect(self, network, password=None):
        self._ensure_available()
        interface = self._wifi_interface()
        ssid = network.ssid
        logger.info("[WIFI] tentando conectar ssid=%s", ssid)

        if network.known and password is None:
            args = [
                "--wait", "12", "connection", "up", "id",
                network.profile_name, "ifname", interface,
            ]
            input_text = None
        else:
            args = [
                "--wait", "12", "device", "wifi", "connect", ssid,
                "ifname", interface,
            ]
            input_text = None
            if network.protected:
                if not password:
                    raise WifiServiceError(
                        "AUTH_REQUIRED",
                        "Digite a senha desta rede para continuar.",
                    )
                # --ask recebe o segredo por stdin; a senha não aparece em argv/ps.
                args.insert(0, "--ask")
                input_text = f"{password}\n"

        try:
            self._run(
                args,
                timeout=self.CONNECT_TIMEOUT_SECONDS,
                input_text=input_text,
                operation="connect",
            )
        except WifiServiceError as error:
            logger.warning("[WIFI] conexão falhou ssid=%s reason=%s", ssid, error.code)
            raise

        status = self._status_for(interface)
        if not status.connected or status.ssid != ssid:
            raise WifiServiceError(
                "NETWORK_UNAVAILABLE",
                "A rede não está mais disponível. Atualize a lista e tente novamente.",
            )
        logger.info("[WIFI] conectado ssid=%s", ssid)
        return status

    def disconnect(self):
        self._ensure_available()
        interface = self._wifi_interface()
        logger.info("[WIFI] desconectando interface=%s", interface)
        self._run(
            ["--wait", "8", "device", "disconnect", interface],
            timeout=self.DISCONNECT_TIMEOUT_SECONDS,
            operation="disconnect",
        )
        logger.info("[WIFI] desconectado interface=%s", interface)
        return WifiStatus(True, False, interface)

    def enable_wifi(self):
        self._ensure_available()
        logger.info("[WIFI] ativando rádio")
        self._run(
            ["radio", "wifi", "on"],
            timeout=self.DISCONNECT_TIMEOUT_SECONDS,
            operation="enable",
        )
        return self.snapshot()

    def _ensure_available(self):
        if not self.nmcli_path:
            raise WifiServiceError(
                "SERVICE_UNAVAILABLE",
                "Não foi possível acessar as configurações de Wi-Fi.",
                "nmcli não encontrado",
            )

    def _wifi_enabled(self):
        result = self._run(
            ["-t", "radio", "wifi"],
            timeout=self.STATUS_TIMEOUT_SECONDS,
            operation="status",
        )
        return result.stdout.strip().lower() == "enabled"

    def _wifi_interface(self):
        result = self._run(
            ["-t", "--escape", "yes", "-f", "DEVICE,TYPE,STATE", "device", "status"],
            timeout=self.STATUS_TIMEOUT_SECONDS,
            operation="status",
        )
        for line in result.stdout.splitlines():
            fields = self._split_terse(line)
            if len(fields) >= 2 and fields[1].lower() == "wifi":
                return fields[0]
        raise WifiServiceError(
            "NO_ADAPTER",
            "Nenhum adaptador Wi-Fi foi encontrado neste equipamento.",
        )

    def _saved_wifi_profiles(self):
        result = self._run(
            ["-t", "--escape", "yes", "-f", "NAME,TYPE", "connection", "show"],
            timeout=self.STATUS_TIMEOUT_SECONDS,
            operation="profiles",
        )
        profiles = {}
        for line in result.stdout.splitlines():
            fields = self._split_terse(line)
            if len(fields) < 2 or fields[1] not in {"802-11-wireless", "wifi"}:
                continue
            profile_name = fields[0]
            # O perfil criado pelo `nmcli device wifi connect` usa o SSID como
            # nome padrão. Perfis renomeados continuam conectáveis com senha,
            # sem multiplicar subprocessos nem alongar o scan indefinidamente.
            profiles[profile_name] = profile_name
        return profiles

    def _scan(self, interface, profiles, rescan):
        result = self._run(
            [
                "-t", "--escape", "yes", "-f", "IN-USE,SSID,SIGNAL,SECURITY",
                "device", "wifi", "list", "ifname", interface,
                "--rescan", "yes" if rescan else "no",
            ],
            timeout=self.SCAN_TIMEOUT_SECONDS if rescan else self.STATUS_TIMEOUT_SECONDS,
            operation="scan",
        )
        unique = {}
        for line in result.stdout.splitlines():
            fields = self._split_terse(line)
            if len(fields) < 4:
                continue
            in_use, ssid, raw_signal, security = fields[:4]
            if not ssid:
                continue
            try:
                signal = max(0, min(100, int(raw_signal)))
            except ValueError:
                signal = 0
            network = WifiNetwork(
                ssid=ssid,
                signal=signal,
                security=security,
                connected=in_use.strip() == "*",
                profile_name=profiles.get(ssid, ""),
            )
            previous = unique.get(ssid)
            if previous is None or (network.connected, network.signal) > (
                previous.connected, previous.signal
            ):
                unique[ssid] = network
        return sorted(
            unique.values(),
            key=lambda network: (
                not network.connected,
                -network.signal,
                network.ssid.casefold(),
            ),
        )

    def _status_for(self, interface):
        networks = self._scan(interface, {}, rescan=False)
        current = next((network for network in networks if network.connected), None)
        return WifiStatus(
            enabled=True,
            connected=current is not None,
            interface=interface,
            ssid=current.ssid if current else "",
            signal=current.signal if current else 0,
            ip_address=self._ip_address(interface) if current else "",
        )

    def _ip_address(self, interface):
        result = self._run(
            ["-g", "IP4.ADDRESS", "device", "show", interface],
            timeout=self.STATUS_TIMEOUT_SECONDS,
            operation="status",
        )
        first = next((line.strip() for line in result.stdout.splitlines() if line.strip()), "")
        return first.split("/", 1)[0]

    def _run(self, args, timeout, operation, input_text=None):
        environment = os.environ.copy()
        environment.update({"LC_ALL": "C", "LANG": "C"})
        try:
            result = self._runner(
                [self.nmcli_path, "--colors", "no", *args],
                input=input_text,
                text=True,
                capture_output=True,
                timeout=timeout,
                check=False,
                env=environment,
            )
        except subprocess.TimeoutExpired as error:
            raise WifiServiceError(
                "TIMEOUT",
                "A operação de Wi-Fi demorou demais. Tente novamente.",
                f"timeout em {operation}",
            ) from error
        except OSError as error:
            raise WifiServiceError(
                "SERVICE_UNAVAILABLE",
                "Não foi possível acessar as configurações de Wi-Fi.",
                str(error),
            ) from error
        if result.returncode != 0:
            raise self._map_error(operation, result.stderr or result.stdout)
        return result

    @staticmethod
    def _map_error(operation, raw_message):
        message = str(raw_message or "").lower()
        if any(term in message for term in (
            "secrets were required", "no secrets", "invalid secrets",
            "authentication", "password", "802-11-wireless-security",
        )):
            return WifiServiceError(
                "AUTH_FAILED",
                "Não foi possível conectar. Verifique a senha da rede e tente novamente.",
                f"falha de autenticação em {operation}",
            )
        if any(term in message for term in (
            "not found", "no network", "not available", "was not provided by any",
        )):
            return WifiServiceError(
                "NETWORK_UNAVAILABLE",
                "A rede não está mais disponível. Atualize a lista e tente novamente.",
                f"rede indisponível em {operation}",
            )
        if "not authorized" in message or "permission" in message:
            return WifiServiceError(
                "PERMISSION_DENIED",
                "Este usuário não possui permissão para alterar o Wi-Fi.",
                f"permissão negada em {operation}",
            )
        return WifiServiceError(
            "OPERATION_FAILED",
            "Não foi possível concluir a operação de Wi-Fi.",
            f"nmcli falhou em {operation}",
        )

    @staticmethod
    def _split_terse(line):
        fields = []
        current = []
        escaped = False
        for character in line:
            if escaped:
                current.append(character)
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == ":":
                fields.append("".join(current))
                current = []
            else:
                current.append(character)
        if escaped:
            current.append("\\")
        fields.append("".join(current))
        return fields


class WifiWorker(QThread):
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
        except WifiServiceError as error:
            logger.warning(
                "[WIFI] operação=%s falhou reason=%s technical=%s",
                self.operation, error.code, error.technical_message,
            )
            if not self.isInterruptionRequested():
                self.failed.emit(error.code, error.user_message)
        except Exception:
            logger.exception("[WIFI] falha inesperada operação=%s", self.operation)
            if not self.isInterruptionRequested():
                self.failed.emit(
                    "OPERATION_FAILED",
                    "Não foi possível concluir a operação de Wi-Fi.",
                )
        finally:
            self.parameters.clear()
