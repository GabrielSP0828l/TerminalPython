"""Inspeção estrutural dos artefatos oficiais de release do Terminal App247."""

from __future__ import annotations

import argparse
import base64
import binascii
import grp
import json
import os
import posixpath
import pwd
import re
import subprocess
import tarfile
import tempfile
from pathlib import Path, PurePosixPath

from cryptography.hazmat.primitives import serialization

from updater.updater import (
    UpdateManifest,
    load_update_public_key,
    normalize_architecture,
    verify_manifest_signature,
    verify_package,
)


_ARTIFACT_PATTERN = re.compile(
    r"^app247-terminal-(?P<version>[0-9]+\.[0-9]+\.[0-9]+"
    r"(?:-[0-9A-Za-z.-]+)?)-(?P<architecture>[A-Za-z0-9_+-]+)\.tar\.gz$"
)
_FORBIDDEN_COMPONENTS = {
    ".git",
    ".venv",
    ".pytest_cache",
    "__pycache__",
    "build",
    "dist",
    "runtime",
    "secrets",
    "test",
    "tests",
    "venv",
}
_FORBIDDEN_NAMES = {
    ".env",
    "device-credential",
    "terminal.db",
    "terminal.json",
}
_PRIVATE_KEY_MARKERS = (
    b"-----BEGIN PRIVATE KEY-----",
    b"-----BEGIN ENCRYPTED PRIVATE KEY-----",
    b"-----BEGIN OPENSSH PRIVATE KEY-----",
    b"-----BEGIN ED25519 PRIVATE KEY-----",
)
_EXPECTED_TOP_LEVEL = {
    "app",
    "install.sh",
    "app247-terminal.service",
    "app247-terminal-launcher",
    "terminal.env.production.example",
    "update-signing-public-key.pem",
    "VERSION",
    "RELEASE_INFO.json",
}


def debian_architecture(value: str) -> str:
    """Converte aliases do kernel/manifesto para os nomes de pacote Debian."""
    normalized = value.strip().lower()
    aliases = {
        "aarch64": "arm64",
        "arm64": "arm64",
        "armv6l": "armhf",
        "armv7": "armhf",
        "armv7l": "armhf",
        "armhf": "armhf",
        "amd64": "amd64",
        "x86-64": "amd64",
        "x86_64": "amd64",
    }
    return aliases.get(normalized, normalized)


def detect_binary_architecture(executable: Path) -> str:
    """Detecta a arquitetura ELF real usando a ferramenta ``file``."""
    try:
        result = subprocess.run(
            ["file", "-Lb", str(executable)],
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as error:
        raise ValueError("Não foi possível inspecionar o binário com file") from error
    description = result.stdout.strip()
    lowered = description.lower()
    if "elf 64-bit" in lowered and ("x86-64" in lowered or "x86_64" in lowered):
        return "amd64"
    if "elf 64-bit" in lowered and ("aarch64" in lowered or "arm64" in lowered):
        return "arm64"
    if "elf 32-bit" in lowered and "arm" in lowered:
        return "armhf"
    raise ValueError(f"Arquitetura ELF não suportada: {description}")


def _normalized_member_path(name: str) -> PurePosixPath:
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError(f"Caminho inseguro no pacote: {name}")
    normalized = PurePosixPath(posixpath.normpath(name))
    if normalized.as_posix() in {"", "."}:
        raise ValueError(f"Caminho vazio no pacote: {name}")
    return normalized


def _validate_link(member: tarfile.TarInfo, root_name: str) -> None:
    if not member.issym() and not member.islnk():
        return
    link = PurePosixPath(member.linkname)
    if link.is_absolute():
        raise ValueError(f"Link absoluto proibido: {member.name}")
    member_path = _normalized_member_path(member.name)
    raw_target = link if member.islnk() else member_path.parent / link
    target = PurePosixPath(posixpath.normpath(raw_target.as_posix()))
    if not target.parts or target.parts[0] != root_name or ".." in target.parts:
        raise ValueError(f"Link escapa da raiz da release: {member.name}")


def _read_json_member(package: tarfile.TarFile, member: tarfile.TarInfo) -> dict:
    stream = package.extractfile(member)
    if stream is None:
        raise ValueError(f"Arquivo não pode ser lido: {member.name}")
    try:
        value = json.loads(stream.read().decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"JSON inválido: {member.name}") from error
    if not isinstance(value, dict):
        raise ValueError(f"JSON deve ser objeto: {member.name}")
    return value


def _public_key_bytes(path: Path) -> bytes:
    return load_update_public_key(path).public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )


