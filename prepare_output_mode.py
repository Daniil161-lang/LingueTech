#!/usr/bin/env python3
"""
prepare_output_mode.py
======================

Controls publication/internal output mode:
- internal: use full supplementary file
- publication: generate filtered supplementary without internal/service subsections
  and switch structure.tex to publication-safe include list.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import List


FORBIDDEN_MARKERS = [
    "coverage",
    "context used in this version",
    "draft",
    "auto-generated",
]


def write_structure(root: Path, mode: str) -> None:
    structure_path = root / "structure.tex"
    lines: List[str] = [
        r"\input{parts/01_Introduction}",
        r"\input{parts/02_Methods}",
        r"\input{parts/03_Results}",
        r"\input{parts/04_Discusion}",
        r"\input{parts/04_Conclusion}",
    ]
    if mode == "publication":
        lines.append(r"\input{parts/05_Supplementary_publication}")
    else:
        lines.append(r"\input{parts/05_Supplementary}")
    structure_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_publication_supplementary(root: Path) -> None:
    src = root / "parts/05_Supplementary.tex"
    dst = root / "parts/05_Supplementary_publication.tex"

    lines = src.read_text(encoding="utf-8", errors="ignore").splitlines()
    out: List[str] = []
    skip = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith(r"\subsection{"):
            title = stripped[len(r"\subsection{") :].rstrip("}").lower()
            skip = any(marker in title for marker in FORBIDDEN_MARKERS)
            if skip:
                continue
        if not skip:
            out.append(line)

    dst.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")


def validate_publication_blocks(root: Path) -> None:
    pub_file = root / "parts/05_Supplementary_publication.tex"
    text = pub_file.read_text(encoding="utf-8", errors="ignore").lower()
    hits = [marker for marker in FORBIDDEN_MARKERS if marker in text]
    if hits:
        raise RuntimeError(
            "Publication supplementary still contains forbidden markers: "
            + ", ".join(hits)
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare project output mode.")
    parser.add_argument("--mode", choices=["internal", "publication"], default="publication")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent
    if args.mode == "publication":
        build_publication_supplementary(root)
        validate_publication_blocks(root)
    write_structure(root, args.mode)

    print(f"Output mode prepared: {args.mode}")
    print(f"- structure.tex updated")
    if args.mode == "publication":
        print("- generated: parts/05_Supplementary_publication.tex")


if __name__ == "__main__":
    main()
