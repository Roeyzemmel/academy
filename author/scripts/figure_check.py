#!/usr/bin/env python3
"""Mechanical figure rules of the Author's reviews (domain pack figures.md, "What the
Author's reviews corrected"): no tables or running text inside a figure, nothing tiny at
the printed width, short captions.

    figure_check.py tikz FILE [--compile] [--frac 0.85] [--textwidth-pt 430]
    figure_check.py captions FILE.tex [FILE.tex ...]

Exit 0 when clean, 1 on a violation (V), warnings (W) do not fail. Static checks need no
TeX; `--compile` builds the standalone figure in a scratch directory and measures the word
boxes of the PDF (pdftotext -bbox), scaled by frac * textwidth / natural width. The word-box
height of a math label is about 0.57 of its font size (calibrated on small labels), so the floor is set on that.
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile

MAX_NODE_CHARS = 12          # a label longer than this (outside math) is running text
MIN_EFFECTIVE_BOX_PT = 4.0   # printed word-box height; calibrated: math glyph boxes are ~0.57 of the font size, so about a 7pt font
MAX_CAPTION_SENTENCES = 4
MAX_CAPTION_WORDS = 90

TABLE_RE = re.compile(r"\\begin\{(tabular\*?|array|matrix|pmatrix|bmatrix)\}|matrix of nodes")
TINY_RE = re.compile(r"\\(tiny|scriptsize)\b|font=\\(tiny|scriptsize)|\\scriptstyle")
_PAREN = r"\((?:[^()]|\((?:[^()]|\([^()]*\))*\))*\)"
NODE_RE = re.compile(r"\bnode\b(?:\s*\[[^\]]*\])?(?:\s*\([^)]*\))?(?:\s*at\s*" + _PAREN + r")?"
                     r"(?:\s*\[[^\]]*\])?\s*\{((?:[^{}]|\{[^{}]*\})*)\}")


def strip_comments(text):
    return re.sub(r"(?<!\\)%.*", "", text)


def prose_length(label):
    """Characters of a node label outside math and control sequences."""
    s = re.sub(r"\$[^$]*\$", "", label)
    s = re.sub(r"\\[a-zA-Z]+\*?(\{[^{}]*\})?", "", s)
    return len(s.strip())


def static_tikz(path):
    text = strip_comments(open(path, encoding="utf-8", errors="replace").read())
    out = []
    for m in TABLE_RE.finditer(text):
        out.append(("V", "table or matrix inside a figure: move it to the caption or the text"))
    for m in TINY_RE.finditer(text):
        out.append(("W", "tiny font command %r: label must stay legible at the printed width" % m.group(0)))
    for m in NODE_RE.finditer(text):
        lab = m.group(1)
        if prose_length(lab) > MAX_NODE_CHARS:
            out.append(("V", "running text in a node (%r): only bare symbols inside a figure" % lab[:40]))
    return out


def _pdftotext():
    """The first pdftotext on PATH that supports -bbox (poppler; the xpdf build does not)."""
    for d in os.environ.get("PATH", "").split(os.pathsep):
        for n in ("pdftotext.exe", "pdftotext"):
            exe = os.path.join(d, n)
            if os.path.isfile(exe):
                probe = subprocess.run([exe, "-bbox", os.devnull, "-"], capture_output=True, text=True)
                if "-bbox" not in (probe.stderr + probe.stdout).split("Usage")[0] and \
                        "Unknown option" not in probe.stderr and "Usage" not in probe.stderr:
                    return exe
    return "pdftotext"


def printed_boxes(pdf):
    """Word boxes (height in pt) of a one-page pdf, and its page width in pt."""
    res = subprocess.run([_pdftotext(), "-bbox", pdf, "-"], capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError("pdftotext failed: " + res.stderr.strip())
    page = re.search(r'<page width="([\d.]+)"', res.stdout)
    boxes = []
    for m in re.finditer(r'yMin="([\d.]+)" xMax="[\d.]+" yMax="([\d.]+)">([^<]*)<', res.stdout):
        boxes.append((float(m.group(2)) - float(m.group(1)), m.group(3)))
    return boxes, float(page.group(1))


def compiled_tikz(path, frac, textwidth):
    work = tempfile.mkdtemp(prefix="figcheck-")
    try:
        env = dict(os.environ, TEXINPUTS=os.path.dirname(os.path.abspath(path)) + os.pathsep)
        subprocess.run(["pdflatex", "-interaction=nonstopmode", "-halt-on-error",
                              "-output-directory", work, os.path.abspath(path)],
                             capture_output=True, text=True, env=env, cwd=work)
        pdf = os.path.join(work, os.path.splitext(os.path.basename(path))[0] + ".pdf")
        if not os.path.exists(pdf):
            return [("V", "figure does not compile standalone")]
        boxes, natural = printed_boxes(pdf)
        scale = frac * textwidth / natural
        out = [("W", "natural width %.0fpt printed at %.0fpt (scale %.2f)" % (natural, frac * textwidth, scale))]
        for h, word in boxes:
            if h * scale < MIN_EFFECTIVE_BOX_PT:
                out.append(("V", "tiny at print size: %r, line box %.1fpt after scaling" % (word, h * scale)))
        return out
    finally:
        shutil.rmtree(work, ignore_errors=True)


def captions(path):
    text = strip_comments(open(path, encoding="utf-8", errors="replace").read())
    out = []
    for fig in re.finditer(r"\\begin\{figure\*?\}.*?\\end\{figure\*?\}", text, re.S):
        body = fig.group(0)
        line = text[:fig.start()].count("\n") + 1
        m = re.search(r"\\caption\{", body)
        if not m:
            continue
        i, depth = m.end(), 1
        while i < len(body) and depth:
            depth += {"{": 1, "}": -1}.get(body[i], 0)
            i += 1
        cap = re.sub(r"\$[^$]*\$", "M", body[m.end():i - 1])
        cap = re.sub(r"\\(cref|Cref|cite|label)\*?(\[[^\]]*\])?\{[^}]*\}", "X", cap)
        label = (re.search(r"\\label\{([^}]*)\}", body) or [None, "(no label)"])[1]
        words = len(cap.split())
        # a sentence ends at . ! ? followed by space and a capital; panel letters (a). do not
        sentences = len(re.findall(r"[.!?](?=\s+[A-Z]|\s*$)", cap.strip())) or 1
        if sentences > MAX_CAPTION_SENTENCES or words > MAX_CAPTION_WORDS:
            out.append(("V", "%s:%d %s: caption of %d sentences, %d words (max %d, %d): the "
                        "explanation belongs in the paragraph citing the figure"
                        % (path, line, label, sentences, words, MAX_CAPTION_SENTENCES, MAX_CAPTION_WORDS)))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("tikz")
    t.add_argument("file")
    t.add_argument("--compile", action="store_true")
    t.add_argument("--frac", type=float, default=0.85, help="width=<frac>\\linewidth of the include")
    t.add_argument("--textwidth-pt", type=float, default=430.0)
    c = sub.add_parser("captions")
    c.add_argument("files", nargs="+")
    a = ap.parse_args(argv)
    if a.cmd == "tikz":
        findings = static_tikz(a.file)
        if a.compile:
            findings += compiled_tikz(a.file, a.frac, a.textwidth_pt)
    else:
        findings = [f for p in a.files for f in captions(p)]
    for sev, msg in findings:
        print("%s: %s" % (sev, msg))
    bad = any(s == "V" for s, _ in findings)
    print("figure_check: %s" % ("FAIL" if bad else "ok"))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
