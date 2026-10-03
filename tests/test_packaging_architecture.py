import base64
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app247_terminal.runtime import prepare_runtime_layout
from app247_terminal.utils.resources import icon_path, image_path
from app247_terminal.version import APP_VERSION
from updater.installer import InstallLayout
from updater.updater import (
    UpdateManifest,
    canonical_manifest_payload,
    prepare_update,
    verify_manifest_signature,
    verify_package,
)
from updater.version import CURRENT_VERSION, Version


class PackagingArchitectureTest(unittest.TestCase):
    def test_arm64_build_uses_system_pyqt_without_pip_requirement(self):
        project_root = Path(__file__).resolve().parents[1]
        build_script = (project_root / "scripts/build.sh").read_text(encoding="utf-8")
        arm_requirements = (project_root / "requirements-arm64.txt").read_text(
            encoding="utf-8"
        )
        self.assertIn("--system-site-packages", build_script)
        self.assertIn("python3-pyqt5", build_script)
        requirement_names = {
            line.split("=", 1)[0].split("<", 1)[0].strip().lower()
            for line in arm_requirements.splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        }
        self.assertNotIn("pyqt5", requirement_names)
        self.assertNotIn("pyqt5_sip", requirement_names)

    def test_assets_are_resolved_without_current_working_directory(self):
        self.assertTrue(image_path("logo.png").is_file())
        self.assertTrue(icon_path("checked.svg").is_file())

    def test_version_has_one_package_source_of_truth(self):
        self.assertEqual(Version.parse(APP_VERSION), CURRENT_VERSION)
        self.assertLess(Version.parse("1.0.0-rc1"), Version.parse("1.0.0"))
        self.assertLess(Version.parse("1.0.0"), Version.parse("1.1.0"))

    def test_manifest_verifies_sha256_and_builds_release_plan(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package = root / "release.tar.gz"
            package.write_bytes(b"release-content")
            digest = hashlib.sha256(package.read_bytes()).hexdigest()
            manifest_path = root / "manifest.json"
            payload = {
                "schemaVersion": 1,
                "version": "2.0.0",
                "sha256": digest,
                "architecture": "aarch64",
                "package": package.name,
            }
            private_key = Ed25519PrivateKey.generate()
            payload["signature"] = base64.b64encode(
                private_key.sign(canonical_manifest_payload(payload))
            ).decode("ascii")
            manifest_path.write_text(json.dumps(payload), encoding="utf-8")
            public_key_path = root / "public.pem"
            public_key_path.write_bytes(private_key.public_key().public_bytes(
                serialization.Encoding.PEM,
                serialization.PublicFormat.SubjectPublicKeyInfo,
            ))
            os.chmod(public_key_path, 0o644)

            manifest = UpdateManifest.load(manifest_path)
            verify_manifest_signature(manifest, public_key_path)
            verify_package(package, manifest)
            layout = InstallLayout(root / "opt", root / "data", root / "etc")
            plan = prepare_update(
                package,
                manifest_path,
                layout,
                public_key_path=public_key_path,
                expected_architecture="arm64",
            )
            self.assertEqual(root / "opt/releases/2.0.0", plan.release_dir)
            self.assertFalse(plan.release_dir.exists())

    def test_manifest_signature_rejects_tampered_version(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            private_key = Ed25519PrivateKey.generate()
            public_key = root / "public.pem"
            public_key.write_bytes(private_key.public_key().public_bytes(
                serialization.Encoding.PEM,
                serialization.PublicFormat.SubjectPublicKeyInfo,
            ))
            os.chmod(public_key, 0o644)
            payload = {
                "schemaVersion": 1,
                "version": "2.0.0",
                "sha256": "0" * 64,
                "architecture": "aarch64",
                "package": "release.tar.gz",
            }
            payload["signature"] = base64.b64encode(
                private_key.sign(canonical_manifest_payload(payload))
            ).decode("ascii")
            payload["version"] = "2.0.1"
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Assinatura"):
                verify_manifest_signature(UpdateManifest.load(manifest_path), public_key)

    def test_legacy_runtime_state_is_copied_not_moved_or_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            legacy = root / "legacy"
            data = root / "data"
            (legacy / "db").mkdir(parents=True)
            legacy_db = legacy / "db/terminal.db"
            legacy_db.write_bytes(b"legacy-db")
            destination = data / "terminal.db"

            with patch("app247_terminal.runtime.SOURCE_ROOT", legacy), patch(
                "app247_terminal.runtime.DATABASE_PATH", destination
            ), patch("app247_terminal.runtime.TERMINAL_CONFIG_PATH", data / "terminal.json"), patch(
                "app247_terminal.runtime.DEVICE_CREDENTIAL_PATH", data / "device-credential"
            ), patch("app247_terminal.runtime.DISPLAY_ORIENTATION_PATH", data / "orientation"), patch(
                "app247_terminal.runtime.LAST_SYNC_PATH", data / "last_sync.txt"
            ):
                copied = prepare_runtime_layout()

            self.assertEqual(b"legacy-db", destination.read_bytes())
            self.assertEqual(b"legacy-db", legacy_db.read_bytes())
            self.assertEqual([(legacy_db, destination)], copied)

            destination.write_bytes(b"new-db")
            with patch("app247_terminal.runtime.SOURCE_ROOT", legacy), patch(
                "app247_terminal.runtime.DATABASE_PATH", destination
            ), patch("app247_terminal.runtime.TERMINAL_CONFIG_PATH", data / "terminal.json"), patch(
                "app247_terminal.runtime.DEVICE_CREDENTIAL_PATH", data / "device-credential"
            ), patch("app247_terminal.runtime.DISPLAY_ORIENTATION_PATH", data / "orientation"), patch(
                "app247_terminal.runtime.LAST_SYNC_PATH", data / "last_sync.txt"
            ):
                prepare_runtime_layout()
            self.assertEqual(b"new-db", destination.read_bytes())


if __name__ == "__main__":
    unittest.main()