def _validate_archive_members(
    archive: tarfile.TarFile,
    *,
    root_name: str,
    version: str,
    architecture: str,
    artifact: str,
) -> None:
    members = archive.getmembers()
    if not members:
        raise ValueError("Pacote vazio")
    by_name: dict[str, tarfile.TarInfo] = {}
    top_level: set[str] = set()
    for member in members:
        path = _normalized_member_path(member.name)
        if path.parts[0] != root_name:
            raise ValueError(f"Entrada fora da raiz {root_name}: {member.name}")
        member_key = member.name.rstrip("/")
        if member_key in by_name:
            raise ValueError(f"Entrada duplicada no pacote: {member.name}")
        by_name[member_key] = member
        if not (member.isfile() or member.isdir() or member.issym() or member.islnk()):
            raise ValueError(f"Tipo especial proibido no pacote: {member.name}")
        if len(path.parts) >= 2:
            top_level.add(path.parts[1])
        _validate_link(member, root_name)

        relative_parts = path.parts[1:]
        if any(part in _FORBIDDEN_COMPONENTS for part in relative_parts):
            raise ValueError(f"Conteúdo proibido no pacote: {member.name}")
        basename = path.name.lower()
        if (
            basename in _FORBIDDEN_NAMES
            or basename.startswith(".env.")
            or basename.endswith((".db", ".sqlite", ".sqlite3"))
            or ("device" in basename and "credential" in basename)
        ):
            raise ValueError(f"Dado operacional proibido no pacote: {member.name}")
        if "private" in basename and "key" in basename:
            raise ValueError(f"Possível chave privada no pacote: {member.name}")
        if member.isfile():
            stream = archive.extractfile(member)
            content = stream.read(64 * 1024).lstrip() if stream is not None else b""
            if any(content.startswith(marker) for marker in _PRIVATE_KEY_MARKERS):
                raise ValueError(f"Chave privada encontrada no pacote: {member.name}")

    unexpected = top_level.difference(_EXPECTED_TOP_LEVEL)
    missing = _EXPECTED_TOP_LEVEL.difference(top_level)
    if unexpected:
        raise ValueError(f"Entradas de topo inesperadas: {', '.join(sorted(unexpected))}")
    if missing:
        raise ValueError(f"Estrutura incompleta: {', '.join(sorted(missing))}")

    required = {
        f"{root_name}/app/app247-terminal": "executável",
        f"{root_name}/app/_internal": "diretório _internal",
        f"{root_name}/install.sh": "instalador",
        f"{root_name}/app247-terminal.service": "unidade systemd",
        f"{root_name}/app247-terminal-launcher": "launcher gráfico",
        f"{root_name}/terminal.env.production.example": "template de produção",
        f"{root_name}/update-signing-public-key.pem": "chave pública",
        f"{root_name}/VERSION": "VERSION",
        f"{root_name}/RELEASE_INFO.json": "RELEASE_INFO.json",
    }
    for name, label in required.items():
        if name not in by_name:
            raise ValueError(f"{label} ausente no pacote")
    if not by_name[f"{root_name}/app/app247-terminal"].isfile():
        raise ValueError("app247-terminal não é arquivo regular")
    if not by_name[f"{root_name}/app/app247-terminal"].mode & 0o111:
        raise ValueError("app247-terminal não é executável")
    if not by_name[f"{root_name}/app/_internal"].isdir():
        raise ValueError("_internal não é diretório")
    if not by_name[f"{root_name}/install.sh"].mode & 0o111:
        raise ValueError("install.sh não é executável")

    version_stream = archive.extractfile(by_name[f"{root_name}/VERSION"])
    packaged_version = version_stream.read().decode("utf-8").strip() if version_stream else ""
    if packaged_version != version:
        raise ValueError(f"VERSION divergente: {packaged_version!r}")
    release_info = _read_json_member(
        archive, by_name[f"{root_name}/RELEASE_INFO.json"]
    )
    expected_info = {
        "product": "app247-terminal",
        "version": version,
        "architecture": architecture,
        "packaging": "pyinstaller-onedir",
        "artifact": artifact,
        "signatureAlgorithm": "Ed25519",
    }
    for key, expected in expected_info.items():
        if release_info.get(key) != expected:
            raise ValueError(
                f"RELEASE_INFO.json divergente em {key}: "
                f"esperado={expected!r} atual={release_info.get(key)!r}"
            )


