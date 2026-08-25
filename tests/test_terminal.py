import json
import tempfile
import unittest
from pathlib import Path

from model.Terminal import Terminal


class TerminalTest(unittest.TestCase):
    def test_uses_backend_terminal_id_as_canonical_uuid(self):
        terminal = Terminal.from_dict({
            "terminalId": "terminal-uuid",
            "serialNumber": "serial",
            "nome": "Terminal",
            "codigo": "T01",
            "status": "ONLINE",
            "ativo": True,
            "activated": True,
            "condominioId": "condominio-uuid",
            "condominioNome": "Condomínio"
        })

        self.assertEqual("terminal-uuid", terminal.terminalId)
        self.assertEqual("terminal-uuid", terminal.uuidTerminal)

    def test_preserves_legacy_uuid_as_canonical_identity(self):
        terminal = Terminal.from_dict({
            "terminalId": 1,
            "uuidTerminal": "legacy-uuid",
            "ativo": True,
            "activated": True
        })

        self.assertEqual("legacy-uuid", terminal.terminalId)
        self.assertEqual("legacy-uuid", terminal.uuidTerminal)

    def test_activation_requires_valid_active_terminal_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "terminal.json"
            path.write_text("not-json", encoding="utf-8")
            self.assertFalse(Terminal.is_activated(path))

            path.write_text(json.dumps({
                "terminalId": "uuid",
                "ativo": False,
                "activated": True
            }), encoding="utf-8")
            self.assertFalse(Terminal.is_activated(path))

    def test_save_is_loadable(self):
        terminal = Terminal.from_dict({
            "terminalId": "uuid",
            "ativo": True,
            "activated": True
        })
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "terminal.json"
            terminal.save(path)

            self.assertTrue(Terminal.is_activated(path))
            self.assertEqual("uuid", Terminal.load(path).terminalId)
            self.assertFalse(path.with_suffix(".json.tmp").exists())


if __name__ == "__main__":
    unittest.main()
