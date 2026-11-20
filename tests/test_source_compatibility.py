"""Local integration checks; copyrighted game files are never test fixtures.

Run with FACTORIO_TEST_APP pointing to your own audited game installation.
"""
import os
from pathlib import Path
import sys
import struct
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from config import validate_source
import config
from macho import MachO

LOCAL_SHA256 = '42218e9676f36687282800e5b6336b049c0f0e45f0f71eb20f90c49ccdec4359'


class SourceValidationTests(unittest.TestCase):
    def test_unknown_executable_is_rejected_before_patching(self):
        with tempfile.TemporaryDirectory() as directory:
            app = Path(directory) / 'factorio.app'
            binary = app / 'Contents/MacOS/factorio'
            binary.parent.mkdir(parents=True)
            binary.write_bytes(b'unknown executable')
            with self.assertRaisesRegex(ValueError, 'Unsupported Factorio executable'):
                validate_source(app)

    @unittest.skipUnless(os.environ.get('FACTORIO_TEST_APP'), 'requires an owned local game')
    def test_audited_local_executable_is_accepted(self):
        try:
            digest = validate_source(Path(os.environ['FACTORIO_TEST_APP']))
        except ValueError as error:
            self.fail(f'Audited experimental executable was rejected: {error}')
        self.assertEqual(digest, LOCAL_SHA256)


@unittest.skipUnless(os.environ.get('FACTORIO_TEST_APP'), 'requires an owned local game')
class PatchLayoutTests(unittest.TestCase):
    def setUp(self):
        self.macho = MachO(Path(os.environ['FACTORIO_TEST_APP']) / 'Contents/MacOS/factorio')
        self.validate = getattr(config, 'validate_patch_layout', None)
        self.assertIsNotNone(self.validate, 'Patch layout must be validated before accepting a new binary')

    def test_original_layout_has_valid_patch_sites(self):
        self.validate(self.macho, 3)

    def test_changed_sdl3_version_instruction_is_rejected(self):
        symbol = next(s for s in self.macho.symbols() if s['name'] == '_SDL_GetVersion_REAL')
        offset = symbol['address'] - 0x100000000
        self.macho.data[offset:offset + 4] = bytes(4)
        with self.assertRaisesRegex(ValueError, 'SDL version'):
            self.validate(self.macho, 3)

    def test_entrypoint_that_does_not_match_main_is_rejected(self):
        position = next(p for c, p, n in self.macho.commands if c == 0x80000028)
        struct.pack_into('<Q', self.macho.data, position + 8, 0)
        with self.assertRaisesRegex(ValueError, 'entrypoint'):
            self.validate(self.macho, 3)

    def test_occupied_trampoline_padding_is_rejected(self):
        first = min(s['offset'] for s in self.macho.sections if s['offset'] > 0)
        self.macho.data[first - 16] = 1
        with self.assertRaisesRegex(ValueError, 'padding'):
            self.validate(self.macho, 3)


if __name__ == '__main__':
    unittest.main()
