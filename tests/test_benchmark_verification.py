"""Verify a measured Space Age baseline without weakening the base default."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import verify


class BenchmarkVerificationTests(unittest.TestCase):
    def setUp(self):
        self.check = getattr(verify, 'verify_benchmark', None)
        self.assertIsNotNone(self.check, 'Benchmark verification must accept an explicit measured baseline')

    def test_space_age_matches_explicit_native_baseline(self):
        result = self.check('Performed 120 updates\n  checksum: 2376201887\nGoodbye\n', 2376201887)
        self.assertEqual(result['checksum'], '2376201887')

    def test_default_still_rejects_a_different_simulation(self):
        with self.assertRaisesRegex(RuntimeError, 'checksum'):
            self.check('Performed 120 updates\n  checksum: 2376201887\nGoodbye\n')

    def test_matching_checksum_does_not_hide_an_incomplete_run(self):
        with self.assertRaisesRegex(RuntimeError, 'Incomplete'):
            self.check('checksum: 2376201887\n', 2376201887)

    def test_original_base_game_baseline_remains_valid(self):
        result = self.check('Performed 120 updates\n  checksum: 2892897386\nGoodbye\n')
        self.assertEqual(result['ticks'], 120)


if __name__ == '__main__':
    unittest.main()
