#!/usr/bin/env python3
"""
convert_docx_sources.py
=======================

Converts DOCX draft into Markdown and TEI using pandoc.

Usage:
    python3 scripts/convert_docx_sources.py \
        --docx src/paper_data/new_draft.docx \
        --md src/paper_data/new_draft.md \
        --tei src/paper_data/new_draft.tei
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path


def run_command(command: list[str], cwd: Path) -> None:
    proc = subprocess.run(
        command,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"Command failed: {' '.join(command)}\n"
            f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )


def convert_docx(docx: Path, md: Path, tei: Path, root: Path) -> None:
    if not docx.exists():
        raise FileNotFoundError(f"DOCX not found: {docx}")

    md.parent.mkdir(parents=True, exist_ok=True)
    tei.parent.mkdir(parents=True, exist_ok=True)

    pandoc = shutil.which("pandoc")
    if pandoc:
        # DOCX -> Markdown
        run_command([pandoc, str(docx), "-t", "gfm", "-o", str(md)], root)
        # DOCX -> TEI
        run_command([pandoc, str(docx), "-t", "tei", "-o", str(tei)], root)
        return

    # Fallback path: python-docx only
    try:
        from docx import Document  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(
            "Neither pandoc nor python-docx is available.\n"
            "Install one of them:\n"
            "  sudo apt install pandoc\n"
            "or\n"
            "  pip install python-docx"
        ) from exc

    doc = Document(str(docx))
    lines = []
    for paragraph in doc.paragraphs:
        text = paragraph.text.strip()
        if text:
            lines.append(text)

    if not lines:
        lines = ["(Empty DOCX content)"]

    # Minimal markdown fallback
    md.write_text("\n\n".join(lines) + "\n", encoding="utf-8")

    # Minimal TEI fallback (structure-first; bibliography parsing may be limited)
    escaped = "\n".join(
        f"        <p>{line.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')}</p>"
        for line in lines
    )
    tei_text = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<TEI xmlns="http://www.tei-c.org/ns/1.0">\n'
        "  <teiHeader>\n"
        "    <fileDesc>\n"
        "      <titleStmt><title>Converted from DOCX (fallback)</title></titleStmt>\n"
        "      <publicationStmt><p>Unpublished</p></publicationStmt>\n"
        "      <sourceDesc><p>DOCX fallback conversion</p></sourceDesc>\n"
        "    </fileDesc>\n"
        "  </teiHeader>\n"
        "  <text>\n"
        "    <body>\n"
        f"{escaped}\n"
        "    </body>\n"
        "  </text>\n"
        "</TEI>\n"
    )
    tei.write_text(tei_text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert draft DOCX into MD and TEI.")
    parser.add_argument("--docx", default="src/paper_data/new_draft.docx")
    parser.add_argument("--md", default="src/paper_data/new_draft.md")
    parser.add_argument("--tei", default="src/paper_data/new_draft.tei")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent
    docx = root / args.docx
    md = root / args.md
    tei = root / args.tei

    convert_docx(docx=docx, md=md, tei=tei, root=root)

    print("DOCX conversion complete.")
    print(f"- DOCX: {docx}")
    print(f"- MD: {md}")
    print(f"- TEI: {tei}")


if __name__ == "__main__":
    main()
