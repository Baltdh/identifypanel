import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (ROOT / "preboot" / "PanelSelector-Wrapper.ini").read_text(encoding="utf-8")
INSTALLER = (ROOT / "preboot" / "Install-PanelSelector.ps1").read_text(encoding="utf-8")


class PreBootSelectorTests(unittest.TestCase):
    def test_selector_is_gated_by_r1_and_has_cancel_chord(self):
        self.assertIn("if gpio input c7; then", SCRIPT)
        self.assertIn("if gpio input c1; then", SCRIPT)
        self.assertIn('setenv ip_choice "cancel"', SCRIPT)

    def test_all_physical_choices_have_known_fat_paths(self):
        expected = [
            "IPANEL/PANEL1.DTBO",
            "IPANEL/PANEL2.DTBO",
            "IPANEL/PANEL3.DTBO",
            "IPANEL/PANEL4.DTBO",
            "IPANEL/R36H.DTBO",
            "IPANEL/BASE.DTBO",
            "IPANEL/CLONE.DTBO",
            "IPANEL/351MP.DTBO",
        ]
        for path in expected:
            with self.subTest(path=path):
                self.assertIn(path, SCRIPT)

    def test_active_overlay_is_backed_up_and_verified(self):
        self.assertIn("IPANEL/BASE.DTBO", SCRIPT)
        self.assertIn("fatwrite mmc 1:1", SCRIPT)
        self.assertIn("md5sum", SCRIPT)
        self.assertIn("overlays/mipi-panel.dtbo", SCRIPT)
        self.assertIn("source ", SCRIPT)
        self.assertIn("boot0.scr", SCRIPT)

    def test_installer_refuses_ambiguous_boot_layout(self):
        self.assertIn('Test-Path -LiteralPath $BootIni', INSTALLER)
        self.assertIn("FDTOVERLAYS", INSTALLER)
        self.assertIn("U-Boot legado A", INSTALLER)
        self.assertIn("FDT explicita", INSTALLER)

    def test_no_raw_bootloader_sector_write_commands(self):
        forbidden = ("mmc erase", "mmc write", "sf write", "nand write")
        for command in forbidden:
            self.assertNotIn(command, SCRIPT.lower())


if __name__ == "__main__":
    unittest.main()
