import struct
import unittest

from identifypanel import HEADER_SIZE, MAGIC, validate_fdt_bytes


def make_fdt(total=80, off_struct=40, off_strings=64, off_rsvmap=48,
             version=17, last_comp=16, size_strings=8, size_struct=8):
    return MAGIC + struct.pack(">9I", total, off_struct, off_strings, off_rsvmap,
                               version, last_comp, 0, size_strings, size_struct) + b"\0" * (total - HEADER_SIZE)


class FdtValidationTests(unittest.TestCase):
    def test_accepts_consistent_header(self):
        ok, _ = validate_fdt_bytes(make_fdt())
        self.assertTrue(ok)

    def test_rejects_bad_magic(self):
        ok, _ = validate_fdt_bytes(b"NOPE" + b"\0" * 60)
        self.assertFalse(ok)

    def test_rejects_truncated_header(self):
        ok, _ = validate_fdt_bytes(MAGIC + b"\0" * 20)
        self.assertFalse(ok)

    def test_rejects_declared_size_beyond_file(self):
        data = bytearray(make_fdt())
        struct.pack_into(">I", data, 4, 128)
        ok, _ = validate_fdt_bytes(bytes(data))
        self.assertFalse(ok)

    def test_rejects_section_outside_blob(self):
        ok, _ = validate_fdt_bytes(make_fdt(off_struct=60, size_struct=16))
        self.assertFalse(ok)

    def test_rejects_invalid_version(self):
        ok, _ = validate_fdt_bytes(make_fdt(version=15))
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
