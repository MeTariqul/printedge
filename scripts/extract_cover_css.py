# -*- coding: utf-8 -*-
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
html = (ROOT / "_external_cover.html").read_text(encoding="utf-8")
m = re.search(r"<style>(.*?)</style>", html, re.DOTALL)
css = m.group(1)

start = css.index(".cover-page {")
end = css.index(".form-panel::-webkit-scrollbar")
chunk = css[start:end]

# Drop preview-panel only rules before cover if any slipped in
chunk = re.sub(r"\.preview-panel[^{]*\{[^}]*\}", "", chunk, flags=re.DOTALL)

replacements = [
    ("var(--accent-gold)", "var(--pe-gold)"),
    ("var(--accent-gold-light)", "var(--pe-gold-light)"),
    ("var(--accent-gold-dark)", "var(--pe-gold-dark)"),
    ("var(--accent-navy)", "var(--pe-brand-dark)"),
    ("--accent-gold:", "--pe-gold:"),
    ("--accent-gold-light:", "--pe-gold-light:"),
    ("--accent-gold-dark:", "--pe-gold-dark:"),
    ("--accent-navy:", "--pe-brand-dark:"),
]
for a, b in replacements:
    chunk = chunk.replace(a, b)

# Scope selectors under #cover-sheet
def scope_css(text):
    out = []
    i = 0
    while i < len(text):
        if text[i] == "@" and text[i:].startswith("@media"):
            j = text.find("{", i)
            depth = 0
            k = j
            while k < len(text):
                if text[k] == "{":
                    depth += 1
                elif text[k] == "}":
                    depth -= 1
                    if depth == 0:
                        block = text[i : k + 1]
                        inner_start = block.find("{") + 1
                        inner_end = block.rfind("}")
                        inner = scope_css(block[inner_start:inner_end])
                        out.append(block[:inner_start] + inner + block[inner_end:])
                        i = k + 1
                        break
                k += 1
            else:
                out.append(text[i:])
                break
            continue

        if text[i] in "\n\r" or text[i] == " ":
            out.append(text[i])
            i += 1
            continue

        if text[i] == "}":
            out.append(text[i])
            i += 1
            continue

        j = text.find("{", i)
        if j == -1:
            out.append(text[i:])
            break
        selector = text[i:j].strip()
        k = j + 1
        depth = 1
        while k < len(text) and depth:
            if text[k] == "{":
                depth += 1
            elif text[k] == "}":
                depth -= 1
            k += 1
        body = text[j:k]
        if selector.startswith("#cover-sheet"):
            scoped = selector
        elif selector.startswith(".export-stage"):
            scoped = "#cover-sheet " + selector
        else:
            parts = [p.strip() for p in selector.split(",")]
            scoped_parts = []
            for p in parts:
                if p.startswith("#cover-sheet"):
                    scoped_parts.append(p)
                elif p.startswith("."):
                    scoped_parts.append("#cover-sheet " + p)
                else:
                    scoped_parts.append("#cover-sheet " + p)
            scoped = ", ".join(scoped_parts)
        out.append(scoped + body)
        i = k
    return "".join(out)

chunk = scope_css(chunk)

header = """/* Based on Assignment-Cover-Page by MeTariqul (MIT). Adapted for Print Edge. */

#cover-sheet {
  --pe-brand: #4f46e5;
  --pe-purple: #9333ea;
  --pe-dark: #0a0a0a;
  --pe-gold: #c9a227;
  --pe-gold-light: #e0e7ff;
  --pe-gold-dark: #4338ca;
  --pe-brand-dark: #312e81;
  --a4-width: 794px;
  --a4-height: 1123px;
  --primary-dark: #0f172a;
  --text-primary: #172033;
  --text-secondary: #5f6b7f;
  --shadow-soft: 0 18px 40px rgba(15, 23, 42, 0.08);
  --shadow-medium: 0 24px 60px rgba(15, 23, 42, 0.14);
  --shadow-strong: 0 32px 90px rgba(15, 23, 42, 0.2);
  width: 210mm;
  min-height: 297mm;
  background: #fff;
  overflow: hidden;
  box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
}

#cover-sheet .export-stage {
  position: fixed;
  left: -9999px;
  top: 0;
  z-index: -1;
}

@media print {
  body * { visibility: hidden !important; }
  #cover-print-root, #cover-print-root * { visibility: visible !important; }
  #cover-print-root { position: absolute; left: 0; top: 0; width: 100%; }
  #cover-sheet { box-shadow: none; margin: 0; transform: none !important; }
}

"""

out = ROOT / "static/css/cover-studio.css"
out.write_text(header + chunk, encoding="utf-8")
print("wrote", out, out.stat().st_size)
