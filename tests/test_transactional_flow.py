import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace

from identifypanel import boot_info, confirm, rollback, restore, stage, validate_fdt_bytes
from test_fdt_validation import make_fdt


def blob(marker):
    data = bytearray(make_fdt())
    data[-1] = marker
    ok, detail = validate_fdt_bytes(bytes(data))
    if not ok:
        raise AssertionError(detail)
    return bytes(data)


class TransactionalPanelTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "boot"
        self.overlay_dir = self.root / "overlays"
        self.overlay_dir.mkdir(parents=True)
        self.package = Path(self.temp.name) / "profiles"
        self.package.mkdir()
        self.profile_a = self.package / "candidate-a.dtbo"
        self.profile_b = self.package / "candidate-b.dtbo"
        self.profile_a.write_bytes(blob(0xA1))
        self.profile_b.write_bytes(blob(0xB2))
        self.active = self.overlay_dir / "mipi-panel.dtbo"
        self.active.write_bytes(blob(0x11))

    def tearDown(self):
        self.temp.cleanup()

    def args(self, **kwargs):
        values = {"boot": str(self.root), "dtbo": str(self.profile_a), "name": "candidate-a"}
        values.update(kwargs)
        return SimpleNamespace(**values)

    def read_state(self):
        return json.loads((self.root / ".identifypanel" / "manifest.json").read_text())

    def test_stage_is_pending_until_manual_confirmation(self):
        original = self.active.read_bytes()
        stage(self.args())
        state = self.read_state()
        self.assertEqual(state["pending"]["profile"], "candidate-a")
        self.assertEqual(state["pending"]["status"], "pending")
        self.assertNotIn("active_profile", state)
        self.assertEqual(self.active.read_bytes(), self.profile_a.read_bytes())
        self.assertEqual((self.root / state["original_backup"]).read_bytes(), original)
        confirm(SimpleNamespace(boot=str(self.root)))
        state = self.read_state()
        self.assertNotIn("pending", state)
        self.assertEqual(state["active_profile"], "candidate-a")
        self.assertEqual(state["last_confirmed"]["confirmation"], "manual-user-visual")
        self.assertEqual((self.root / state["original_backup"]).read_bytes(), original)

    def test_cannot_stage_second_profile_while_first_is_pending(self):
        stage(self.args())
        with self.assertRaises(SystemExit):
            stage(self.args(dtbo=str(self.profile_b), name="candidate-b"))
        self.assertEqual(self.active.read_bytes(), self.profile_a.read_bytes())

    def test_rollback_restores_previous_confirmed_profile_and_original_backup(self):
        original = self.active.read_bytes()
        stage(self.args())
        confirm(SimpleNamespace(boot=str(self.root)))
        confirmed_a = self.active.read_bytes()
        stage(self.args(dtbo=str(self.profile_b), name="candidate-b"))
        rollback(SimpleNamespace(boot=str(self.root)))
        self.assertEqual(self.active.read_bytes(), confirmed_a)
        state = self.read_state()
        self.assertEqual(state["active_profile"], "candidate-a")
        self.assertNotIn("pending", state)
        self.assertEqual((self.root / state["original_backup"]).read_bytes(), original)

    def test_rollback_removes_overlay_when_none_existed_before_first_trial(self):
        self.active.unlink()
        stage(self.args())
        self.assertTrue(self.active.is_file())
        rollback(SimpleNamespace(boot=str(self.root)))
        self.assertFalse(self.active.exists())
        state = self.read_state()
        self.assertTrue(state["original_missing"])
        self.assertNotIn("pending", state)

    def test_confirm_refuses_changed_active_overlay(self):
        stage(self.args())
        self.active.write_bytes(blob(0xC3))
        with self.assertRaises(SystemExit):
            confirm(SimpleNamespace(boot=str(self.root)))
        self.assertIn("pending", self.read_state())

    def test_restore_returns_to_baseline_after_confirmed_test(self):
        original = self.active.read_bytes()
        stage(self.args())
        confirm(SimpleNamespace(boot=str(self.root)))
        restore(SimpleNamespace(boot=str(self.root)))
        self.assertEqual(self.active.read_bytes(), original)
        state = self.read_state()
        self.assertEqual(state["active_profile"], "original-backup")
        self.assertNotIn("pending", state)

    def test_stage_rejects_catalog_hash_mismatch(self):
        catalog = self.package / "manifest.json"
        catalog.write_text(json.dumps({
            "profiles": [{
                "file": self.profile_a.name,
                "size": self.profile_a.stat().st_size,
                "sha256": "0" * 64,
            }]
        }))
        with self.assertRaises(SystemExit):
            stage(self.args())
        self.assertEqual(self.active.read_bytes(), blob(0x11))
        self.assertFalse((self.root / ".identifypanel" / "manifest.json").exists())

    def test_profiles_rejects_catalog_hash_mismatch(self):
        from identifypanel import profiles
        catalog = self.package / "manifest.json"
        catalog.write_text(json.dumps({
            "profiles": [{
                "file": self.profile_a.name,
                "size": self.profile_a.stat().st_size,
                "sha256": "0" * 64,
            }]
        }))
        with self.assertRaises(SystemExit):
            profiles(SimpleNamespace(profiles=str(self.package)))

    def test_corrupt_manifest_is_not_overwritten(self):
        state_dir = self.root / ".identifypanel"
        state_dir.mkdir()
        path = state_dir / "manifest.json"
        path.write_text("{ not json")
        with self.assertRaises(SystemExit):
            stage(self.args())
        self.assertEqual(path.read_text(), "{ not json")


    def test_restore_recovers_original_even_if_active_overlay_was_removed(self):
        original = self.active.read_bytes()
        stage(self.args())
        confirm(SimpleNamespace(boot=str(self.root)))
        self.active.unlink()
        restore(SimpleNamespace(boot=str(self.root)))
        self.assertEqual(self.active.read_bytes(), original)

    def test_restore_removes_profile_if_original_overlay_did_not_exist(self):
        self.active.unlink()
        stage(self.args())
        confirm(SimpleNamespace(boot=str(self.root)))
        restore(SimpleNamespace(boot=str(self.root)))
        self.assertFalse(self.active.exists())
        state = self.read_state()
        self.assertTrue(state["original_missing"])
        self.assertEqual(state["active_profile"], "no-original-overlay")

    def test_rollback_rejects_symlinked_backup(self):
        stage(self.args())
        state = self.read_state()
        relative = state["pending"]["previous_overlay_backup"]
        backup = self.root / relative
        link = backup.with_name("unsafe-link.dtbo")
        link.symlink_to(backup.name)
        state["pending"]["previous_overlay_backup"] = str(link.relative_to(self.root))
        (self.root / ".identifypanel" / "manifest.json").write_text(json.dumps(state))
        with self.assertRaises(SystemExit):
            rollback(SimpleNamespace(boot=str(self.root)))
        self.assertIn("pending", self.read_state())

    def test_boot_info_reports_boot_script_without_modifying_it(self):
        script = self.root / "boot.ini"
        original = "load mmc 1:1 ${dtbo_loadaddr} overlays/mipi-panel.dtbo\nfdt apply ${dtbo_loadaddr}\n"
        script.write_text(original, encoding="utf-8")
        output = io.StringIO()
        with redirect_stdout(output):
            boot_info(SimpleNamespace(boot=str(self.root)))
        report = output.getvalue()
        self.assertIn("boot.ini", report)
        self.assertIn("mipi-panel.dtbo", report)
        self.assertIn("Comando/aplicação FDT detectado: sim", report)
        self.assertEqual(script.read_text(encoding="utf-8"), original)


if __name__ == "__main__":
    unittest.main()
