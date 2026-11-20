#!/usr/bin/env python3
"""Usage: to_webp.py <dossier_png> <dossier_sortie> [taille=768] [qualite=80]
Recadre au carré (centre), redimensionne et écrit <id>.webp pour chaque PNG. Écrase les fichiers existants."""
import glob, os, shutil, sys
try:
    from PIL import Image, ImageOps
except ImportError:
    venv_python = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".venv", "bin", "python")
    if not os.environ.get("ASSET_PILLOW_RETRY"):
        os.environ["ASSET_PILLOW_RETRY"] = "1"
        if os.path.exists(venv_python):
            os.execv(venv_python, [venv_python, *sys.argv])
        if shutil.which("uv"):
            os.execvp("uv", ["uv", "run", "-q", "--no-project", "--with", "pillow", "python", *sys.argv])
    sys.exit("Pillow manquant : lancer bash " + os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/install.sh")
src, out = sys.argv[1], sys.argv[2]
size = int(sys.argv[3]) if len(sys.argv) > 3 else 768
quality = int(sys.argv[4]) if len(sys.argv) > 4 else 80
os.makedirs(out, exist_ok=True)
for f in sorted(glob.glob(os.path.join(src, '*.png'))):
    im = Image.open(f)
    im = im.convert('RGBA' if im.mode in ('RGBA', 'LA') else 'RGB')
    im = ImageOps.fit(im, (size, size), Image.LANCZOS)
    name = os.path.splitext(os.path.basename(f))[0]
    im.save(os.path.join(out, name + '.webp'), 'WEBP', quality=quality, method=6)
    print(name)
