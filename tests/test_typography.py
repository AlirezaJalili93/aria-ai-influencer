"""A missing native FriBiDi dependency must fail before service installation."""
from pathlib import Path
import runpy
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
probe = runpy.run_path(str(ROOT / 'scripts/check_typography.py'))


class TypographyTests(unittest.TestCase):
    def test_missing_raqm_has_actionable_runtime_dependency_error(self):
        with patch.object(probe['features'], 'check', return_value=False):
            with self.assertRaisesRegex(RuntimeError, 'dnf install -y fribidi'):
                probe['check_typography']()

    def test_native_render_works_for_both_bundled_fonts(self):
        image = probe['check_typography']()
        self.assertEqual(image.size, (1080, 240))
        for box in [(50, 20, 1001, 110), (50, 110, 1001, 220)]:
            self.assertGreater(len(image.crop(box).getcolors(100000)), 1)
