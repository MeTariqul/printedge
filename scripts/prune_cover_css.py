# -*- coding: utf-8 -*-
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
main = ROOT / "static/css/cover-studio.css"
ext = ROOT / "static/css/cover-studio-extensions.css"
out = ROOT / "static/css/cover-studio.css"

text = main.read_text(encoding="utf-8")
cut = text.find("#cover-sheet .template-split")
if cut == -1:
    cut = text.find("\n#cover-sheet .template-split")
if cut > 0:
    text = text[:cut].rstrip() + "\n\n"

extensions = ext.read_text(encoding="utf-8")
out.write_text(text + extensions, encoding="utf-8")
print("wrote", out, "bytes", out.stat().st_size)
ext.unlink(missing_ok=True)
