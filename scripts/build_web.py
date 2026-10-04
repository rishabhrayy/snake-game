"""Build the browser version: pygbag compiles src/ to WebAssembly, then the output is copied
into site/game/, which the arcade page in site/index.html embeds.

Usage:  python scripts/build_web.py
"""

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "src" / "build" / "web"
GAME = ROOT / "site" / "game"

subprocess.run(
    [sys.executable, "-m", "pygbag", "--build", "--title", "Snake", "--ume_block", "0", str(ROOT / "src")],
    check=True,
)

GAME.mkdir(parents=True, exist_ok=True)
for name in ("index.html", "src.apk", "src.tar.gz", "favicon.png"):
    shutil.copy2(BUILD / name, GAME / name)
print(f"web build copied to {GAME}")
