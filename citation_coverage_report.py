#!/usr/bin/env python3
"""
citation_coverage_report.py
===========================

Builds coverage report for bibliography usage in parts/*.tex.
Outputs:
 - out/coverage/citation_coverage.json
 - out/coverage/citation_coverage.md
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Dict, List, Set


def extract_bib_keys(bib_path: Path) -> List[str]:
    text = bib_path.read_text(encoding="utf-8", errors="ignore")
    keys = re.findall(r"@\w+\{([^,]+),", text)
    return sorted(set(k.strip() for k in keys if k.strip()))


def extract_cite_keys(tex_path: Path) -> Set[str]:
    text = tex_path.read_text(encoding="utf-8", errors="ignore")
    matches = re.findall(r"\\(?:cite|citep|citet)\{([^}]+)\}", text)
    keys: Set[str] = set()
    for chunk in matches:
        for key in chunk.split(","):
            k = key.strip()
            if k:
                keys.add(k)
    return keys


def build_report(root: Path, bib_rel: str, parts_rel: str, out_dir_rel: str) -> Dict[str, object]:
    bib_path = root / bib_rel
    parts_dir = root / parts_rel
    out_dir = root / out_dir_rel
    out_dir.mkdir(parents=True, exist_ok=True)

    bib_keys = extract_bib_keys(bib_path)
    used_keys: Set[str] = set()
    file_usage: Dict[str, List[str]] = {}

    for tex_file in sorted(parts_dir.glob("*.tex")):
        keys = sorted(extract_cite_keys(tex_file))
        file_usage[str(tex_file)] = keys
        used_keys.update(keys)

    bib_set = set(bib_keys)
    used_sorted = sorted(used_keys)
    unused_sorted = sorted(bib_set - used_keys)
    unknown_sorted = sorted(used_keys - bib_set)
    coverage_pct = (len(used_keys & bib_set) / len(bib_set) * 100.0) if bib_set else 0.0

    data: Dict[str, object] = {
        "bib_file": str(bib_path),
        "parts_dir": str(parts_dir),
        "total_bib_keys": len(bib_keys),
        "used_bib_keys": len(used_keys & bib_set),
        "unused_bib_keys": len(unused_sorted),
        "unknown_cited_keys": len(unknown_sorted),
        "coverage_percent": round(coverage_pct, 2),
        "used_keys": used_sorted,
        "unused_keys": unused_sorted,
        "unknown_cited_keys_list": unknown_sorted,
        "file_usage": file_usage,
    }

    json_path = out_dir / "citation_coverage.json"
    md_path = out_dir / "citation_coverage.md"
    json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    md_lines = [
        "# Citation Coverage Report",
        "",
        f"- Bib file: `{bib_path}`",
        f"- Parts dir: `{parts_dir}`",
        f"- Total bib keys: **{data['total_bib_keys']}**",
        f"- Used bib keys: **{data['used_bib_keys']}**",
        f"- Unused bib keys: **{data['unused_bib_keys']}**",
        f"- Unknown cited keys: **{data['unknown_cited_keys']}**",
        f"- Coverage: **{data['coverage_percent']}%**",
        "",
        "## Unused Keys",
    ]
    if unused_sorted:
        md_lines.extend([f"- `{k}`" for k in unused_sorted])
    else:
        md_lines.append("- None")

    md_lines.extend(["", "## Per-file Usage"])
    for file_path, keys in file_usage.items():
        md_lines.append(f"- `{file_path}`: {len(keys)} keys")

    md_path.write_text("\n".join(md_lines), encoding="utf-8")
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate citation coverage report.")
    parser.add_argument("--bib", default="refs/bib/references.bib")
    parser.add_argument("--parts", default="parts")
    parser.add_argument("--out-dir", default="out/coverage")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent
    data = build_report(root, args.bib, args.parts, args.out_dir)
    print("Citation coverage report generated.")
    print(f"- Coverage: {data['coverage_percent']}%")
    print(f"- Used: {data['used_bib_keys']} / {data['total_bib_keys']}")
    print(f"- Output: {root / args.out_dir}")


if __name__ == "__main__":
    main()
