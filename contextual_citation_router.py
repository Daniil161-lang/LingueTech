#!/usr/bin/env python3
"""
contextual_citation_router.py
=============================

Builds section-aware citation recommendations using lightweight keyword matching:
- reads BibTeX entries;
- reads section files from parts/*.tex;
- recommends top references per section with explainable scores.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple


TOKEN_PATTERN = re.compile(r"[A-Za-zА-Яа-я0-9]+")


SECTION_HINTS = {
    "introduction": {"review", "overview", "challenge", "background", "introduction"},
    "methods": {"method", "protocol", "experimental", "workflow", "microfluidic"},
    "results": {"result", "analysis", "performance", "cluster", "validation"},
    "conclusion": {"conclusion", "future", "summary", "discussion"},
    "supplementary": {"supplementary", "appendix", "extended"},
}


def _tokenize(text: str) -> List[str]:
    return [token.lower() for token in TOKEN_PATTERN.findall(text)]


def _parse_bib_entries(bib_path: Path) -> Dict[str, Dict[str, str]]:
    content = bib_path.read_text(encoding="utf-8", errors="ignore")
    entries = {}

    for block in re.split(r"\n(?=@\w+\{)", content):
        match = re.match(r"@\w+\{([^,]+),", block.strip())
        if not match:
            continue
        key = match.group(1).strip()
        title = _extract_field(block, "title")
        journal = _extract_field(block, "journal")
        year = _extract_field(block, "year")
        entries[key] = {
            "title": title,
            "journal": journal,
            "year": year,
            "raw": block.strip(),
        }
    return entries


def _extract_field(block: str, field: str) -> str:
    match = re.search(rf"{field}\s*=\s*\{{([^}}]+)\}}", block, flags=re.IGNORECASE)
    return match.group(1).strip() if match else ""


def _section_kind_from_filename(filename: str) -> str:
    name = filename.lower()
    if "intro" in name:
        return "introduction"
    if "method" in name or "experiment" in name:
        return "methods"
    if "result" in name:
        return "results"
    if "conclusion" in name:
        return "conclusion"
    if "supplement" in name:
        return "supplementary"
    return "unknown"


def _score_entry(section_tokens: List[str], section_kind: str, entry: Dict[str, str]) -> Tuple[int, List[str]]:
    entry_text = " ".join([entry.get("title", ""), entry.get("journal", "")]).lower()
    entry_tokens = set(_tokenize(entry_text))
    section_set = set(section_tokens)
    overlap = section_set.intersection(entry_tokens)

    score = len(overlap) * 2
    reasons: List[str] = []
    if overlap:
        reasons.append(f"token overlap: {sorted(overlap)[:6]}")

    kind_hints = SECTION_HINTS.get(section_kind, set())
    hint_overlap = kind_hints.intersection(entry_tokens)
    if hint_overlap:
        score += len(hint_overlap) * 3
        reasons.append(f"section hints: {sorted(hint_overlap)}")

    year = entry.get("year", "")
    if year.isdigit() and int(year) >= 2020:
        score += 1
        reasons.append("recent reference boost")

    return score, reasons


def run_router(parts_dir: Path, bib_path: Path, top_k: int, output_path: Path) -> None:
    entries = _parse_bib_entries(bib_path)
    results = defaultdict(list)

    for part in sorted(parts_dir.glob("*.tex")):
        content = part.read_text(encoding="utf-8", errors="ignore")
        section_tokens = _tokenize(content)
        section_kind = _section_kind_from_filename(part.name)

        scored = []
        for key, entry in entries.items():
            score, reasons = _score_entry(section_tokens, section_kind, entry)
            if score > 0:
                scored.append(
                    {
                        "key": key,
                        "score": score,
                        "title": entry.get("title", ""),
                        "journal": entry.get("journal", ""),
                        "year": entry.get("year", ""),
                        "reasons": reasons,
                    }
                )

        scored.sort(key=lambda item: item["score"], reverse=True)
        results[str(part)] = {
            "section_kind": section_kind,
            "top_recommendations": scored[:top_k],
        }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Citation routing saved to: {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate section-aware citation recommendations.")
    parser.add_argument("--parts-dir", default="parts")
    parser.add_argument("--bib", default="refs/bib/references.bib")
    parser.add_argument("--top-k", type=int, default=12)
    parser.add_argument("--output", default="out/semantic/citation_routing.json")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent
    run_router(
        parts_dir=root / args.parts_dir,
        bib_path=root / args.bib,
        top_k=args.top_k,
        output_path=root / args.output,
    )


if __name__ == "__main__":
    main()