def _verify_standalone_installer(extracted_root: Path, public_key_path: Path) -> None:
    sandbox = extracted_root.parent / "installer-smoke"
    install_root = sandbox / "opt/app247"
    data_dir = sandbox / "var/lib/app247"
    config_dir = sandbox / "etc/app247"
    environment = os.environ.copy()
    environment.update(
        {
            "APP247_INSTALL_ROOT": str(install_root),
            "APP247_DATA_DIR": str(data_dir),
            "APP247_CONFIG_DIR": str(config_dir),
            "APP247_SYSTEMD_DIR": str(sandbox / "systemd"),
            "APP247_LAUNCHER_DESTINATION": str(
                sandbox / "usr/local/bin/app247-terminal-launcher"
            ),
            "APP247_MANAGE_SYSTEMD": "false",
            "APP247_SERVICE_USER": pwd.getpwuid(os.getuid()).pw_name,
            "APP247_SERVICE_GROUP": grp.getgrgid(os.getgid()).gr_name,
        }
    )
    result = subprocess.run(
        [str(extracted_root / "install.sh")],
        cwd=extracted_root,
        env=environment,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        details = (result.stderr or result.stdout).strip()
        raise ValueError(f"Instalador standalone falhou: {details}")
    version = (extracted_root / "VERSION").read_text(encoding="utf-8").strip()
    installed = install_root / "releases" / version / "app247-terminal"
    if not installed.is_file():
        raise ValueError("Instalador standalone não preparou a release esperada")
    installed_key = config_dir / "update-signing-public-key.pem"
    if _public_key_bytes(installed_key) != _public_key_bytes(public_key_path):
        raise ValueError("Instalador standalone instalou uma chave pública divergente")


def verify_release_archive(
    package_path: Path,
    manifest_path: Path,
    detached_signature_path: Path,
    public_key_path: Path,
) -> dict:
    package_path = package_path.resolve(strict=True)
    manifest_path = manifest_path.resolve(strict=True)
    detached_signature_path = detached_signature_path.resolve(strict=True)
    public_key_path = public_key_path.resolve(strict=True)
    manifest = UpdateManifest.load(manifest_path)
    verify_manifest_signature(manifest, public_key_path)
    verify_package(package_path, manifest)
    if package_path.name != manifest.package:
        raise ValueError("Nome do pacote diverge do manifesto")
    expected_manifest_name = (
        package_path.name.removesuffix(".tar.gz") + ".manifest.json"
    )
    if manifest_path.name != expected_manifest_name:
        raise ValueError("Nome do manifesto não segue o padrão oficial")
    if detached_signature_path.name != manifest_path.name + ".sig":
        raise ValueError("Nome da assinatura destacada não segue o padrão oficial")

    try:
        detached = base64.b64decode(
            detached_signature_path.read_text(encoding="ascii").strip(),
            validate=True,
        )
        embedded = base64.b64decode(manifest.signature, validate=True)
    except (UnicodeError, ValueError, binascii.Error) as error:
        raise ValueError("Assinatura destacada inválida") from error
    if detached != embedded:
        raise ValueError("Assinatura destacada diverge da assinatura do manifesto")

    artifact_match = _ARTIFACT_PATTERN.fullmatch(package_path.name)
    if not artifact_match:
        raise ValueError("Nome do artefato não segue o padrão oficial")
    version = artifact_match.group("version")
    architecture = debian_architecture(artifact_match.group("architecture"))
    if version != manifest.version:
        raise ValueError("Versão no nome diverge do manifesto")
    if normalize_architecture(architecture) != manifest.architecture:
        raise ValueError("Arquitetura no nome diverge do manifesto")
    root_name = f"app247-terminal-{version}"

    with tarfile.open(package_path, "r:gz") as archive:
        _validate_archive_members(
            archive,
            root_name=root_name,
            version=version,
            architecture=architecture,
            artifact=package_path.name,
        )
        with tempfile.TemporaryDirectory(prefix="app247-verify-") as directory:
            extraction_dir = Path(directory)
            archive.extractall(extraction_dir, filter="data")
            extracted_root = extraction_dir / root_name
            executable = extracted_root / "app/app247-terminal"
            binary_architecture = detect_binary_architecture(executable)
            if binary_architecture != architecture:
                raise ValueError(
                    "Arquitetura real diverge do nome: "
                    f"nome={architecture} binário={binary_architecture}"
                )
            packaged_key = extracted_root / "update-signing-public-key.pem"
            if _public_key_bytes(packaged_key) != _public_key_bytes(public_key_path):
                raise ValueError("Chave pública do pacote diverge da trust anchor")
            _verify_standalone_installer(extracted_root, public_key_path)

    return {
        "package": package_path.name,
        "version": version,
        "architecture": architecture,
        "sha256": manifest.sha256,
        "size": package_path.stat().st_size,
        "signatureAlgorithm": manifest.signature_algorithm or "Ed25519",
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    detect = subparsers.add_parser("detect-architecture")
    detect.add_argument("executable", type=Path)
    verify = subparsers.add_parser("verify")
    verify.add_argument("package", type=Path)
    verify.add_argument("manifest", type=Path)
    verify.add_argument("signature", type=Path)
    verify.add_argument("--public-key", required=True, type=Path)
    arguments = parser.parse_args(argv)
    if arguments.command == "detect-architecture":
        print(detect_binary_architecture(arguments.executable))
        return 0
    result = verify_release_archive(
        arguments.package,
        arguments.manifest,
        arguments.signature,
        arguments.public_key,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
