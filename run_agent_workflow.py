#!/usr/bin/env python3
"""
run_agent_workflow.py
=====================

Single-entry orchestrator for long-running article workflows.

What it does:
1) Semantic parse (draft -> bib/maps)
2) Citation routing by section context
3) Iteration plan generation
4) Optional rewrite command execution per iteration prompt
5) Validation and final build
6) Report export to JSON + markdown

Notes:
- This script can be fully automatic only if you provide a rewrite adapter command.
- Adapter command must accept prompt path placeholder: {prompt_file}
"""

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Optional


@dataclass
class StepResult:
    name: str
    command: str
    exit_code: int
    stdout: str
    stderr: str
    elapsed_sec: float


def run_cmd(name: str, command: List[str], cwd: Path) -> StepResult:
    start = datetime.now()
    proc = subprocess.run(
        command,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    elapsed = (datetime.now() - start).total_seconds()
    return StepResult(
        name=name,
        command=" ".join(command),
        exit_code=proc.returncode,
        stdout=proc.stdout.strip(),
        stderr=proc.stderr.strip(),
        elapsed_sec=elapsed,
    )


def ensure_ok(result: StepResult) -> None:
    if result.exit_code != 0:
        raise RuntimeError(
            f"Step failed: {result.name}\nCommand: {result.command}\n"
            f"Exit code: {result.exit_code}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )


def parse_iteration_plan(path: Path) -> List[Path]:
    data = json.loads(path.read_text(encoding="utf-8"))
    prompts = []
    for item in data.get("generated_prompts", []):
        prompts.append(Path(item["prompt_file"]))
    return prompts


def run_workflow(
    root: Path,
    iterations: int,
    rewrite_command_template: Optional[str],
    output_dir: Path,
    auto_docx: bool,
    docx_path: str,
    output_mode: str,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    results: List[StepResult] = []

    # 0) optional DOCX -> MD+TEI conversion
    if auto_docx:
        docx_abs = root / docx_path
        if docx_abs.exists():
            step = run_cmd(
                "docx_conversion",
                [
                    "python3",
                    "scripts/convert_docx_sources.py",
                    "--docx",
                    docx_path,
                    "--md",
                    "src/paper_data/new_draft.md",
                    "--tei",
                    "src/paper_data/new_draft.tei",
                ],
                root,
            )
            results.append(step)
            ensure_ok(step)

    # 1) semantic parse
    step = run_cmd("semantic_parse", ["python3", "scripts/parse_draft_semantic.py"], root)
    results.append(step)
    ensure_ok(step)

    # 2) citation routing
    step = run_cmd(
        "citation_routing",
        ["python3", "scripts/contextual_citation_router.py", "--top-k", "12"],
        root,
    )
    results.append(step)
    ensure_ok(step)

    # 3) iteration generation
    step = run_cmd(
        "iteration_generation",
        [
            "python3",
            "scripts/iterative_rewriter.py",
            "--iterations",
            str(iterations),
            "--run-checks",
        ],
        root,
    )
    results.append(step)
    ensure_ok(step)

    # 4) optional rewrite adapter execution
    iteration_plan = root / "out/rewrite_iterations/iteration_plan.json"
    prompt_files = parse_iteration_plan(iteration_plan)

    if rewrite_command_template:
        for idx, prompt in enumerate(prompt_files, start=1):
            cmd_text = rewrite_command_template.replace("{prompt_file}", str(prompt))
            step = run_cmd(
                f"rewrite_iter_{idx:02d}",
                ["bash", "-lc", cmd_text],
                root,
            )
            results.append(step)
            ensure_ok(step)

            # validate after each rewrite pass
            vc = run_cmd(
                f"validate_citations_iter_{idx:02d}",
                ["python3", "scripts/validate_citations.py"],
                root,
            )
            results.append(vc)
            ensure_ok(vc)

            vf = run_cmd(
                f"validate_facts_iter_{idx:02d}",
                ["python3", "scripts/validate_facts.py", "--check-usage"],
                root,
            )
            results.append(vf)
            ensure_ok(vf)

            vcross = run_cmd(
                f"validate_consistency_iter_{idx:02d}",
                ["python3", "scripts/validate_consistency.py"],
                root,
            )
            results.append(vcross)
            ensure_ok(vcross)

    # 5) output mode preparation + final validation, coverage report and build
    for name, cmd in [
        ("prepare_output_mode", ["python3", "scripts/prepare_output_mode.py", "--mode", output_mode]),
        ("final_validate_citations", ["python3", "scripts/validate_citations.py"]),
        ("final_validate_facts", ["python3", "scripts/validate_facts.py", "--check-usage"]),
        ("final_validate_consistency", ["python3", "scripts/validate_consistency.py"]),
        ("final_citation_coverage", ["python3", "scripts/citation_coverage_report.py"]),
        ("final_build", ["make"]),
    ]:
        step = run_cmd(name, cmd, root)
        results.append(step)
        ensure_ok(step)

    # 6) report
    report = {
        "timestamp": datetime.now().isoformat(),
        "root": str(root),
        "iterations": iterations,
        "rewrite_command_template": rewrite_command_template or "",
        "auto_rewrite_enabled": bool(rewrite_command_template),
        "auto_docx_enabled": auto_docx,
        "docx_path": docx_path,
        "output_mode": output_mode,
        "final_pdf": "out/Report_Final.pdf",
        "citation_coverage_report": "out/coverage/citation_coverage.md",
        "steps": [asdict(item) for item in results],
    }

    json_path = output_dir / "workflow_report.json"
    md_path = output_dir / "workflow_report.md"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        "# Agent Workflow Report",
        "",
        f"- Timestamp: {report['timestamp']}",
        f"- Iterations: {iterations}",
        f"- Auto rewrite enabled: {report['auto_rewrite_enabled']}",
        f"- Output mode: `{report['output_mode']}`",
        f"- Final PDF: `{report['final_pdf']}`",
        f"- Citation coverage: `{report['citation_coverage_report']}`",
        "",
        "## Steps",
    ]
    for item in results:
        status = "OK" if item.exit_code == 0 else "FAIL"
        lines.append(
            f"- `{item.name}`: {status} ({item.elapsed_sec:.2f}s) — `{item.command}`"
        )
    md_path.write_text("\n".join(lines), encoding="utf-8")

    print("Workflow complete.")
    print(f"- JSON report: {json_path}")
    print(f"- Markdown report: {md_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run full agent workflow from one command.")
    parser.add_argument("--iterations", type=int, default=5)
    parser.add_argument(
        "--rewrite-command",
        default="",
        help=(
            "Optional adapter command for auto rewrite. "
            "Use {prompt_file} placeholder. Example: "
            "\"python3 my_adapter.py --prompt-file {prompt_file}\""
        ),
    )
    parser.add_argument("--output-dir", default="out/workflow")
    parser.add_argument(
        "--output-mode",
        choices=["internal", "publication"],
        default="publication",
        help="Select output mode: internal (full service sections) or publication (clean output).",
    )
    parser.add_argument(
        "--auto-docx",
        action="store_true",
        help="If enabled and DOCX exists, convert draft.docx to draft.md + draft.tei first.",
    )
    parser.add_argument(
        "--docx-path",
        default="src/paper_data/new_draft.docx",
        help="Path to DOCX draft relative to project root.",
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent
    run_workflow(
        root=root,
        iterations=max(1, args.iterations),
        rewrite_command_template=args.rewrite_command.strip() or None,
        output_dir=root / args.output_dir,
        auto_docx=bool(args.auto_docx),
        docx_path=args.docx_path,
        output_mode=args.output_mode,
    )


if __name__ == "__main__":
    main()
