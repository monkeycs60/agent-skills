#!/usr/bin/env python3
"""Usage: contact_sheet.py <folder> <output.jpg> [thumbnail_size]
Assembles every image in the folder into a contact sheet (6 per row, name under each thumbnail)."""
import glob, os, shutil, sys
try:
    from PIL import Image, ImageDraw
except ImportError:
    venv_python = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".venv", "bin", "python")
    if not os.environ.get("ASSET_PILLOW_RETRY"):
        os.environ["ASSET_PILLOW_RETRY"] = "1"
        if os.path.exists(venv_python):
            os.execv(venv_python, [venv_python, *sys.argv])
        if shutil.which("uv"):
            os.execvp("uv", ["uv", "run", "-q", "--no-project", "--with", "pillow", "python", *sys.argv])
    sys.exit("Pillow missing: run bash " + os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/install.sh")
src, out = sys.argv[1], sys.argv[2]
size = int(sys.argv[3]) if len(sys.argv) > 3 else 220
files = sorted(f for f in glob.glob(os.path.join(src, '*')) if f.lower().endswith(('.png', '.webp', '.jpg', '.jpeg')))
if not files: sys.exit('no images found')
cols = min(6, len(files)); rows = (len(files) + cols - 1) // cols
sheet = Image.new('RGB', (cols * size, rows * (size + 18)), (12, 14, 20))
draw = ImageDraw.Draw(sheet)
for i, f in enumerate(files):
    im = Image.open(f).convert('RGB'); im.thumbnail((size, size))
    x, y = (i % cols) * size, (i // cols) * (size + 18)
    sheet.paste(im, (x + (size - im.width) // 2, y))
    draw.text((x + 4, y + size + 3), os.path.splitext(os.path.basename(f))[0], fill=(200, 205, 215))
os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
sheet.save(out, quality=82)
print(out, len(files), 'images')
