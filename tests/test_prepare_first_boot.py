import struct
import unittest

from tools.prepare_first_boot import (
    PreparationError,
    active_extlinux_value,
    fdt_string,
    parse_fdt,
    pin_extlinux_fdt,
)


def make_overlay(target="/dsi@ff450000/panel@0"):
    strings = b"target-path\0compatible\0panel_description\0"

    def token(value):
        return struct.pack(">I", value)

    def pad(value):
        return value + (b"\0" * ((-len(value)) % 4))

    def begin(name):
        return token(1) + pad(name.encode("utf-8") + b"\0")

    def prop(nameoff, value):
        return token(3) + struct.pack(">II", len(value), nameoff) + pad(value)

    target_off = strings.index(b"target-path\0")
    compat_off = strings.index(b"compatible\0")
    desc_off = strings.index(b"panel_description\0")
    structure = b"".join(
        [
            begin(""),
            begin("fragment@0"),
            prop(target_off, target.encode("utf-8") + b"\0"),
            begin("__overlay__"),
            prop(compat_off, b"rocknix,generic-dsi\0"),
            prop(desc_off, b"G size=52,70\0"),
            token(2),
            token(2),
            token(2),
            token(9),
        ]
    )
    off_rsv = 40
    off_struct = off_rsv + 16
    off_strings = off_struct + len(structure)
    total = off_strings + len(strings)
    header = b"\xd0\x0d\xfe\xed" + struct.pack(
        ">9I",
        total,
        off_struct,
        off_strings,
        off_rsv,
        17,
        16,
        0,
        len(strings),
        len(structure),
    )
    return header + (b"\0" * 16) + structure + strings


class FirstBootFdtTests(unittest.TestCase):
    def test_parses_overlay_target_and_compatible(self):
        tree = parse_fdt(make_overlay())
        self.assertEqual(
            fdt_string(tree["/fragment@0"], "target-path"),
            "/dsi@ff450000/panel@0",
        )
        self.assertEqual(
            fdt_string(tree["/fragment@0/__overlay__"], "compatible"),
            "rocknix,generic-dsi",
        )

    def test_rejects_bad_fdt_magic(self):
        with self.assertRaises(PreparationError):
            parse_fdt(b"NOPE" + b"\0" * 100)

    def test_rejects_target_property_missing(self):
        tree = parse_fdt(make_overlay())
        with self.assertRaises(PreparationError):
            fdt_string(tree["/fragment@0"], "missing")

    def test_reads_only_active_extlinux_directives(self):
        conf = (
            "# FDTOVERLAYS /wrong.dtbo\n"
            "  FDTOVERLAYS /overlays/mipi-panel.dtbo\n"
            "  FDT /rk3326-gameconsole-r36s.dtb\n"
        )
        self.assertEqual(
            active_extlinux_value(conf, "FDTOVERLAYS"),
            ["/overlays/mipi-panel.dtbo"],
        )
        self.assertEqual(
            active_extlinux_value(conf, "FDT"),
            ["/rk3326-gameconsole-r36s.dtb"],
        )


    def test_pins_base_dtb_before_overlay_when_fdt_is_automatic(self):
        conf = (
            "LABEL ROCKNIX\n"
            "  LINUX /KERNEL\n"
            "  FDTDIR /\n"
            "  FDTOVERLAYS /overlays/mipi-panel.dtbo\n"
            "  APPEND quiet\n"
        )
        updated, changed = pin_extlinux_fdt(conf, "rk3326-gameconsole-r36s.dtb")
        self.assertTrue(changed)
        self.assertIn("  FDT /rk3326-gameconsole-r36s.dtb\n", updated)
        self.assertEqual(
            active_extlinux_value(updated, "FDT"),
            ["/rk3326-gameconsole-r36s.dtb"],
        )
        self.assertEqual(
            active_extlinux_value(updated, "FDTOVERLAYS"),
            ["/overlays/mipi-panel.dtbo"],
        )

    def test_preserves_windows_line_endings_when_pinning_fdt(self):
        conf = (
            "LABEL ROCKNIX\r\n"
            "  FDTDIR /\r\n"
            "  FDTOVERLAYS /overlays/mipi-panel.dtbo\r\n"
        )
        updated, changed = pin_extlinux_fdt(conf, "rk3326-gameconsole-r36s.dtb")
        self.assertTrue(changed)
        self.assertIn("  FDT /rk3326-gameconsole-r36s.dtb\r\n", updated)

    def test_keeps_an_already_matching_fdt_directive(self):
        conf = (
            "LABEL ROCKNIX\n"
            "  FDT /rk3326-gameconsole-r36s.dtb\n"
            "  FDTOVERLAYS /overlays/mipi-panel.dtbo\n"
        )
        updated, changed = pin_extlinux_fdt(conf, "rk3326-gameconsole-r36s.dtb")
        self.assertFalse(changed)
        self.assertEqual(updated, conf)

    def test_rejects_mismatched_existing_fdt(self):
        conf = (
            "LABEL ROCKNIX\n"
            "  FDT /rk3326-odroid-go2.dtb\n"
            "  FDTOVERLAYS /overlays/mipi-panel.dtbo\n"
        )
        with self.assertRaises(PreparationError):
            pin_extlinux_fdt(conf, "rk3326-gameconsole-r36s.dtb")

    def test_rejects_base_dtb_path_that_extlinux_cannot_parse(self):
        conf = "  FDTOVERLAYS /overlays/mipi-panel.dtbo\n"
        with self.assertRaises(PreparationError):
            pin_extlinux_fdt(conf, "dtb folder/gameconsole-r36s.dtb")


if __name__ == "__main__":
    unittest.main()
