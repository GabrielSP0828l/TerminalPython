"""Gera um manifesto assinado; use somente no pipeline confiável de release."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from updater.updater import canonical_manifest_payload, normalize_architecture
from updater.version import Version


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_private_key(path: Path, password_file: Path | None) -> Ed25519PrivateKey:
    password = password_file.read_bytes().rstrip(b"\r\n") if password_file else None
    loaded = serialization.load_pem_private_key(path.read_bytes(), password=password)
    if not isinstance(loaded, Ed25519PrivateKey):
        raise ValueError("A chave privada deve ser Ed25519")
    return loaded


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Assina manifesto de release App247")
    parser.add_argument("package", type=Path)
    parser.add_argument("--version", required=True)
    parser.add_argument("--architecture", default="aarch64")
    parser.add_argument("--private-key", required=True, type=Path)
    parser.add_argument("--password-file", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)

    package = args.package.resolve(strict=True)
    payload = {
        "schemaVersion": 1,
        "version": str(Version.parse(args.version)),
        "sha256": sha256_file(package),
        "architecture": normalize_architecture(args.architecture),
        "package": package.name,
    }
    signature = load_private_key(args.private_key, args.password_file).sign(
        canonical_manifest_payload(payload)
    )
    document = dict(payload, signature=base64.b64encode(signature).decode("ascii"))
    args.output.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Manifesto assinado criado em {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
