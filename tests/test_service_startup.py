"""Regressão do loop de ExecStartPre --apply-display na unit gráfica."""

import grp
import os
import pwd
import shutil
import socket
import subprocess
import tempfile
import time
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = PROJECT_ROOT / "packaging/app247-terminal-launcher"

# Unit encontrada no Raspberry de campo (sem marcador) e que entrava em loop.
LEGACY_FIELD_UNIT = """[Unit]
Description=Terminal de autoatendimento App247
After=graphical-session.target
Wants=graphical-session.target

[Service]
Type=simple
ExecStartPre=/usr/local/bin/app247-terminal-launcher --apply-display
ExecStart=/usr/local/bin/app247-terminal-launcher
Restart=on-failure
RestartSec=3

[Install]
WantedBy=default.target
"""


@unittest.skipIf(os.getuid() == 0, "o launcher gráfico recusa root")
class LauncherApplyDisplayTest(unittest.TestCase):
    def setUp(self):
        self._directory = tempfile.TemporaryDirectory()
        self.root = Path(self._directory.name)
        self.runtime = self.root / "runtime"
        self.runtime.mkdir()
        self.server = socket.socket(socket.AF_UNIX)
        self.server.bind(str(self.runtime / "wayland-0"))
        self.current = self.root / "current"
        self.current.mkdir()
        self.marker = self.root / "calls"
        config = self.root / "terminal.env"
        config.write_text(
            f"APP247_DATA_DIR={self.root}\nAPP247_TEST_MARKER={self.marker}\n",
            encoding="utf-8",
        )
        config.chmod(0o640)
        self.environment = os.environ.copy()
        self.environment.update({
            "APP247_CONFIG_FILE": str(config),
            "APP247_CURRENT_LINK": str(self.current),
            "XDG_RUNTIME_DIR": str(self.runtime),
            "APP247_GRAPHICAL_SESSION_WAIT_SECONDS": "0",
            "APP247_APPLY_DISPLAY_SESSION_WAIT_SECONDS": "0",
        })
        self.environment.pop("WAYLAND_DISPLAY", None)

    def tearDown(self):
        self.server.close()
        self._directory.cleanup()

    def _executable(self, body):
        executable = self.current / "app247-terminal"
        executable.write_text("#!/bin/sh\n" + body, encoding="utf-8")
        executable.chmod(0o755)

    def _launch(self, *arguments, timeout=15):
        return subprocess.run(
            [str(LAUNCHER), *arguments],
            check=False,
            env=self.environment,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

    def test_apply_display_reaches_executable_with_only_that_argument(self):
        self._executable(
            'printf "%s|%s|%s\\n" "$#" "$1" "$WAYLAND_DISPLAY" >> "$APP247_TEST_MARKER"\n'
        )
        result = self._launch("--apply-display")

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(
            "1|--apply-display|wayland-0",
            self.marker.read_text(encoding="utf-8").strip(),
        )

    def test_apply_display_rejects_extra_arguments_without_running_gui(self):
        self._executable('printf run >> "$APP247_TEST_MARKER"\n')
        result = self._launch("--apply-display", "--outro")

        self.assertEqual(2, result.returncode)
        self.assertFalse(self.marker.exists())

    @unittest.skipIf(shutil.which("timeout") is None, "coreutils timeout ausente")
    def test_apply_display_is_bounded_even_if_executable_hangs(self):
        # Um executável que não termina (ex.: launcher antigo abrindo a GUI)
        # não pode prender o ExecStartPre até o timeout de 90 s do systemd.
        self._executable("sleep 30\n")
        self.environment["APP247_APPLY_DISPLAY_TIMEOUT_SECONDS"] = "1"
        started = time.monotonic()
        result = self._launch("--apply-display")

        self.assertEqual(124, result.returncode)
        self.assertLess(time.monotonic() - started, 6)

    @unittest.skipIf(shutil.which("flock") is None, "flock ausente")
    def test_apply_display_runs_while_graphical_instance_holds_lock(self):
        self._executable(
            'case "$1" in\n'
            '  --apply-display) printf display >> "$APP247_TEST_MARKER" ;;\n'
            '  *) printf gui >> "$APP247_TEST_MARKER"; sleep 2 ;;\n'
            'esac\n'
        )
        gui = subprocess.Popen(
            [str(LAUNCHER)],
            env=self.environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            for _ in range(40):
                if self.marker.exists():
                    break
                time.sleep(0.05)
            display = self._launch("--apply-display")
            second_gui = self._launch()
        finally:
            gui.communicate(timeout=10)

        self.assertEqual(0, display.returncode, display.stderr)
        self.assertIn("já está em execução", second_gui.stdout)
        self.assertEqual("guidisplay", self.marker.read_text(encoding="utf-8"))


class InstalledUnitTest(unittest.TestCase):
    def _environment(self, root, desktop_home):
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
        (root / "data").mkdir()
        user = pwd.getpwuid(os.getuid()).pw_name
        environment = os.environ.copy()
        environment.update({
            "APP247_ARTIFACT_DIR": str(artifact),
            "APP247_INSTALL_VERSION": "9.9.9-test",
            "APP247_INSTALL_ROOT": str(root / "opt"),
            "APP247_DATA_DIR": str(root / "data"),
            "APP247_CONFIG_DIR": str(root / "etc"),
            "APP247_CONFIG_TEMPLATE": str(template),
            "APP247_SYSTEMD_DIR": str(root / "systemd"),
            "APP247_USER_SYSTEMD_DIR": str(desktop_home / ".config/systemd/user"),
            "APP247_LAUNCHER_DESTINATION": str(root / "bin/launcher"),
            "APP247_MANAGE_SYSTEMD": "false",
            "APP247_SERVICE_USER": user,
            "APP247_SERVICE_GROUP": grp.getgrgid(os.getgid()).gr_name,
            "APP247_DESKTOP_USER": user,
            "APP247_DESKTOP_HOME": str(desktop_home),
            "APP247_DESKTOP_DIR": str(desktop_home / "Desktop"),
            "APP247_AUTOSTART_DIR": str(desktop_home / ".config/autostart"),
            "APP247_NM_CONF_DIR": str(root / "NetworkManager/conf.d"),
            "APP247_ICON_DESTINATION": str(root / "pixmaps/app247-terminal.png"),
        })
        (root / "NetworkManager").mkdir()
        desktop_home.mkdir(exist_ok=True)
        return environment

    def _install(self, environment):
        subprocess.run(
            [str(PROJECT_ROOT / "scripts/install.sh")],
            check=True, env=environment, capture_output=True, text=True,
        )
        return subprocess.run(
            [str(PROJECT_ROOT / "scripts/install.sh"), "--activate"],
            check=False, env=environment, capture_output=True, text=True,
        )

    def test_legacy_field_unit_is_preserved_and_replaced(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            desktop_home = root / "home"
            unit_dir = desktop_home / ".config/systemd/user"
            unit_dir.mkdir(parents=True)
            unit_path = unit_dir / "app247-terminal.service"
            unit_path.write_text(LEGACY_FIELD_UNIT, encoding="utf-8")
            dropin = unit_dir / "app247-terminal.service.d/override.conf"
            dropin.parent.mkdir()
            dropin_contents = (
                "[Service]\nExecStartPre=\n"
                "ExecStartPre=-/opt/app247/current/app247-terminal --apply-display\n"
            )
            dropin.write_text(dropin_contents, encoding="utf-8")

            wants = unit_dir / "default.target.wants"
            wants.mkdir()
            # Link absoluto criado por `systemctl --user enable` no campo.
            (wants / "app247-terminal.service").symlink_to(unit_path)

            activation = self._install(self._environment(root, desktop_home))

            self.assertEqual(0, activation.returncode, activation.stderr)
            self.assertEqual(
                unit_path, (wants / "app247-terminal.service").resolve()
            )
            unit = unit_path.read_text(encoding="utf-8")
            launcher = root / "bin/launcher"
            self.assertIn("# Managed by App247", unit)
            self.assertIn(f"ExecStartPre=-{launcher} --apply-display", unit)
            self.assertIn(f"ExecStart={launcher}\n", unit)
            backups = list(unit_dir.glob("app247-terminal.service.legacy-*"))
            self.assertEqual(1, len(backups))
            self.assertEqual(LEGACY_FIELD_UNIT, backups[0].read_text(encoding="utf-8"))
            self.assertIn("override.conf redefine ExecStart", activation.stderr)
            self.assertEqual(dropin_contents, dropin.read_text(encoding="utf-8"))

            # O launcher instalado junto com a unit trata --apply-display.
            installed = launcher.read_text(encoding="utf-8")
            self.assertIn('has_argument "--apply-display" "$@"', installed)
            self.assertIn('"$EXECUTABLE" --apply-display', installed)

    def test_installer_persists_wifi_powersave_disabled_policy(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            environment = self._environment(root, root / "home")

            activation = self._install(environment)

            self.assertEqual(0, activation.returncode, activation.stderr)
            policy = root / "NetworkManager/conf.d/app247-wifi-powersave.conf"
            contents = policy.read_text(encoding="utf-8")
            self.assertIn("# Managed by App247", contents)
            self.assertIn("[connection]\nwifi.powersave = 2\n", contents)
            self.assertEqual(0o644, policy.stat().st_mode & 0o777)
            self.assertIn("a rede não foi reiniciada", activation.stdout)

    def test_wifi_policy_respects_keep_and_operator_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            environment = self._environment(root, root / "home")
            policy_dir = root / "NetworkManager/conf.d"
            policy_dir.mkdir()
            policy = policy_dir / "app247-wifi-powersave.conf"
            operator = "[connection]\nwifi.powersave = 3\n"
            policy.write_text(operator, encoding="utf-8")

            activation = self._install(environment)
            self.assertEqual(0, activation.returncode, activation.stderr)
            self.assertIn("não é gerenciado pelo App247", activation.stderr)
            self.assertEqual(operator, policy.read_text(encoding="utf-8"))

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            environment = self._environment(root, root / "home")
            environment["APP247_WIFI_POWERSAVE"] = "keep"

            activation = self._install(environment)
            self.assertEqual(0, activation.returncode, activation.stderr)
            self.assertFalse(
                (root / "NetworkManager/conf.d/app247-wifi-powersave.conf").exists()
            )

    def test_desktop_shortcut_uses_installed_logo(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            desktop_home = root / "home"
            environment = self._environment(root, desktop_home)
            bundled = root / "artifact/_internal/assets/images/logo.png"
            bundled.parent.mkdir(parents=True)
            shutil.copy2(PROJECT_ROOT / "assets/images/logo.png", bundled)

            activation = self._install(environment)

            self.assertEqual(0, activation.returncode, activation.stderr)
            icon = root / "pixmaps/app247-terminal.png"
            self.assertEqual(bundled.read_bytes(), icon.read_bytes())
            self.assertEqual(0o644, icon.stat().st_mode & 0o777)
            for entry in (
                desktop_home / "Desktop/Terminal 24-7.desktop",
                desktop_home / ".config/autostart/app247-terminal.desktop",
            ):
                self.assertIn(f"Icon={icon}\n", entry.read_text(encoding="utf-8"))

    def test_legacy_field_shortcut_is_preserved_outside_desktop(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            desktop_home = root / "home"
            environment = self._environment(root, desktop_home)
            desktop = desktop_home / "Desktop"
            desktop.mkdir()
            legacy = desktop / "App247 Terminal.desktop"
            legacy_contents = (
                "[Desktop Entry]\nType=Application\nName=App247 Terminal\n"
                "Exec=/usr/local/bin/app247-terminal-launcher\n"
                "Path=/opt/app247/current\nTerminal=false\n"
            )
            legacy.write_text(legacy_contents, encoding="utf-8")
            unrelated = desktop / "Outro.desktop"
            unrelated.write_text("[Desktop Entry]\nName=Outro\n", encoding="utf-8")

            activation = self._install(environment)

            self.assertEqual(0, activation.returncode, activation.stderr)
            self.assertFalse(legacy.exists())
            backups = list(
                (desktop_home / ".local/share/app247/legacy-desktop").iterdir()
            )
            self.assertEqual(1, len(backups))
            self.assertEqual(legacy_contents, backups[0].read_text(encoding="utf-8"))
            self.assertTrue(unrelated.exists())
            self.assertTrue((desktop / "Terminal 24-7.desktop").is_file())

    def test_desktop_shortcut_falls_back_without_logo(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            desktop_home = root / "home"

            activation = self._install(self._environment(root, desktop_home))

            self.assertEqual(0, activation.returncode, activation.stderr)
            entry = desktop_home / "Desktop/Terminal 24-7.desktop"
            self.assertIn("Icon=computer\n", entry.read_text(encoding="utf-8"))
            self.assertIn("logo ausente", activation.stderr)

    def test_foreign_enable_link_is_still_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            desktop_home = root / "home"
            wants = desktop_home / ".config/systemd/user/default.target.wants"
            wants.mkdir(parents=True)
            (wants / "app247-terminal.service").symlink_to("/usr/lib/systemd/user/outra.service")

            activation = self._install(self._environment(root, desktop_home))

            self.assertNotEqual(0, activation.returncode)
            self.assertIn("enable existente da unit não pertence", activation.stderr)

    def test_unrelated_unit_with_same_name_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            desktop_home = root / "home"
            unit_dir = desktop_home / ".config/systemd/user"
            unit_dir.mkdir(parents=True)
            unit_path = unit_dir / "app247-terminal.service"
            foreign = "[Service]\nExecStart=/usr/bin/true\n"
            unit_path.write_text(foreign, encoding="utf-8")

            activation = self._install(self._environment(root, desktop_home))

            self.assertNotEqual(0, activation.returncode)
            self.assertIn("não é gerenciada pelo App247", activation.stderr)
            self.assertEqual(foreign, unit_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
