"""Valida pacote/manifesto e produz um plano; não ativa releases."""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import os
import platform
import stat
from dataclasses import dataclass
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from app247_terminal.config.settings import UPDATE_PUBLIC_KEY_PATH

from updater.installer import InstallLayout, InstallPlan, build_install_plan
from updater.version import CURRENT_VERSION, Version


@dataclass(frozen=True)
class UpdateManifest:
    schema_version: int
    version: str
    sha256: str
    architecture: str
    package: str
    size: int | None
    signature_algorithm: str | None
    signature: str

    @classmethod
    def load(cls, path) -> "UpdateManifest":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("Manifesto deve ser um objeto JSON")
        required = {
            "schemaVersion", "version", "sha256", "architecture", "package", "signature"
        }
        optional = {"size", "signatureAlgorithm"}
        if missing := required.difference(data):
            raise ValueError(f"Manifesto incompleto: {', '.join(sorted(missing))}")
        if set(data).difference(required | optional):
            raise ValueError("Manifesto contém campos não reconhecidos")
        if data["schemaVersion"] != 1:
            raise ValueError("Versão de schema do manifesto não suportada")
        version = str(Version.parse(data["version"]))
        digest = str(data["sha256"]).strip().lower()
        if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
            raise ValueError("SHA-256 inválido no manifesto")
        architecture = normalize_architecture(str(data["architecture"]))
        package = str(data["package"])
        if not package or Path(package).name != package:
            raise ValueError("Nome de pacote inválido no manifesto")
        size = data.get("size")
        signature_algorithm = data.get("signatureAlgorithm")
        if (size is None) != (signature_algorithm is None):
            raise ValueError(
                "Metadados de tamanho e algoritmo devem aparecer juntos no manifesto"
            )
        if size is not None and (
            not isinstance(size, int) or isinstance(size, bool) or size <= 0
        ):
            raise ValueError("Tamanho de pacote inválido no manifesto")
        if signature_algorithm is not None and signature_algorithm != "Ed25519":
            raise ValueError("Algoritmo de assinatura não suportado")
        signature = str(data["signature"])
        try:
            base64.b64decode(signature, validate=True)
        except (ValueError, binascii.Error) as error:
            raise ValueError("Assinatura Base64 inválida") from error
        return cls(
            1,
            version,
            digest,
            architecture,
            package,
            size,
            signature_algorithm,
            signature,
        )

    def signed_payload(self) -> bytes:
        payload = {
            "schemaVersion": self.schema_version,
            "version": self.version,
            "sha256": self.sha256,
            "architecture": self.architecture,
            "package": self.package,
        }
        if self.size is not None:
            payload["size"] = self.size
            payload["signatureAlgorithm"] = self.signature_algorithm
        return canonical_manifest_payload(payload)


def canonical_manifest_payload(data: dict) -> bytes:
    """Serialização estável coberta pela assinatura Ed25519."""
    return json.dumps(
        data, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def normalize_architecture(value: str) -> str:
    normalized = value.strip().lower()
    aliases = {"arm64": "aarch64", "amd64": "x86_64"}
    return aliases.get(normalized, normalized)


def load_update_public_key(path) -> Ed25519PublicKey:
    key_path = Path(path)
    try:
        metadata = key_path.lstat()
    except OSError as error:
        raise ValueError("Chave pública de atualização indisponível") from error
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise ValueError("Chave pública deve ser um arquivo regular, não um link")
    if metadata.st_mode & 0o022:
        raise ValueError("Chave pública não pode ser gravável por grupo ou outros")
    production_key_dir = Path("/etc/app247")
    try:
        is_production_key = key_path.absolute().is_relative_to(production_key_dir)
    except AttributeError:  # pragma: no cover - compatibilidade Python < 3.9
        is_production_key = production_key_dir in key_path.absolute().parents
    if is_production_key and metadata.st_uid != 0:
        raise ValueError("Chave pública deve pertencer ao root em produção")
    try:
        descriptor = os.open(key_path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(descriptor, "rb") as stream:
            opened = os.fstat(stream.fileno())
            if (
                not stat.S_ISREG(opened.st_mode)
                or opened.st_mode & 0o022
                or opened.st_size > 16 * 1024
            ):
                raise ValueError("Proteção da chave pública inválida")
            encoded_key = stream.read(16 * 1024 + 1)
        loaded = serialization.load_pem_public_key(encoded_key)
    except (OSError, ValueError) as error:
        raise ValueError("Chave pública de atualização inválida") from error
    if not isinstance(loaded, Ed25519PublicKey):
        raise ValueError("A chave de atualização deve ser Ed25519")
    return loaded


def verify_manifest_signature(manifest: UpdateManifest, public_key_path) -> None:
    try:
        signature = base64.b64decode(manifest.signature, validate=True)
        load_update_public_key(public_key_path).verify(signature, manifest.signed_payload())
    except InvalidSignature as error:
        raise ValueError("Assinatura do manifesto inválida") from error


def sha256_file(path, chunk_size=1024 * 1024) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_package(package, manifest: UpdateManifest) -> None:
    package_path = Path(package)
    if manifest.size is not None and package_path.stat().st_size != manifest.size:
        raise ValueError(
            f"Tamanho divergente: esperado={manifest.size} "
            f"atual={package_path.stat().st_size}"
        )
    actual = sha256_file(package_path)
    if actual != manifest.sha256:
        raise ValueError(f"SHA-256 divergente: esperado={manifest.sha256} atual={actual}")


def prepare_update(
    package,
    manifest_path,
    layout=None,
    public_key_path=UPDATE_PUBLIC_KEY_PATH,
    expected_architecture=None,
) -> InstallPlan:
    manifest = UpdateManifest.load(manifest_path)
    verify_manifest_signature(manifest, public_key_path)
    package_path = Path(package)
    if package_path.name != manifest.package:
        raise ValueError("Pacote não corresponde ao nome assinado no manifesto")
    expected = normalize_architecture(expected_architecture or platform.machine())
    if manifest.architecture != expected:
        raise ValueError(
            f"Arquitetura incompatível: manifesto={manifest.architecture} host={expected}"
        )
    if Version.parse(manifest.version) <= CURRENT_VERSION:
        raise ValueError(
            f"Versão candidata {manifest.version} não é superior a {CURRENT_VERSION}"
        )
    verify_package(package, manifest)
    return build_install_plan(manifest.version, package, layout or InstallLayout())


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Valida uma futura atualização App247")
    parser.add_argument("package")
    parser.add_argument("manifest")
    parser.add_argument(
        "--public-key", default=str(UPDATE_PUBLIC_KEY_PATH),
        help="chave pública Ed25519 confiável (padrão: configuração APP247)",
    )
    arguments = parser.parse_args(argv)
    plan = prepare_update(
        arguments.package, arguments.manifest, public_key_path=arguments.public_key
    )
    print(f"Pacote válido para staging: {plan.release_dir}")
    print("Nenhuma release foi extraída ou ativada.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
