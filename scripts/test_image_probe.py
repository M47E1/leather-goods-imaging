"""Synthetic fixtures only: never edits any user image."""
from pathlib import Path
import tempfile
import unittest
import json
import subprocess
import sys
from PIL import Image
from image_probe import probe


class ProbeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.im = Image.new('RGB', (10, 10), (255, 255, 255))
        self.im.putpixel((5, 5), (10, 20, 30))
        self.source = self.save('source.png', self.im)

    def tearDown(self):
        self.tmp.cleanup()

    def save(self, name, im):
        p = self.root / name
        im.save(p)
        return p

    def test_metadata_not_quality_pass(self):
        r = probe(self.source)
        self.assertIsNone(r['all_requested_checks_passed'])
        self.assertEqual(r['visual_quality'], 'not_assessed')

    def test_only_selected_background(self):
        self.assertTrue(probe(self.source, backgrounds=[(0, 0, 4, 4)])['all_requested_checks_passed'])
        self.assertFalse(probe(self.source, backgrounds=[(0, 0, 10, 10)])['all_requested_checks_passed'])

    def test_offwhite_fails(self):
        im = self.im.copy(); im.putpixel((0, 0), (254, 255, 255))
        self.assertFalse(probe(self.save('off.png', im), backgrounds=[(0, 0, 1, 1)])['all_requested_checks_passed'])

    def test_out_of_bounds_rejected(self):
        with self.assertRaises(ValueError):
            probe(self.source, backgrounds=[(-1, 0, 2, 2)])

    def test_alpha_not_pure_opaque_white(self):
        im = Image.new('RGBA', (2, 2), (255, 255, 255, 0))
        self.assertFalse(probe(self.save('alpha.png', im), backgrounds=[(0, 0, 2, 2)])['all_requested_checks_passed'])

    def test_padding_preserves_source_without_claiming_background(self):
        im = Image.new('RGB', (14, 14), 'white'); im.paste(self.im, (2, 2))
        self.assertTrue(probe(self.save('pad.png', im), padding_source=self.source, offset=(2, 2))['all_requested_checks_passed'])
        im.putpixel((7, 7), (1, 2, 3))
        self.assertFalse(probe(self.save('wrong.png', im), padding_source=self.source, offset=(2, 2))['all_requested_checks_passed'])

    def test_protection_scope(self):
        im = self.im.copy(); im.putpixel((5, 5), (1, 2, 3)); p = self.save('change.png', im)
        self.assertTrue(probe(p, compare=self.source, protected=[(0, 0, 4, 4)])['all_requested_checks_passed'])
        self.assertFalse(probe(p, compare=self.source, protected=[(0, 0, 10, 10)])['all_requested_checks_passed'])

    def test_nonbinary_mask_rejected(self):
        mask = self.save('mask.png', Image.new('L', (10, 10), 50))
        with self.assertRaises(ValueError):
            probe(self.source, background_mask=mask)

    def palette(self, colour=(0, 0, 0), size=(10, 10)):
        im = Image.new('P', size, 0)
        im.putpalette([255, 255, 255, *colour] + [0] * (768 - 6))
        im.putpixel((5, 5), 1)
        return im

    def test_changed_palette_rejected_in_protected_region(self):
        src = self.save('palette.png', self.palette())
        dst = self.save('palette-red.png', self.palette((255, 0, 0)))
        r = probe(dst, compare=src, protected=[(0, 0, 10, 10)])
        self.assertFalse(r['all_requested_checks_passed'])
        self.assertGreater(r['checks']['protected_regions']['regions'][0]['changed_channel_bytes'], 0)

    def test_changed_palette_rejected_in_padding(self):
        src = self.save('palette.png', self.palette())
        pad = self.palette((255, 0, 0), (14, 14))
        pad.putpixel((5, 5), 0); pad.putpixel((7, 7), 1)
        r = probe(self.save('pad.png', pad), padding_source=src, offset=(2, 2))
        self.assertFalse(r['checks']['padding']['source_pixels_equal'])
        self.assertFalse(r['all_requested_checks_passed'])

    def test_unchanged_palette_padding_passes(self):
        src = self.save('palette.png', self.palette())
        pad = self.palette(size=(14, 14))
        pad.putpixel((5, 5), 0); pad.putpixel((7, 7), 1)
        self.assertTrue(probe(self.save('pad.png', pad), padding_source=src,
                              offset=(2, 2))['all_requested_checks_passed'])

    def test_palette_transparency_rejected_in_both_comparisons(self):
        src = self.save('palette.png', self.palette())
        dst = self.palette(); dst.info['transparency'] = 1
        self.assertFalse(probe(self.save('alpha-p.png', dst), compare=src,
                               protected=[(0, 0, 10, 10)])['all_requested_checks_passed'])
        pad = self.palette(size=(14, 14)); pad.info['transparency'] = 1
        pad.putpixel((5, 5), 0); pad.putpixel((7, 7), 1)
        self.assertFalse(probe(self.save('alpha-pad.png', pad), padding_source=src,
                               offset=(2, 2))['all_requested_checks_passed'])

    def test_rgb_transparency_key_rejected(self):
        dst = self.im.copy(); dst.info['transparency'] = (10, 20, 30)
        self.assertFalse(probe(self.save('rgb-key.png', dst), compare=self.source,
                               protected=[(0, 0, 10, 10)])['all_requested_checks_passed'])

    def test_unused_palette_change_does_not_change_rendered_pixels(self):
        src = self.save('palette.png', self.palette())
        dst = self.palette(); palette = dst.getpalette()
        palette[6:9] = [99, 88, 77]; dst.putpalette(palette)
        self.assertTrue(probe(self.save('unused.png', dst), compare=src,
                              protected=[(0, 0, 10, 10)])['all_requested_checks_passed'])

    def test_icc_change_does_not_claim_unchanged_appearance(self):
        dst = self.im.copy(); dst.info['icc_profile'] = b'synthetic-profile-change'
        r = probe(self.save('icc.png', dst), compare=self.source, protected=[(0, 0, 10, 10)])
        self.assertEqual(r['checks']['protected_regions']['regions'][0]['changed_channel_bytes'], 0)
        self.assertFalse(r['checks']['protected_regions']['rendering_metadata_equal'])
        self.assertFalse(r['all_requested_checks_passed'])

    def test_orientation_change_does_not_pass(self):
        exif = Image.Exif(); exif[274] = 6
        dst = self.root / 'orientation.png'; self.im.save(dst, exif=exif)
        self.assertFalse(probe(dst, compare=self.source,
                               protected=[(0, 0, 10, 10)])['all_requested_checks_passed'])

    def test_high_bit_metadata_allowed_but_pixel_checks_rejected(self):
        src = self.save('high.png', Image.new('I;16', (2, 2), 65535))
        self.assertIsNone(probe(src)['all_requested_checks_passed'])
        with self.assertRaisesRegex(ValueError, 'do not support mode'):
            probe(src, compare=src, protected=[(0, 0, 2, 2)])
        with self.assertRaisesRegex(ValueError, 'do not support mode'):
            probe(src, backgrounds=[(0, 0, 2, 2)])

    def cli(self, *args):
        return subprocess.run([sys.executable, '-B', str(Path(__file__).with_name('image_probe.py')),
                               *map(str, args)], capture_output=True, text=True, encoding='utf-8')

    def test_cli_palette_regression_exits_nonzero(self):
        src = self.save('palette.png', self.palette())
        dst = self.save('palette-red.png', self.palette((255, 0, 0)))
        c = self.cli(dst, '--compare', src, '--protected-box', '0,0,10,10')
        self.assertEqual(c.returncode, 2, c.stderr)
        self.assertFalse(json.loads(c.stdout)['all_requested_checks_passed'])

    def test_cli_padding_regression_exits_nonzero(self):
        src = self.save('palette.png', self.palette())
        pad = self.palette((255, 0, 0), (14, 14))
        pad.putpixel((5, 5), 0); pad.putpixel((7, 7), 1)
        c = self.cli(self.save('pad.png', pad), '--padding-source', src, '--offset', '2,2')
        self.assertEqual(c.returncode, 2, c.stderr)

    def test_cli_never_overwrites_evidence(self):
        output = self.root / 'existing.json'; output.write_text('preserve', encoding='utf-8')
        c = self.cli(self.source, '--output', output)
        self.assertEqual(c.returncode, 2)
        self.assertEqual(output.read_text(encoding='utf-8'), 'preserve')


if __name__ == '__main__':
    unittest.main()
