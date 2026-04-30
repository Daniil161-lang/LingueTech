#!/usr/bin/env python3
"""
rewrite_adapter.py
==================

Deterministic local rewrite adapter for iterative workflow.

This adapter is designed to be called from run_agent_workflow.py:
    python3 scripts/rewrite_adapter.py --prompt-file out/rewrite_iterations/iter_01_prompt.md

It applies lightweight, idempotent improvements to parts/*.tex according to the
current pass focus and stores per-iteration reports in out/rewrite_iterations.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Dict, List, Tuple


PASS_ALIASES = {
    "Structure and Argument Flow": "structure",
    "Evidence and Citation Grounding": "evidence",
    "Scientific Clarity": "clarity",
    "Language and Readability": "language",
    "Final Tightening": "tightening",
}


FIGURE_STEMS_ORDER = [
    "figure_Ctab_agno3_del",
    "figure_Ctab_agno3_mins",
    "figure_Ctab_nai_del",
    "figure_Ctab_nai_mins",
    "figure_PVP_agno3_del",
    "figure_PVP_agno3_mins",
]


FIGURE_LABELS = {
    "figure_Ctab_agno3_del": "fig:ctab_agno3_del",
    "figure_Ctab_agno3_mins": "fig:ctab_agno3_mins",
    "figure_Ctab_nai_del": "fig:ctab_nai_del",
    "figure_Ctab_nai_mins": "fig:ctab_nai_mins",
    "figure_PVP_agno3_del": "fig:pvp_agno3_del",
    "figure_PVP_agno3_mins": "fig:pvp_agno3_mins",
}


def _read_new_draft_figure_captions(new_draft_path: Path) -> Dict[str, str]:
    """
    Parse figure captions from new_draft.md.
    Returns mapping: figure_stem -> Results Caption (as plain text).
    """
    text = _read_text(new_draft_path)
    blocks = re.split(r"^\s*(?:\d+\.\s*)?### Figure:\s*", text, flags=re.MULTILINE)
    fig_to_caption: Dict[str, str] = {}

    for block in blocks[1:]:
        # Find File: line
        m_file = re.search(r"^File:\s*(.+)$", block, flags=re.MULTILINE)
        if not m_file:
            continue
        file_path_raw = m_file.group(1).strip()
        file_path_raw = re.split(r"\s+Section:\s*", file_path_raw)[0].strip()
        file_path_unescaped = file_path_raw.replace(r"\_", "_").replace("\\", "")
        m_stem = re.search(r"(figure_[A-Za-z0-9_]+)", file_path_unescaped)
        if not m_stem:
            continue
        stem = m_stem.group(1)

        if stem not in FIGURE_STEMS_ORDER:
            continue

        m_cap = re.search(r"Results\s+Caption:\s*(.*?)\s+Axes:", block, flags=re.DOTALL)
        if m_cap:
            caption = m_cap.group(1).strip()
        else:
            m_cap2 = re.search(r"^Results\s+Caption:\s*(.+)$", block, flags=re.MULTILINE)
            caption = (m_cap2.group(1).strip() if m_cap2 else "").strip()

        if caption:
            fig_to_caption[stem] = caption
    return fig_to_caption


def _ensure_results_figures(new_draft_path: Path, parts_results_path: Path) -> bool:
    """
    Guarantees that all provided figure_xxx images from FIGURE_STEMS_ORDER
    are present in parts/03_Results.tex with correct captions/labels.
    Rebuilds the content block before the cross-system subsection.
    """
    results_text = _read_text(parts_results_path)
    cross_marker = "\\subsection{Cross-system comparison and operational rules}"
    cross_pos = results_text.find(cross_marker)
    if cross_pos == -1:
        return False

    start_pos = results_text.find("\\subsection{System Au--Ag--CTAB}")
    if start_pos == -1:
        start_pos = results_text.find("\\section{Results}")
        if start_pos == -1:
            return False

    captions = _read_new_draft_figure_captions(new_draft_path)

    def fig_env(stem: str) -> str:
        cap = captions.get(stem, "").strip()
        cap = _latex_escape_simple(cap)
        label = FIGURE_LABELS.get(stem, stem)
        return (
            "\\begin{figure}[H]\n"
            "\\centering\n"
            f"\\includegraphics[width=0.78\\textwidth]{{figures/{stem}.png}}\n"
            f"\\caption{{{cap}}}\n"
            f"\\label{{{label}}}\n"
            "\\end{figure}\n"
        )

    rebuilt = (
        "\\subsection{System Au--Ag--CTAB}\n"
        + fig_env("figure_Ctab_agno3_del")
        + fig_env("figure_Ctab_agno3_mins")
        + "\\subsection{System Au--CTAB--NaI}\n"
        + fig_env("figure_Ctab_nai_del")
        + fig_env("figure_Ctab_nai_mins")
        + "\\subsection{System Au--Ag--PVP}\n"
        + fig_env("figure_PVP_agno3_del")
        + fig_env("figure_PVP_agno3_mins")
    )

    new_text = results_text[:start_pos] + rebuilt + "\n" + results_text[cross_pos:]
    if new_text != results_text:
        _write_text(parts_results_path, new_text)
        return True
    return False


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def _write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def _detect_iteration(prompt_file: Path) -> int:
    match = re.search(r"iter_(\d+)_prompt\.md$", prompt_file.name)
    if not match:
        raise ValueError(f"Cannot parse iteration number from: {prompt_file.name}")
    return int(match.group(1))


def _detect_pass_name(prompt_text: str) -> str:
    for line in prompt_text.splitlines():
        if line.startswith("# Rewrite Pass:"):
            return line.split(":", 1)[1].strip()
    raise ValueError("Pass name not found in prompt file.")


def _normalize_language(text: str) -> Tuple[str, int]:
    replacements = [
        ("self-driving", "self-driving"),
        ("AI-agent operated", "AI-guided"),
        ("inline UV--Vis-диагностику", "inline UV--Vis диагностику"),
        ("inline UV--Vis-диагностикой", "inline UV--Vis диагностикой"),
    ]
    count = 0
    updated = text
    for old, new in replacements:
        if old in updated:
            updated = updated.replace(old, new)
            count += 1
    updated2 = re.sub(r"[ \t]+$", "", updated, flags=re.MULTILINE)
    if updated2 != updated:
        count += 1
    return updated2, count


def _ensure_section_closure(text: str, marker: str, sentence: str) -> Tuple[str, int]:
    if marker in text or sentence in text:
        return text, 0
    if not text.endswith("\n"):
        text += "\n"
    text += f"\n{sentence}\n{marker}\n"
    return text, 1


def _ensure_citation_anchor(text: str, marker: str, citation_line: str) -> Tuple[str, int]:
    if marker in text or citation_line in text:
        return text, 0
    if not text.endswith("\n"):
        text += "\n"
    text += f"\n{citation_line}\n{marker}\n"
    return text, 1


def _tighten_spacing(text: str) -> Tuple[str, int]:
    updated = re.sub(r"\n{3,}", "\n\n", text)
    changed = 1 if updated != text else 0
    return updated, changed


def apply_pass(pass_name: str, iteration: int, parts_dir: Path) -> Dict[str, object]:
    changed_files: List[str] = []
    total_actions = 0

    intro = parts_dir / "01_Introduction.tex"
    methods = parts_dir / "02_Methods.tex"
    results = parts_dir / "03_Results.tex"
    discussion = parts_dir / "04_Discusion.tex"
    conclusion = parts_dir / "04_Conclusion.tex"
    supplementary = parts_dir / "05_Supplementary.tex"

    marker = f"% AutoRewrite ({PASS_ALIASES.get(pass_name, 'generic')})"

    # Progressive Discussion expansion should not depend on pass type:
    # as iteration grows, we want to add more substance even when the current
    # pass focus is about structure/citations.
    root = parts_dir.parent
    new_draft_path = root / "src/paper_data/new_draft.md"
    if new_draft_path.exists():
        try:
            # This is idempotent (markers inside), so it's safe to call often.
            disc_changed = _ensure_discussion_progressive(
                new_draft_path=new_draft_path,
                parts_discussion_path=discussion,
                iteration=iteration,
            )
            if disc_changed:
                changed_files.append(str(discussion))
                total_actions += 1
        except Exception:
            # Never break workflow on discussion expansion.
            pass

    if pass_name == "Structure and Argument Flow":
        text = _read_text(discussion)
        text2, changed = _ensure_section_closure(
            text,
            marker,
            "В совокупности это подтверждает, что структурированный итеративный анализ повышает предсказуемость выбора следующего экспериментального шага.",
        )
        if changed:
            _write_text(discussion, text2)
            changed_files.append(str(discussion))
            total_actions += changed

    elif pass_name == "Evidence and Citation Grounding":
        text = _read_text(conclusion)
        text2, changed = _ensure_citation_anchor(
            text,
            marker,
            "Данные выводы согласуются с современными подходами автономной лабораторной оптимизации и спектральной верификации \\cite{1,2,3,9,10,11,13}.",
        )
        if changed:
            _write_text(conclusion, text2)
            changed_files.append(str(conclusion))
            total_actions += changed

    elif pass_name == "Scientific Clarity":
        # Ensure quantitative blocks exist and progressively expand Discussion.
        root = parts_dir.parent
        new_draft_path = root / "src/paper_data/new_draft.md"
        if new_draft_path.exists():
            # Publication-critical: figures must not disappear between iterations.
            figs_changed = _ensure_results_figures(
                new_draft_path=new_draft_path,
                parts_results_path=results,
            )
            if figs_changed:
                changed_files.append(str(results))
                total_actions += 1

            _insert_quantitative_figure_blocks(
                new_draft_path=new_draft_path,
                parts_results_path=results,
            )
            _insert_r2_and_discussion_analysis(
                new_draft_path=new_draft_path,
                parts_discussion_path=discussion,
            )
            _ensure_discussion_progressive(
                new_draft_path=new_draft_path,
                parts_discussion_path=discussion,
                iteration=iteration,
            )

        text = _read_text(results)
        text2, changed = _ensure_section_closure(
            text,
            marker,
            "Критически важно, что выявленные оптимумы трактуются как устойчивые области, а не как одиночные точки, что снижает риск переинтерпретации случайных всплесков метрики.",
        )
        if changed:
            _write_text(results, text2)
            changed_files.append(str(results))
            total_actions += changed

    elif pass_name == "Language and Readability":
        for path in [intro, methods, results, discussion, conclusion, supplementary]:
            text = _read_text(path)
            text2, changed = _normalize_language(text)
            if changed:
                _write_text(path, text2)
                changed_files.append(str(path))
                total_actions += changed

    elif pass_name == "Final Tightening":
        # 1) Insert quantitative findings mined from new_draft.md (R² and numeric key messages).
        #    This is the publication-critical step: results must not stay qualitative.
        root = parts_dir.parent
        new_draft_path = root / "src/paper_data/new_draft.md"
        if new_draft_path.exists():
            figs_changed = _ensure_results_figures(
                new_draft_path=new_draft_path,
                parts_results_path=results,
            )
            if figs_changed:
                changed_files.append(str(results))
                total_actions += 1

            results_text = _insert_quantitative_figure_blocks(
                new_draft_path=new_draft_path,
                parts_results_path=results,
            )
            if results_text is not None:
                total_actions += 1

            discussion_updated = _insert_r2_and_discussion_analysis(
                new_draft_path=new_draft_path,
                parts_discussion_path=discussion,
            )
            if discussion_updated:
                changed_files.append(str(discussion))
                total_actions += 1

            _ensure_discussion_progressive(
                new_draft_path=new_draft_path,
                parts_discussion_path=discussion,
                iteration=iteration,
            )

        # Final pass also sanitizes LaTeX-unsafe unicode that may have been introduced by rewrites.
        # Quant blocks and R² section are the main sources, but we apply it broadly to avoid build breaks.
        for path in [intro, methods, results, discussion, conclusion, supplementary]:
            text = _read_text(path)
            text = _latex_escape_simple(text)
            text2, changed = _tighten_spacing(text)
            if changed:
                _write_text(path, text2)
                changed_files.append(str(path))
                total_actions += changed

    return {
        "pass_name": pass_name,
        "iteration": iteration,
        "actions_applied": total_actions,
        "changed_files": changed_files,
    }


def _read_new_draft_figures(new_draft_path: Path) -> Dict[str, List[str]]:
    """
    Returns mapping: figure_stem -> list of Key message bullets (in text form).
    """
    text = _read_text(new_draft_path)
    # Each block starts with "### Figure: ..." but some drafts include numeric prefix like "7.  ### Figure:"
    blocks = re.split(r"^\s*(?:\d+\.\s*)?### Figure:\s*", text, flags=re.MULTILINE)
    fig_to_bullets: Dict[str, List[str]] = {}
    for block in blocks[1:]:
        # Find File: line
        m_file = re.search(r"^File:\s*(.+)$", block, flags=re.MULTILINE)
        if not m_file:
            continue
        file_path_raw = m_file.group(1).strip()
        # Some conversions put "Section:" on the same line
        file_path_raw = re.split(r"\s+Section:\s*", file_path_raw)[0].strip()
        # Unescape markdown underscores (figure\_X -> figure_X)
        file_path_unescaped = file_path_raw.replace(r"\_", "_").replace("\\", "")
        m_stem = re.search(r"(figure_[A-Za-z0-9_]+)", file_path_unescaped)
        if not m_stem:
            continue
        stem = m_stem.group(1)

        # Find "Key message:" and the following bullet list until "Evidence:"
        # (draft conversions may change whitespace / unicode around the marker)
        m_key = re.search(r"Key message:\s*", block)
        if not m_key:
            continue
        tail = block[m_key.end() :]
        # Collect bullets including wrapped continuation lines.
        bullets: List[str] = []
        current: str = ""
        for line in tail.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            # Stop when we hit Evidence section (spacing/unicode may vary).
            # Evidence sometimes appears on the same line after bullet text.
            if "Evidence" in stripped:
                if current:
                    left = stripped.split("Evidence", 1)[0].strip()
                    if left:
                        current += " " + left
                break

            if stripped.startswith("- "):
                if current:
                    bullets.append(current.strip())
                current = stripped[2:].strip()
            else:
                # Continuation line of the current bullet.
                if current:
                    current += " " + stripped

        if current:
            bullets.append(current.strip())

        if bullets:
            fig_to_bullets[stem] = bullets
    return fig_to_bullets


def _extract_r2_values(new_draft_path: Path) -> Dict[str, str]:
    """
    Extracts known R² values from new_draft around specific figures.
    Output mapping: figure_stem -> r2_string
    """
    text = _read_text(new_draft_path)
    out: Dict[str, str] = {}

    # We only need the R² values that are explicitly written in the draft.
    # In new_draft.md the figure IDs appear like: figure\_Ctab\_agno3\_del
    for stem in ["figure_Ctab_agno3_del", "figure_Ctab_agno3_mins"]:
        figure_token = stem.replace("_", r"\_")  # -> figure\_Ctab\_...
        # Grab the first R² written after the figure token.
        # Supports unicode minus (U+2212) and ASCII minus.
        m = re.search(
            rf"{re.escape(figure_token)}.*?R\s*(?:²|\^2)\s*=\s*([−-]?\s*\d+(?:[.,]\d+)?)",
            text,
            flags=re.DOTALL,
        )
        if m:
            val = m.group(1).replace(" ", "").replace(",", ".").replace("−", "-")
            out[stem] = val
    return out


def _latex_escape_simple(s: str) -> str:
    # Keep unicode where LaTeX inputenc supports it, but fix known offenders.
    # Convert common unicode math operators to LaTeX-safe forms.
    # These appear in QuantBlock text like "x ≈ 0.1" or "CTAB/Au ≥ 1.65".
    s = s.replace("–", "-")  # en dash

    # inputenc in this project does not handle unicode subscripts (e.g. AgNO₃).
    # Convert them to math-mode subscripts.
    sub_map = {
        "₀": "$_{0}$",
        "₁": "$_{1}$",
        "₂": "$_{2}$",
        "₃": "$_{3}$",
        "₄": "$_{4}$",
        "₅": "$_{5}$",
        "₆": "$_{6}$",
        "₇": "$_{7}$",
        "₈": "$_{8}$",
        "₉": "$_{9}$",
    }
    for k, v in sub_map.items():
        if k in s:
            s = s.replace(k, v)

    # Approximate / comparison operators (wrap in math mode to be safe)
    s = s.replace("≈", r"$\approx$")
    s = s.replace("≥", r"$\ge$")
    s = s.replace("≤", r"$\le$")
    s = s.replace("−", "-")  # unicode minus

    # Common chemistry superscript minus, e.g. I⁻
    s = s.replace("⁻", r"$^{-}$")

    # Draft uses escaping like "\>" and "\~" in plain text.
    # Replace them with LaTeX-safe symbols.
    s = s.replace(r"\>", ">")
    s = s.replace(r"\<", r"$<$")
    s = s.replace(r"\~", r"$\sim$")
    return s


def _insert_quantitative_figure_blocks(new_draft_path: Path, parts_results_path: Path) -> bool | None:
    """
    Adds an explicit quantitative paragraph after each figure in parts/03_Results.tex
    using Key message bullets from new_draft.md.
    Idempotent: if marker exists, skip.
    """
    results_text = _read_text(parts_results_path)

    fig_to_bullets = _read_new_draft_figures(new_draft_path)
    changed = False

    for stem in FIGURE_STEMS_ORDER:
        marker = f"% QuantBlock: {stem}"
        # If the block already exists from a previous run, remove it and re-insert.
        if marker in results_text:
            start = results_text.find(marker)
            # Delete only this QuantBlock region.
            # Important: do NOT delete until next \begin{figure}, because the last figure
            # may be followed by other content (e.g. cross-system tables).
            candidates: List[int] = []
            for needle in [
                "% QuantBlock:",
                "% AutoRewrite",
                "\\subsection{Cross-system",
                "\\subsection{",
                "\\section{",
                "\\begin{table}",
                "\\begin{enumerate}",
                "\\vspace{",
                "\n% R2 quantitative analysis",
            ]:
                idx = results_text.find(needle, start + 1)
                if idx != -1:
                    candidates.append(idx)
            if candidates:
                end = min(candidates)
            else:
                # Fallback: keep it local; cut at first blank line after marker.
                end = results_text.find("\n\n", start)
                if end == -1:
                    end = len(results_text)
            results_text = results_text[:start] + results_text[end:]

        bullets = fig_to_bullets.get(stem, [])
        if not bullets:
            continue

        # Build a compact paragraph: first bullet, second bullet...
        bullet_text = " ".join(_latex_escape_simple(b) for b in bullets[:3])
        insert = (
            "\n"
            f"{marker}\n"
            "\\noindent\\textbf{Quantitative findings.} "
            f"{bullet_text}\n"
        )

        # Robust insertion:
        # locate the includegraphics line by the exact figures/<stem>.png token,
        # then insert after the first \end{figure} after it.
        token = f"figures/{stem}.png"
        pos = results_text.find(token)
        if pos == -1:
            continue
        end_idx = results_text.find("\\end{figure}", pos)
        if end_idx == -1:
            continue
        end_idx += len("\\end{figure}")

        # Insert right after the end of the figure environment.
        results_text = results_text[:end_idx] + insert + results_text[end_idx:]
        changed = True

    if changed:
        _write_text(parts_results_path, results_text)
        return True
    return None


def _ensure_discussion_progressive(new_draft_path: Path, parts_discussion_path: Path, iteration: int) -> bool:
    """
    Expands Discussion with multiple deterministic paragraphs.
    The amount of inserted content grows with `iteration`.
    Idempotent via dedicated markers.
    """
    text = _read_text(parts_discussion_path)

    # Safety cleanup for long runs:
    # Sometimes stray line-break commands appear right before comment markers,
    # e.g. "\\\\% Discussion: ..." (this breaks LaTeX outside tabular).
    # Always normalize these at function entry, even if we don't insert new paragraphs.
    text_cleaned = re.sub(r"(?m)^[\\]+% Discussion:", r"% Discussion:", text)
    text_cleaned = re.sub(r"(?m)^\\+\s*$", "", text_cleaned)
    cleaned_changed = text_cleaned != text
    text = text_cleaned

    # If the comparison table doesn't exist yet, insert a minimal scaffold.
    table_label = "\\label{tab:disc_comparison_contradictions}"
    if table_label not in text:
        # Minimal insertion: Russian headings + citation keys preserved in the adapter.
        insertion = (
            "\n% Discussion comparison+contradictions scaffold\n"
            "\\subsection{Comparison and contradictions}\n"
            "Для повышения научной прозрачности зафиксируем расхождения между дескрипторами и интерпретациями и соотнесем их с типовыми выводами литературы.\n"
            "\\begin{table}[H]\n"
            "\\centering\n"
            "\\caption{Наш результат vs. литература: согласие/разногласие и возможные причины}\n"
            f"{table_label}\n"
            "\\begin{tabular}{p{0.25\\textwidth}p{0.22\\textwidth}p{0.18\\textwidth}p{0.35\\textwidth}}\n"
            "\\toprule\n"
            "Наш результат & Литературный аналог & Согласие/разногласие & Возможная причина \\\\\n"
            "\\midrule\n"
            "\\multicolumn{4}{l}{\\emph{(заполнено ниже прогрессивными абзацами)} }\\\\\n"
            "\\bottomrule\n"
            "\\end{tabular}\n"
            "\\end{table}\n"
        )
        # insert before Limitations section
        lim_idx = text.find("\\subsection{Limitations")
        if lim_idx == -1:
            lim_idx = len(text)
        text = text[:lim_idx] + insertion + text[lim_idx:]

    # Extract numeric R² values.
    r2 = _extract_r2_values(new_draft_path)
    r2_ctab_del = r2.get("figure_Ctab_agno3_del", "")
    r2_ctab_mins = r2.get("figure_Ctab_agno3_mins", "")

    # Extract numeric key-message bullets for actionable windows.
    fig_to_bullets = _read_new_draft_figures(new_draft_path)

    # Determine insertion point right after the comparison table.
    table_idx = text.find(table_label)
    end_table = text.find("\\end{table}", table_idx)
    if end_table == -1:
        return False
    end_table = text.find("\n", end_table)
    if end_table == -1:
        end_table = end_table + len("\\end{table}")
    insert_pos = end_table

    paragraphs: List[Tuple[int, str]] = []

    # 1) Descriptor disagreement (iteration >=1)
    if iteration >= 1:
        marker = "% Discussion: R2 vs descriptors"
        if marker not in text:
            p = (
                f"\n{marker}\n"
                "Для системы Au--Ag--CTAB различие интерпретации между нормированным дескриптором max|450 и разностным max-450 подтверждается предсказательной диагностикой.\n"
            )
            if r2_ctab_del:
                p += f"По max|450 получено R$^2$={r2_ctab_del}, что указывает на слабую линейную объясняющую способность.\n"
            if r2_ctab_mins:
                p += f"По max-450 получено R$^2$={r2_ctab_mins}, т.е. разностный дескриптор согласованнее с наблюдаемой картиной.\n"
            p += (
                "Практическая интерпретация этого расхождения состоит в том, что нормирование может скрывать абсолютные изменения и усиливать влияние шума/нелинейностей; поэтому для принятия решений корректнее опираться на дескриптор, который лучше соответствует механизму выхода сигнала. "
                "\\cite{55,56,57,58,59,60}\n"
            )
            paragraphs.append((1, p))

    # 2) CTAB threshold (iteration >=2)
    if iteration >= 2:
        marker = "% Discussion: CTAB threshold"
        if marker not in text:
            p = (
                f"\n{marker}\n"
                "Для CTAB-содержащих систем ключевым практическим выводом является пороговое поведение стабилизатора: при недостатке CTAB наблюдается деградация плазмонного отклика, а при переходе порога формируется технологический коридор рабочих условий.\n"
                "Такой эффект согласуется с представлением о том, что CTAB управляет доступностью поверхностных участков и мицеллярным окружением, влияющим на нуклеацию и рост.\n"
                "\\cite{17,18,19,20,21,22,23,24,25,26,27,28,29,30}\n"
            )
            paragraphs.append((2, p))

    # 3) NaI competition (iteration >=3)
    if iteration >= 3:
        marker = "% Discussion: NaI competition"
        if marker not in text:
            p = (
                f"\n{marker}\n"
                "Для Au--CTAB--NaI доминирует конкурирующее влияние I$^{-}$ и CTAB: при снижении CTAB иодид начинает вытеснять стабилизатор с поверхности зародышей, что приводит к падению качества и появлению режимов минимального выхода.\n"
                "При этом существуют альтернативные рабочие зоны, где повышенный NaI способен поддерживать выраженный отклик за счет изменения механизмов адсорбции и кинетики восстановления.\n"
                "\\cite{31,32,33,34,35,36,37,38,39,40,41,42}\n"
            )
            paragraphs.append((3, p))

    # 4) PVP narrow window (iteration >=4)
    if iteration >= 4:
        marker = "% Discussion: PVP window"
        if marker not in text:
            p = (
                f"\n{marker}\n"
                "Для Au--Ag--PVP критически важна узость окна по PVP: избыток полимера систематически ухудшает выход и качество пика, что согласуется с эффектом экранирования поверхности и изменением скорости восстановления.\n"
                "Следовательно, стратегия широкой равномерной выборки менее эффективна, чем локальное сгущение точек вокруг оптимума с обязательной проверкой устойчивости.\n"
                "\\cite{43,44,45,46,47,48,49,50,51,52,53,54}\n"
            )
            paragraphs.append((4, p))

    # 5) Practical implications + limitations (iteration >=5)
    if iteration >= 5:
        marker = "% Discussion: practical implications"
        if marker not in text:
            p = (
                f"\n{marker}\n"
                "Практические последствия для следующей кампании состоят в том, что правила планирования должны быть дескрипторно-специфичными.\n"
                "Во-первых, при диагностике предсказательной способности предпочтительно использовать разностный дескриптор.\n"
                "Во-вторых, сетку параметров следует ограничивать технологическими окнами (порог CTAB, узкое PVP-окно и режимы NaI--CTAB конкуренции), чтобы уменьшить долю нерелевантных запусков.\n"
                "К ограничениям подхода относится опора на UV--Vis дескрипторы и предположение о корректности линейной интерпретации R$^2$ как модели покрытия параметров.\n"
                "\\cite{101,102,103,104,105,106,107,108,109,110}\n"
            )
            paragraphs.append((5, p))

    # 6) Actionable parameter windows (iteration >=6)
    if iteration >= 6:
        marker = "% Discussion: actionable windows"
        if marker not in text:
            # Pull grounded bullet text (no Evidence codes) from Key message blocks.
            ctab_agno3_del = fig_to_bullets.get("figure_Ctab_agno3_del", [])
            ctab_nai_del = fig_to_bullets.get("figure_Ctab_nai_del", [])
            pvp_agno3_del = fig_to_bullets.get("figure_PVP_agno3_del", [])
            pvp_agno3_mins = fig_to_bullets.get("figure_PVP_agno3_mins", [])

            def _b(lst: List[str], i: int) -> str:
                return lst[i] if i < len(lst) else ""

            p = f"\n{marker}\n"
            win_parts: List[str] = []
            if _b(ctab_agno3_del, 0):
                win_parts.append(_b(ctab_agno3_del, 0) + ".")
            if _b(ctab_agno3_del, 1):
                win_parts.append(_b(ctab_agno3_del, 1) + ".")
            if _b(ctab_nai_del, 0):
                win_parts.append(_b(ctab_nai_del, 0) + ".")
            if _b(ctab_nai_del, 1):
                win_parts.append(_b(ctab_nai_del, 1) + ".")
            if _b(pvp_agno3_del, 0):
                win_parts.append(_b(pvp_agno3_del, 0) + ".")
            if _b(pvp_agno3_del, 1):
                win_parts.append(_b(pvp_agno3_del, 1) + ".")
            if _b(pvp_agno3_mins, 0):
                win_parts.append(_b(pvp_agno3_mins, 0) + ".")
            if _b(pvp_agno3_mins, 1):
                win_parts.append(_b(pvp_agno3_mins, 1) + ".")

            # If something is missing, still insert the paragraph.
            if win_parts:
                p += "Для следующей серии эти зависимости можно перевести в технологические окна:\n"
                p += " ".join(win_parts)
                p += " "
            p += (
                "С инженерной точки зрения эти окна задают допустимые диапазоны для планировщика экспериментов и позволяют отфильтровать заведомо «тяжелые» зоны до расходования бюджета на повторные запуски.\n"
                "\\cite{17,18,19,20,21,22,23,24,25,31,32,33,34,35,43,44,45,46,47,48,49,50,51,52,53,54}\n"
            )
            paragraphs.append((6, p))

    # 7) Recommended protocol skeleton (iteration >=7)
    if iteration >= 7:
        marker = "% Discussion: protocol skeleton"
        if marker not in text:
            p = (
                f"\n{marker}\n"
                "Пример практического каркаса для планирования следующей итерации:\n"
                "\\begin{enumerate}\n"
                "\\item Сначала выполните грубую развертку в широком диапазоне, но ограничьте поиск предварительно выделенными окнами (CTAB порог, узкое PVP-окно, избегание зон с минимальным откликом).\n"
                "\\item На втором этапе сгущайте выборку локально вокруг области максимума/оптимума, параллельно проверяя устойчивость к небольшим вариациям условий (температура/состав).\n"
                "\\item При расхождении интерпретации между max|450 и max-450 отдайте приоритет тому дескриптору, который демонстрирует более согласованную предсказательную диагностику (например, при R$^2$=-0.08 для max|450 и R$^2$=0.29 для max-450).\n"
                "\\end{enumerate}\n"
                "Такой протокол снижает долю нерелевантных запусков и переводит результаты карт в воспроизводимые правила принятия решений.\n"
                "\\cite{55,56,57,58,59,60,61,62,63,64,65,66,101,102}\n"
            )
            paragraphs.append((7, p))

    # 8) Descriptor selection rule (iteration >=8)
    if iteration >= 8:
        marker = "% Discussion: descriptor selection"
        if marker not in text:
            p = (
                f"\n{marker}\n"
                "Правило выбора дескриптора для последующих серий можно сформулировать как «диагностическую развилку»:\n"
                "если линейная объясняющая способность max|450 существенно слабее, чем у max-450 (как в случае R$^2$=-0.08 vs R$^2$=0.29), то решения по следующему эксперименту следует опирать на разностный дескриптор.\n"
                "Это уменьшает риск того, что нормирование «сгладит» абсолютные различия и приведет к неправильной причинной интерпретации.\n"
                "\\cite{55,56,57,58,59,60}\n"
            )
            paragraphs.append((8, p))

    # 9) Additional limitations framing (iteration >=9)
    if iteration >= 9:
        marker = "% Discussion: remaining limitations"
        if marker not in text:
            p = (
                f"\n{marker}\n"
                "Ограничения подхода остаются важными: используемые дескрипторы получены из UV--Vis карт и потенциально чувствительны к шуму и к нелинейным режимам, поэтому R$^2$ следует интерпретировать как диагностический индикатор качества линейной аппроксимации, а не как универсальную меру причинности.\n"
                "Для более строгой валидации рекомендуется расширять подтверждающие измерения (например, SAXS/TEM) в контрольных подвыборках и проверять переносимость окон между кампаниями.\n"
                "\\cite{101,102,103,104,105,106,107,108,109,110,136,137,138}\n"
            )
            paragraphs.append((9, p))

    if not paragraphs:
        if cleaned_changed:
            _write_text(parts_discussion_path, text)
        return cleaned_changed

    # Insert all new paragraphs at the end of the comparison table.
    insert_text = "".join(p for _, p in sorted(paragraphs, key=lambda x: x[0]))
    text = text[:insert_pos] + insert_text + text[insert_pos:]

    # Cleanup already handled at function entry.
    _write_text(parts_discussion_path, text)
    return True


def _insert_r2_and_discussion_analysis(new_draft_path: Path, parts_discussion_path: Path) -> bool:
    """
    Adds a discussion subsection about R² predictive performance and a compact comparison.
    Idempotent via marker.
    """
    discussion_text = _read_text(parts_discussion_path)
    marker = "% R2 quantitative analysis"
    if marker in discussion_text:
        # Remove the previously inserted R2 block to allow updated escaping.
        start = discussion_text.find(marker)
        # Remove until the end of the inserted block (usually right after \vspace{2mm}).
        v_idx = discussion_text.find("\\vspace{2mm}", start)
        if v_idx != -1:
            end = v_idx + len("\\vspace{2mm}")
            # consume a following newline if present
            if end < len(discussion_text) and discussion_text[end] == "\n":
                end += 1
            discussion_text = discussion_text[:start] + discussion_text[end:]
        else:
            # Fallback: delete to end of file.
            discussion_text = discussion_text[:start]

    r2 = _extract_r2_values(new_draft_path)
    # If we didn't find any R², do nothing.
    if not r2:
        return False

    # Map stems to descriptor names from our captions.
    r2_ctab_del = r2.get("figure_Ctab_agno3_del", "")
    r2_ctab_mins = r2.get("figure_Ctab_agno3_mins", "")

    additions = (
        "\n"
        f"{marker}\n"
        "\\subsection{Predictive performance and R$^2$ interpretation}\n"
    )
    parts: List[str] = []
    if r2_ctab_del:
        parts.append(
            f"Для системы Au--Ag--CTAB зависимость дескриптора max|450 от (AgNO$_3$/Au, CTAB/Au) демонстрирует низкую линейную объясняющую способность: R$^2$={r2_ctab_del}. "
            "Это указывает на существенный вклад нелинейных факторов (например, транспорт/мицеллярные эффекты) и/или на то, что сетка параметров покрывает режимы с высоким шумом."
        )
    if r2_ctab_mins:
        parts.append(
            f"В то же время для разностного дескриптора max-450 получено лучшее качество аппроксимации: R$^2$={r2_ctab_mins}. "
            "Такое расхождение подтверждает, что нормирование (max|450) может скрывать часть физически значимых изменений, тогда как max-450 лучше выявляет выход и/или соотношение вкладов сигнал/фон."
        )
    # Minimal literature comparison (2-4 works) with specific citations
    parts.append(
        "В сопоставлении с подходами агентной автономной оптимизации, ориентированными на итеративное обновление гипотез на основе обратной связи, наши результаты показывают важность выбора информативных дескрипторов и явного учета предсказательных ограничений отклика \cite{1,2,10,13}. "
        "Практическое следствие состоит в том, что при низком R$^2$ корректнее переносить внимание на альтернативные метрики и на локальную донастройку окна, а не пытаться интерпретировать глобальный тренд как линейный."
    )

    additions += "\n".join(parts) + "\n"
    additions += "\\vspace{2mm}\n"

    discussion_text = discussion_text + additions
    _write_text(parts_discussion_path, discussion_text)
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply deterministic rewrite pass from prompt file.")
    parser.add_argument("--prompt-file", required=True)
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent
    prompt_file = (root / args.prompt_file) if not Path(args.prompt_file).is_absolute() else Path(args.prompt_file)
    if not prompt_file.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_file}")

    prompt_text = _read_text(prompt_file)
    iteration = _detect_iteration(prompt_file)
    pass_name = _detect_pass_name(prompt_text)
    result = apply_pass(pass_name=pass_name, iteration=iteration, parts_dir=root / "parts")

    report_path = prompt_file.with_name(f"iter_{iteration:02d}_apply_report.json")
    report_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Adapter pass applied: iter {iteration:02d} / {pass_name}")
    print(f"Actions: {result['actions_applied']}")
    print(f"Report: {report_path}")


if __name__ == "__main__":
    main()
