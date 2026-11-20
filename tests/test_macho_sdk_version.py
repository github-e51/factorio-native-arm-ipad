"""The game Mach-O must advertise the SDK that built its iOS wrapper."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from macho import packed_version


class SDKVersionTests(unittest.TestCase):
    def test_ios_27_1_is_encoded_in_build_version(self):
        self.assertEqual(packed_version('27.1'), (27 << 16) | (1 << 8))
        self.assertEqual(packed_version('26.2.3'), (26 << 16) | (2 << 8) | 3)

    def test_invalid_versions_are_rejected(self):
        for version in ('27.1.2.3', '-1.0', '27.256', ''):
            with self.subTest(version=version), self.assertRaises(ValueError):
                packed_version(version)


if __name__ == '__main__':
    unittest.main()
