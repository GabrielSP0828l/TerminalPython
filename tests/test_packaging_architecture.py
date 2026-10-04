import base64
import hashlib
import json
import os
import grp
import pwd
import shutil
import subprocess
import tarfile
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
from updater.release_archive import (
    debian_architecture,
    detect_binary_architecture,
    verify_release_archive,
)
from updater.updater import (
    UpdateManifest,
    canonical_manifest_payload,
    normalize_architecture,
    prepare_update,
    verify_manifest_signature,
    verify_package,
)
from updater.version import CURRENT_VERSION, Version


class PackagingArchitectureTest(unittest.TestCase):
    def test_installer_can_prepare_then_activate_and_install_service_unit(self):
        project_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifact = root / "artifact"
            artifact.mkdir()
            executable = artifact / "app247-terminal"
            executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            executable.chmod(0o755)
            template = root / "terminal.env"
            template.write_text(
                "APP247_ENV=production\n"
                "APP247_API_URL=https://api.app247.test\n"
                "APP247_WS_URL=wss://api.app247.test\n"
                "APP247_DATA_DIR=/var/lib/app247\n",
                encoding="utf-8",
            )
            environment = os.environ.copy()
            environment.update({
                "APP247_ARTIFACT_DIR": str(artifact),
                "APP247_INSTALL_VERSION": "9.9.9-test",
                "APP247_INSTALL_ROOT": str(root / "opt"),
                "APP247_DATA_DIR": str(root / "data"),
                "APP247_CONFIG_DIR": str(root / "etc"),
                "APP247_CONFIG_TEMPLATE": str(template),
                "APP247_SYSTEMD_DIR": str(root / "systemd"),
                "APP247_LAUNCHER_DESTINATION": str(root / "bin/launcher"),
                "APP247_MANAGE_SYSTEMD": "false",
                "APP247_SERVICE_USER": pwd.getpwuid(os.getuid()).pw_name,
                "APP247_SERVICE_GROUP": grp.getgrgid(os.getgid()).gr_name,
            })

            subprocess.run(
                [str(project_root / "scripts/install.sh")],
                check=True,
                env=environment,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                [str(project_root / "scripts/install.sh"), "--activate"],
                check=True,
                env=environment,
                capture_output=True,
                text=True,
            )

            current = root / "opt/current"
            self.assertTrue(current.is_symlink())
            self.assertEqual(root / "opt/releases/9.9.9-test", current.resolve())
            unit = (root / "systemd/app247-terminal.service").read_text(encoding="utf-8")
            self.assertIn(f"EnvironmentFile=-{root}/etc/terminal.env", unit)
            self.assertIn(f"ExecStart={root}/opt/current/app247-terminal", unit)
            installed_environment = (root / "etc/terminal.env").read_text(encoding="utf-8")
            self.assertIn(f"APP247_DATA_DIR={root}/data", installed_environment)

    def test_release_archive_is_complete_signed_and_standalone(self):
        project_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binary_architecture = detect_binary_architecture(Path("/bin/true"))
            version = "9.8.7-rc.1"
            artifact_name = (
                f"app247-terminal-{version}-{binary_architecture}.tar.gz"
            )
            package_root = root / f"app247-terminal-{version}"
            (package_root / "app/_internal").mkdir(parents=True)
            shutil.copy2("/bin/true", package_root / "app/app247-terminal")
            required_sources = {
                project_root / "scripts/install.sh": package_root / "install.sh",
                project_root / "packaging/systemd/app247-terminal.service": (
                    package_root / "app247-terminal.service"
                ),
                project_root / "packaging/app247-terminal-launcher": (
                    package_root / "app247-terminal-launcher"
                ),
                project_root / "packaging/terminal.env.production.example": (
                    package_root / "terminal.env.production.example"
                ),
            }
            for source, destination in required_sources.items():
                shutil.copy2(source, destination)

            private_key = Ed25519PrivateKey.generate()
            public_key = root / "public.pem"
            public_key.write_bytes(
                private_key.public_key().public_bytes(
                    serialization.Encoding.PEM,
                    serialization.PublicFormat.SubjectPublicKeyInfo,
                )
            )
            public_key.chmod(0o644)
            shutil.copy2(public_key, package_root / "update-signing-public-key.pem")
            (package_root / "VERSION").write_text(version + "\n", encoding="utf-8")
            (package_root / "RELEASE_INFO.json").write_text(
                json.dumps(
                    {
                        "product": "app247-terminal",
                        "version": version,
                        "architecture": binary_architecture,
                        "packaging": "pyinstaller-onedir",
                        "artifact": artifact_name,
                        "signatureAlgorithm": "Ed25519",
                    }
                ),
                encoding="utf-8",
            )
            package = root / artifact_name
            with tarfile.open(package, "w:gz") as archive:
                archive.add(package_root, arcname=package_root.name)

            payload = {
                "schemaVersion": 1,
                "version": version,
                "sha256": hashlib.sha256(package.read_bytes()).hexdigest(),
                "size": package.stat().st_size,
                "architecture": normalize_architecture(binary_architecture),
                "package": artifact_name,
                "signatureAlgorithm": "Ed25519",
            }
            signature = private_key.sign(canonical_manifest_payload(payload))
            payload["signature"] = base64.b64encode(signature).decode("ascii")
            manifest = root / f"{artifact_name.removesuffix('.tar.gz')}.manifest.json"
            manifest.write_text(json.dumps(payload), encoding="utf-8")
            detached = root / f"{manifest.name}.sig"
            detached.write_text(payload["signature"] + "\n", encoding="ascii")

            result = verify_release_archive(package, manifest, detached, public_key)

            self.assertEqual(version, result["version"])
            self.assertEqual(binary_architecture, result["architecture"])
            self.assertEqual("Ed25519", result["signatureAlgorithm"])

    def test_release_archive_rejects_operational_state(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            architecture = detect_binary_architecture(Path("/bin/true"))
            version = "9.8.7"
            artifact_name = f"app247-terminal-{version}-{architecture}.tar.gz"
            package_root = root / f"app247-terminal-{version}"
            package_root.mkdir()
            (package_root / "terminal.db").write_bytes(b"secret-state")
            package = root / artifact_name
            with tarfile.open(package, "w:gz") as archive:
                archive.add(package_root, arcname=package_root.name)
            private_key = Ed25519PrivateKey.generate()
            public_key = root / "public.pem"
            public_key.write_bytes(
                private_key.public_key().public_bytes(
                    serialization.Encoding.PEM,
                    serialization.PublicFormat.SubjectPublicKeyInfo,
                )
            )
            public_key.chmod(0o644)
            payload = {
                "schemaVersion": 1,
                "version": version,
                "sha256": hashlib.sha256(package.read_bytes()).hexdigest(),
                "size": package.stat().st_size,
                "architecture": normalize_architecture(architecture),
                "package": artifact_name,
                "signatureAlgorithm": "Ed25519",
            }
            payload["signature"] = base64.b64encode(
                private_key.sign(canonical_manifest_payload(payload))
            ).decode("ascii")
            manifest = root / f"{artifact_name.removesuffix('.tar.gz')}.manifest.json"
            manifest.write_text(json.dumps(payload), encoding="utf-8")
            detached = root / f"{manifest.name}.sig"
            detached.write_text(payload["signature"], encoding="ascii")

            with self.assertRaisesRegex(ValueError, "operacional proibido"):
                verify_release_archive(package, manifest, detached, public_key)

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

    def test_debian_architecture_aliases_match_manifest_aliases(self):
        self.assertEqual("arm64", debian_architecture("aarch64"))
        self.assertEqual("armhf", debian_architecture("armv7l"))
        self.assertEqual("amd64", debian_architecture("x86_64"))

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

    def test_manifest_with_release_metadata_is_signed_and_verified(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package = root / "release.tar.gz"
            package.write_bytes(b"release-content")
            private_key = Ed25519PrivateKey.generate()
            public_key = root / "public.pem"
            public_key.write_bytes(
                private_key.public_key().public_bytes(
                    serialization.Encoding.PEM,
                    serialization.PublicFormat.SubjectPublicKeyInfo,
                )
            )
            public_key.chmod(0o644)
            payload = {
                "schemaVersion": 1,
                "version": "2.0.0",
                "sha256": hashlib.sha256(package.read_bytes()).hexdigest(),
                "size": package.stat().st_size,
                "architecture": "x86_64",
                "package": package.name,
                "signatureAlgorithm": "Ed25519",
            }
            payload["signature"] = base64.b64encode(
                private_key.sign(canonical_manifest_payload(payload))
            ).decode("ascii")
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(payload), encoding="utf-8")

            manifest = UpdateManifest.load(manifest_path)
            verify_manifest_signature(manifest, public_key)
            verify_package(package, manifest)
            self.assertEqual(package.stat().st_size, manifest.size)
            self.assertEqual("Ed25519", manifest.signature_algorithm)

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
