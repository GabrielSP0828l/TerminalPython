"""Diagnóstico não destrutivo da instalação do Terminal App247."""

from __future__ import annotations

import os
import sqlite3
import stat
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import requests

from app247_terminal.config import settings
from app247_terminal.services.terminal_auth import (
    TerminalCredentialMissing,
    TerminalCredentialStore,
)
from app247_terminal.utils.resources import icon_path, image_path


@dataclass(frozen=True)
class DiagnosticResult:
    level: str
    name: str
    message: str


def _result(level: str, name: str, message: str) -> DiagnosticResult:
    return DiagnosticResult(level, name, message)


def _url_check(name: str, value: str, schemes: set[str]) -> DiagnosticResult:
    if not value:
        return _result("ERROR", name, "não configurada")
    parsed = urlparse(value)
    if parsed.scheme not in schemes or not parsed.netloc:
        return _result("ERROR", name, "URL inválida")
    lowered = value.lower()
    if "exemplo.app247.com" in lowered or "example." in lowered:
        return _result("ERROR", name, "ainda contém valor de exemplo")
    return _result("OK", name, f"configurada ({parsed.scheme})")


def _check_data_dir(path: Path) -> DiagnosticResult:
    if not path.exists():
        return _result("ERROR", "Diretório de dados", f"ausente: {path}")
    if not path.is_dir():
        return _result("ERROR", "Diretório de dados", f"não é diretório: {path}")
    if not os.access(path, os.R_OK | os.W_OK | os.X_OK):
        return _result("ERROR", "Diretório de dados", f"sem acesso de leitura/escrita: {path}")
    return _result("OK", "Diretório de dados", f"acessível: {path}")


def _check_environment_file(path: Path) -> DiagnosticResult:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return _result("ERROR", "Arquivo de ambiente", f"ausente: {path}")
    except OSError as error:
        return _result("ERROR", "Arquivo de ambiente", f"não pode ser inspecionado: {error}")
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        return _result("ERROR", "Arquivo de ambiente", "deve ser arquivo regular")
    if metadata.st_mode & 0o007:
        return _result("ERROR", "Arquivo de ambiente", "acessível por outros usuários")
    if not os.access(path, os.R_OK):
        return _result("ERROR", "Arquivo de ambiente", "sem permissão de leitura")
    return _result("OK", "Arquivo de ambiente", f"arquivo protegido: {path}")


def _check_security_settings() -> list[DiagnosticResult]:
    results = []
    password = settings.TERMINAL_ADMIN_PASSWORD.strip()
    if not password or password.lower() in {"sua_senha", "troque-por-uma-senha-forte"}:
        results.append(_result("ERROR", "Senha administrativa", "ausente ou ainda é placeholder"))
    else:
        results.append(_result("OK", "Senha administrativa", "configurada"))

    if settings.LEGACY_TERMINAL_AUTH_ENABLED:
        token = settings.TERMINAL_INTERNAL_TOKEN.strip()
        if not token or token.lower() == "seu_token":
            results.append(_result(
                "ERROR", "Autenticação legada",
                "habilitada sem token de migração válido",
            ))
        else:
            results.append(_result(
                "WARN", "Autenticação legada",
                "habilitada; desative após provisionar a credencial individual",
            ))
    else:
        results.append(_result("OK", "Autenticação legada", "desabilitada"))
    return results


def _check_database(path: Path) -> DiagnosticResult:
    if not path.exists():
        return _result("WARN", "SQLite", "ainda não criado (normal na primeira ativação)")
    if not path.is_file():
        return _result("ERROR", "SQLite", f"caminho não é arquivo: {path}")
    try:
        connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=3)
        try:
            integrity = connection.execute("PRAGMA integrity_check").fetchone()
        finally:
            connection.close()
    except sqlite3.Error as error:
        return _result("ERROR", "SQLite", f"falha ao abrir: {error}")
    if not integrity or integrity[0] != "ok":
        return _result("ERROR", "SQLite", "integrity_check falhou")
    return _result("OK", "SQLite", f"integridade confirmada: {path}")


def _check_credential(path: Path) -> DiagnosticResult:
    if not path.exists():
        return _result(
            "WARN", "Credencial individual",
            "ainda não instalada (necessária após a ativação)",
        )
    try:
        TerminalCredentialStore(path).load()
    except TerminalCredentialMissing as error:
        return _result("ERROR", "Credencial individual", str(error))
    return _result("OK", "Credencial individual", "formato e permissões válidos")


def _check_backend(api_url: str, session, timeout: float) -> DiagnosticResult:
    if not api_url:
        return _result("ERROR", "Backend", "teste não executado: URL ausente")
    try:
        response = session.get(f"{api_url.rstrip('/')}/terminal/health", timeout=timeout)
    except requests.RequestException as error:
        return _result("ERROR", "Backend", f"inacessível: {type(error).__name__}")
    if not 200 <= response.status_code < 300:
        return _result("ERROR", "Backend", f"health-check retornou HTTP {response.status_code}")
    return _result("OK", "Backend", f"health-check HTTP {response.status_code}")


def _check_release(current_link: Path, production: bool) -> DiagnosticResult:
    if not production:
        return _result("OK", "Release ativa", "dispensada no ambiente de desenvolvimento/teste")
    if not current_link.is_symlink():
        return _result("ERROR", "Release ativa", f"symlink ausente: {current_link}")
    try:
        target = current_link.resolve(strict=True)
    except OSError:
        return _result("ERROR", "Release ativa", f"symlink quebrado: {current_link}")
    if not (target / "app247-terminal").is_file():
        return _result("ERROR", "Release ativa", f"executável ausente em: {target}")
    return _result("OK", "Release ativa", f"versão {settings.APP_VERSION} em {target}")


def run_diagnostics(
    *,
    session=requests,
    backend_timeout: float = 5,
    current_link: Path | None = None,
) -> list[DiagnosticResult]:
    results = [
        _url_check("API URL", settings.API_URL, {"http", "https"}),
        _url_check("WebSocket URL", settings.WS_URL, {"ws", "wss"}),
    ]
    if settings.IS_PRODUCTION:
        results.append(_check_environment_file(settings.CONFIG_ENV_PATH))
        results.extend(_check_security_settings())
    try:
        image_path("logo.png")
        icon_path("checked.svg")
        results.append(_result("OK", "Assets", "logo e ícones encontrados"))
    except FileNotFoundError as error:
        results.append(_result("ERROR", "Assets", str(error)))
    results.extend((
        _check_data_dir(settings.DATA_DIR),
        _check_database(settings.DATABASE_PATH),
        _check_credential(settings.DEVICE_CREDENTIAL_PATH),
        _check_backend(settings.API_URL, session, backend_timeout),
        _check_release(
            current_link or Path(os.getenv("APP247_CURRENT_LINK", "/opt/app247/current")),
            settings.IS_PRODUCTION,
        ),
    ))
    return results


def print_diagnostics(results: list[DiagnosticResult]) -> int:
    for result in results:
        print(f"[{result.level}] {result.name}: {result.message}")
    errors = sum(result.level == "ERROR" for result in results)
    warnings = sum(result.level == "WARN" for result in results)
    print(f"Resumo: {errors} erro(s), {warnings} aviso(s)")
    return 1 if errors else 0


def check_installation() -> int:
    return print_diagnostics(run_diagnostics())
