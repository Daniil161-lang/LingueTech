#!/usr/bin/env python3
"""
iterative_rewriter.py
=====================

Generates a multi-pass rewrite workflow and prompts for repeated text improvement.
This script does not call an LLM directly; it creates deterministic iteration packs
that can be fed into any model/chat manually or via external automation.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Dict, List


PASSES = [
    {
        "name": "Structure and Argument Flow",
        "goal": "Improve section logic: context -> method -> result -> interpretation.",
        "checks": ["No duplicated paragraphs", "Each subsection ends with a concrete conclusion."],
    },
    {
        "name": "Evidence and Citation Grounding",
        "goal": "Ensure quantitative claims are backed by citations and evidence markers.",
        "checks": [
            "Every key claim has \\cite{...}",
            "Evidence markers [E-*] are consistent.",
            "Numeric statements are preserved/extracted from source context and not dropped.",
        ],
    },
    {
        "name": "Scientific Clarity",
        "goal": "Reduce vague language, add explicit mechanisms and limitations.",
        "checks": ["Avoid generic adjectives", "State uncertainty/limits explicitly."],
    },
    {
        "name": "Language and Readability",
        "goal": "Unify style, remove noisy phrasing, improve transitions.",
        "checks": ["Consistent terminology", "Paragraph openings are informative."],
    },
    {
        "name": "Final Tightening",
        "goal": "Polish concise and publication-ready narrative.",
        "checks": ["No unresolved TODO placeholders", "Abstract, intro, conclusion aligned."],
    },
]


CRITIC_PROMPT_TEMPLATE = """# Critic Step: Iteration {iteration:02d}

## Role
You are a strict scientific reviewer for the current article draft.

## Pass Focus
{pass_name}

## What to Evaluate
- Logical flow between sections and subsection transitions.
- Scientific grounding and citation adequacy.
- Factual consistency with evidence markers [E-*].
- Readability, precision of claims, and academic tone.
- Missing analysis depth, missing limitations, missing practical implications.
- Missing quantitative details (sample sizes, ranges, metric values, uncertainty where available).
- Discussion quality: comparison with literature, contradictions, and limitations.

## Required Output Format
1. Severity-ranked issues (major -> minor), each with:
   - location (file/section),
   - why it is a problem,
   - concrete fix instruction.
2. Expansion opportunities:
   - what can be expanded,
   - what evidence/citation should support it.
3. Final checklist for the reviser.
"""


REVISER_PROMPT_TEMPLATE = """# Revision Step: Iteration {iteration:02d}

## Input
- Critic report from `iter_{iteration:02d}_critic.md`
- Current LaTeX sections in `parts/*.tex`

## Pass Focus
{pass_name}

## Mandatory Actions
- Apply all major and medium critic findings.
- Expand sections where critic requested deeper analysis.
- Keep scientific style and avoid unsupported claims.
- Preserve figure references and citation correctness.
- Keep and foreground quantitative values from source context whenever available.
- In Discussion, include explicit comparison with 2-4 works and contradictions analysis.

