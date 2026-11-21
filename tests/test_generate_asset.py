import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

SCRIPTS = Path(__file__).resolve().parent.parent / "generate-asset" / "scripts"


class ConversionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="generate-asset-"))
        self.png = self.tmp / "png"
        self.png.mkdir()
        icon = Image.new("RGBA", (300, 200), (0, 0, 0, 0))
        ImageDraw.Draw(icon).rectangle((110, 60, 190, 140), fill=(200, 40, 40, 255))
        icon.save(self.png / "potion.png")
        Image.new("RGB", (120, 160), (30, 90, 200)).save(self.png / "texture.png")
        self.env = {**os.environ, "ASSET_PILLOW_RETRY": "1"}

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_script(self, name, *args):
        return subprocess.run([sys.executable, str(SCRIPTS / name), *map(str, args)],
                              capture_output=True, text=True, env=self.env, timeout=60)

    def test_webp_keeps_transparency_and_squares(self):
        out = self.tmp / "webp"
        r = self.run_script("to_webp.py", self.png, out, 64, 80)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.split(), ["potion", "texture"])
        with Image.open(out / "potion.webp") as potion:
            self.assertEqual((potion.format, potion.size, potion.mode), ("WEBP", (64, 64), "RGBA"))
            self.assertEqual(potion.getpixel((0, 32))[3], 0)
            self.assertEqual(potion.getpixel((32, 32))[3], 255)
        with Image.open(out / "texture.webp") as texture:
            self.assertEqual((texture.size, texture.mode), ((64, 64), "RGB"))

    def test_contact_sheet(self):
        sheet = self.tmp / "review" / "sheet.jpg"
        r = self.run_script("contact_sheet.py", self.png, sheet, 50)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("2 images", r.stdout)
        with Image.open(sheet) as image:
            self.assertEqual((image.format, image.size), ("JPEG", (100, 68)))
        empty = self.tmp / "empty"
        empty.mkdir()
        r = self.run_script("contact_sheet.py", empty, self.tmp / "none.jpg")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("no images found", r.stderr)


if __name__ == "__main__":
    unittest.main()
