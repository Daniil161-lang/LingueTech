#!/usr/bin/env python3
"""
validate_consistency.py
-----------------------
Checks that claims in non-source sections do not contradict Methods/Results.

Source-of-truth sections:
- parts/02_Methods.tex
- parts/03_Results.tex

Checked sections:
- parts/01_Introduction.tex
- parts/04_Discusion.tex
- parts/04_Conclusion.tex
- parts/05_Supplementary.tex
- parts/05_Supplementary_publication.tex
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import List, Tuple


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def _norm_spaces(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def _split_sentences(text: str) -> List[str]:
    parts = re.split(r"(?<=[\.\!\?])\s+|\n+", text)
    return [_norm_spaces(p) for p in parts if _norm_spaces(p)]


def _extract_result_facts(results_text: str) -> dict:
    facts = {}

    # Prefer explicit paired statement in Results when available.
    pair = re.search(
        r"max\-450.*?R²\s*=\s*([\-−]?\d+(?:\.\d+)?).*?max\|450.*?R²\s*=\s*([\-−]?\d+(?:\.\d+)?)",
        results_text,
        flags=re.S,
    )
    if pair:
        facts["r2_max_minus_450"] = float(pair.group(1).replace("−", "-"))
        facts["r2_max_bar_450"] = float(pair.group(2).replace("−", "-"))
        return facts

    # Fallback: descriptor-local extraction with limited span.
    m = re.search(r"max\-450[^\\n]{0,200}?R²\s*=\s*([\-−]?\d+(?:\.\d+)?)", results_text)
    if m:
        facts["r2_max_minus_450"] = float(m.group(1).replace("−", "-"))
    m = re.search(r"max\|450[^\\n]{0,200}?R²\s*=\s*([\-−]?\d+(?:\.\d+)?)", results_text)
    if m:
        facts["r2_max_bar_450"] = float(m.group(1).replace("−", "-"))
    return facts


def _extract_r2_for_descriptor(sent: str, descriptor: str) -> List[float]:
    out: List[float] = []
    # Pattern A: "... max|450 ... R^2 = -0.08"
    p1 = re.findall(
        rf"{re.escape(descriptor)}.*?(?:R\$\^2\$|R²)\s*=\s*([\-]?\d+(?:\.\d+)?)",
        sent,
        flags=re.I,
    )
    for raw in p1:
        out.append(float(raw))
    return out


def _check_r2_consistency(sent: str, facts: dict) -> List[str]:
    errs: List[str] = []
    # normalize unicode minus
    s = sent.replace("−", "-")
    if "R$^2$" not in s and "R²" not in s:
        return errs

    expected_bar = facts.get("r2_max_bar_450")
    expected_minus = facts.get("r2_max_minus_450")

    # Comparative sentences often mention both descriptors and two R² values
    # (e.g., "-0.08 vs 0.29"). Validate as an unordered pair to avoid
    # directional parsing artifacts.
    if "max|450" in s and "max-450" in s:
        all_vals = re.findall(r"(?:R\$\^2\$|R²)\s*=\s*([\-]?\d+(?:\.\d+)?)", s)
        if len(all_vals) >= 2 and expected_bar is not None and expected_minus is not None:
            pair = sorted([float(all_vals[0]), float(all_vals[1])])
            exp_pair = sorted([expected_bar, expected_minus])
            if pair != exp_pair:
                errs.append(
                    f"Comparative R^2 pair differs from Results: {pair} vs {exp_pair}"
                )
            return errs

    vals_bar = _extract_r2_for_descriptor(s, "max|450")
    vals_minus = _extract_r2_for_descriptor(s, "max-450")

    if expected_bar is not None:
        for n in vals_bar:
            if abs(n - expected_bar) > 1e-6:
                if expected_minus is not None and abs(n - expected_minus) <= 1e-6:
                    errs.append(f"R^2 for max|450 swapped with max-450 value: {n}")
                else:
                    errs.append(f"R^2 for max|450 differs from Results: {n} vs {expected_bar}")

    if expected_minus is not None:
        for n in vals_minus:
            if abs(n - expected_minus) > 1e-6:
                if expected_bar is not None and abs(n - expected_bar) <= 1e-6:
                    errs.append(f"R^2 for max-450 swapped with max|450 value: {n}")
                else:
                    errs.append(f"R^2 for max-450 differs from Results: {n} vs {expected_minus}")
    return errs


def _check_rule_consistency(sent: str) -> List[str]:
    errs: List[str] = []
    low = sent.lower()

    # CTAB excess (>2.5) should not be called optimal/high-quality.
    if ("ctab" in low and "> 2.5" in low) or ("ctab" in low and ">$2.5" in low):
        if any(w in low for w in ["оптим", "high", "луч", "повыш", "максим"]):
            errs.append("CTAB/Au > 2.5 marked as favorable, contradicts Results.")

    # For CTAB/NaI system: CTAB/Au < 1.5 corresponds to low response region.
    if "ctab/au" in low and "< 1.5" in low:
        if any(w in low for w in ["оптим", "high", "луч", "максим", "высок"]):
            errs.append("CTAB/Au < 1.5 marked as favorable, contradicts Results.")

    # For PVP system: PVP/Au > 0.3 should not be called optimal.
    if "pvp/au" in low and "> 0.3" in low:
        if any(w in low for w in ["оптим", "high", "луч", "максим", "высок"]):
            errs.append("PVP/Au > 0.3 marked as favorable, contradicts Results.")
    return errs


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate cross-section consistency against Results.")
    parser.add_argument("--parts-dir", default="parts")
    args = parser.parse_args()

    parts = Path(args.parts_dir)
    results_path = parts / "03_Results.tex"
    methods_path = parts / "02_Methods.tex"
    if not results_path.exists() or not methods_path.exists():
        print("ERROR: Methods/Results files not found.", file=sys.stderr)
        sys.exit(1)

    results_text = _read(results_path)
    facts = _extract_result_facts(results_text)
    if "r2_max_bar_450" not in facts or "r2_max_minus_450" not in facts:
        print("ERROR: Cannot extract baseline R² facts from Results.", file=sys.stderr)
        sys.exit(1)

    targets = [
        parts / "01_Introduction.tex",
        parts / "04_Discusion.tex",
        parts / "04_Conclusion.tex",
        parts / "05_Supplementary.tex",
        parts / "05_Supplementary_publication.tex",
    ]
    findings: List[Tuple[str, str, str]] = []
    for path in targets:
        if not path.exists():
            continue
        for sent in _split_sentences(_read(path)):
            for err in _check_r2_consistency(sent, facts):
                findings.append((str(path), err, sent))
            for err in _check_rule_consistency(sent):
                findings.append((str(path), err, sent))

    if findings:
        print("ERROR: Cross-section consistency check failed.")
        for path, err, sent in findings:
            print(f"- {path}: {err}")
            print(f"  -> {sent}")
        sys.exit(1)

    print("OK: Cross-section consistency check passed.")


if __name__ == "__main__":
    main()