## Deliverables
1. Short change summary.
2. Updated `parts/*.tex`.
3. Explicit list of fixed critic points.
"""


def _run_command(command: List[str], cwd: Path) -> Dict[str, str]:
    proc = subprocess.run(
        command,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return {
        "command": " ".join(command),
        "exit_code": proc.returncode,
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
    }


def _collect_parts_snapshot(parts_dir: Path) -> Dict[str, Dict[str, int]]:
    snapshot: Dict[str, Dict[str, int]] = {}
    for file_path in sorted(parts_dir.glob("*.tex")):
        text = file_path.read_text(encoding="utf-8", errors="ignore")
        snapshot[str(file_path)] = {
            "characters": len(text),
            "lines": len(text.splitlines()),
            "subsections": text.count("\\subsection"),
            "figures": text.count("\\begin{figure}"),
            "citations": text.count("\\cite{") + text.count("\\citep{") + text.count("\\citet{"),
        }
    return snapshot


def _build_prompt(pass_info: Dict[str, object], snapshot: Dict[str, Dict[str, int]]) -> str:
    lines = [
        f"# Rewrite Pass: {pass_info['name']}",
        "",
        f"## Goal",
        str(pass_info["goal"]),
        "",
        "## Quality Checks",
    ]
    for check in pass_info["checks"]:
        lines.append(f"- {check}")
    lines.extend(["", "## Current Snapshot"])
    for path, stats in snapshot.items():
        lines.append(
            f"- `{path}`: {stats['lines']} lines, {stats['characters']} chars, "
            f"{stats['subsections']} subsections, {stats['figures']} figures, {stats['citations']} citations"
        )
    lines.extend(
        [
            "",
            "## Instructions To Model",
            "Rewrite all `parts/*.tex` sections according to the Goal and Checks.",
            "Keep scientific tone and factual consistency.",
            "Do not invent references or numeric values.",
            "Extract quantitative facts from context and retain them explicitly in Results/Discussion.",
            "Discussion is mandatory to include: (1) comparison with 2-4 specific works, (2) agreement/disagreement, (3) possible causes, (4) practical implications and limitations.",
            "Preferred Discussion table format: Our result | Literature analogue | Agreement/Disagreement | Possible reason.",
            "Return a concise change summary before code changes.",
        ]
    )
    return "\n".join(lines)


def generate_iterations(root: Path, iterations: int, output_dir: Path, run_checks: bool) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    parts_snapshot = _collect_parts_snapshot(root / "parts")

    generated = []

    for idx in range(iterations):
        pass_info = PASSES[idx % len(PASSES)]
        prompt_text = _build_prompt(pass_info, parts_snapshot)
        prompt_file = output_dir / f"iter_{idx + 1:02d}_prompt.md"
        prompt_file.write_text(prompt_text, encoding="utf-8")
        critic_file = output_dir / f"iter_{idx + 1:02d}_critic.md"
        critic_file.write_text(
            CRITIC_PROMPT_TEMPLATE.format(iteration=idx + 1, pass_name=pass_info["name"]),
            encoding="utf-8",
        )

        reviser_file = output_dir / f"iter_{idx + 1:02d}_reviser.md"
        reviser_file.write_text(
            REVISER_PROMPT_TEMPLATE.format(iteration=idx + 1, pass_name=pass_info["name"]),
            encoding="utf-8",
        )

        generated.append(
            {
                "iteration": idx + 1,
                "pass": pass_info["name"],
                "prompt_file": str(prompt_file),
                "critic_file": str(critic_file),
                "reviser_file": str(reviser_file),
            }
        )

    check_results = []
    if run_checks:
        check_results.append(_run_command(["python3", "scripts/validate_citations.py"], root))
        check_results.append(_run_command(["python3", "scripts/validate_facts.py"], root))
        check_results.append(_run_command(["make"], root))

    report = {
        "iterations_requested": iterations,
        "iterations_generated": iterations,
        "generated_prompts": generated,
        "run_checks": run_checks,
        "check_results": check_results,
    }
    report_path = output_dir / "iteration_plan.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print("Iteration workflow generated.")
    print(f"- Prompts dir: {output_dir}")
    print(f"- Plan report: {report_path}")
    if run_checks:
        print("- Checks executed: validate_citations, validate_facts, make")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate multi-pass rewrite prompts and reports.")
    parser.add_argument("--iterations", type=int, default=5)
    parser.add_argument("--output-dir", default="out/rewrite_iterations")
    parser.add_argument("--run-checks", action="store_true")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent
    generate_iterations(
        root=root,
        iterations=max(1, args.iterations),
        output_dir=root / args.output_dir,
        run_checks=args.run_checks,
    )


if __name__ == "__main__":
    main()
