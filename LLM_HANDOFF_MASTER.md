# LLM Handoff Master — PaperWriter Pipeline

This file is the single source of instructions for an LLM agent to understand this project and run it end-to-end.
If you upload only one instruction file plus `scripts/`, upload this file.

---

## 1) Project Purpose

PaperWriter is an automated scientific-article generation and polishing pipeline (LaTeX + BibTeX) with:
- draft ingestion (`.docx`/`.md`/`.tei`),
- iterative rewriting,
- citation/evidence validation,
- consistency and quality gates,
- publication-ready PDF build.

Primary goal: produce `out/base_final.pdf` (and timestamped snapshot) that passes strict quality checks.

---

## 2) Core Inputs and Outputs

## Inputs (expected)
- `project_info.yaml` — metadata (title, authors, abstract, language, journal scope)
- `PROJECT.md` — section skeleton / TOC
- `EVIDENCE.md` — verified factual claims (SSOT)
- `src/paper_data/new_draft.docx` (preferred) or `src/paper_data/new_draft.md`
- `refs/bib/references.bib`
- figures in `figures/` (or paths referenced from manuscript)

## Key Outputs
- `out/Report_Final.pdf`
- `out/base_final.pdf`
- `out/base_final_YYYY-MM-DD_HH-MM.pdf`
- validation and workflow reports in `out/`

---

## 3) What Each Main Script Does

- `scripts/run_agent_workflow.py`  
  Main orchestrator for iterative generation/rewrite cycle.

- `scripts/build_base_final.py`  
  One-command quality gate pipeline: workflow + cleanup + validation + build + base_final artifacts.

- `scripts/rewrite_adapter.py`  
  Deterministic rewrite applicator (section shaping, figure/text enrichment, discussion progression).

- `scripts/iterative_rewriter.py`  
  Generates iterative critic/reviser prompt passes.

- `scripts/convert_docx_sources.py`  
  Converts DOCX to `new_draft.md` + `new_draft.tei`.

- `scripts/parse_draft_semantic.py`  
  Extracts structured semantics from draft, references, fact markers.

- `scripts/contextual_citation_router.py`  
  Suggests citations by section context.

- `scripts/prepare_output_mode.py`  
  Switches publication/internal output variants.

- `scripts/elaborate_figure_descriptions.py`  
  Adds post-pass figure interpretation blocks (caption elaboration layer).

### Validators / Quality Gates
- `scripts/validate_citations.py`
- `scripts/validate_facts.py`
- `scripts/validate_consistency.py`
- `scripts/validate_assets.py`
- `scripts/validate_bib_quality.py`
- `scripts/validate_language.py`
- `scripts/validate_no_instructions.py`
- `scripts/validate_text_artifacts.py`
- `scripts/validate_quantitative_content.py`
- `scripts/validate_idempotence.py`

### Cleanup / Sanitization
- `scripts/sanitize_discussion.py`
- `scripts/cleanup_publication_artifacts.py`
- `scripts/cleanup_text_artifacts.py`
- `scripts/cleanup_citations_by_bib_quality.py`

---

## 4) Canonical Execution Commands

## Recommended full run (strict publication)
```bash
python3 scripts/build_base_final.py \
  --iterations 20 \
  --docx-path src/paper_data/new_draft.docx \
  --output-mode publication \
  --strict-gates
```

## If bibliography is broad/dirty and should not be aggressively pruned
```bash
python3 scripts/build_base_final.py \
  --iterations 20 \
  --docx-path src/paper_data/new_draft.docx \
  --output-mode publication \
  --strict-gates \
  --soft-literature
```

## Long rewrite mode
```bash
python3 scripts/build_base_final.py \
  --iterations 50 \
  --docx-path src/paper_data/new_draft.docx \
  --output-mode publication \
  --strict-gates \
  --soft-literature
```

---

## 5) Mandatory Agent Behavior

1. Work autonomously: do not ask user to run commands manually.
2. Do not stop at analysis — run full pipeline and validations.
3. Keep publication output in one language (default: English unless user requests otherwise).
4. Never invent facts, numeric values, or references.
5. Preserve consistency: claims in Introduction/Discussion/Conclusion must not contradict Results/Methods.
6. Ensure all figures referenced by `\includegraphics` exist.
7. Ensure all cited BibTeX keys resolve and cited entries are complete enough for publication.
8. Remove generator/meta artifacts from final manuscript text.
9. Keep process idempotent: reruns must not duplicate injected blocks.

---

## 6) Final Success Criteria (Definition of Done)

A run is successful only if:
- all required validators pass (strict mode where requested),
- `make` succeeds,
- `out/Report_Final.pdf` is non-empty,
- `out/base_final.pdf` is updated,
- timestamped `out/base_final_YYYY-MM-DD_HH-MM.pdf` exists.

---

## 7) Practical Minimal Handoff for Another LLM

If sharing to another user/agent, provide:
1. this file (`LLM_HANDOFF_MASTER.md`),
2. folder `scripts/`,
3. root config files (`project_info.yaml`, `PROJECT.md`, `EVIDENCE.md`, `main.tex`, `structure.tex`, `Makefile`),
4. `refs/bib/references.bib`,
5. user draft in `src/paper_data/new_draft.docx`.

This is enough for full autonomous operation.

---

## 8) Suggested Agent Prompt (copy-paste)

```text
Read LLM_HANDOFF_MASTER.md and execute the full publication pipeline autonomously.
Use src/paper_data/new_draft.docx as primary draft input.
Run strict quality gates, ensure figure integrity, bibliography hygiene, consistency, and language uniformity.
Polish manuscript for publication quality, then build PDF and update out/base_final.pdf plus timestamped snapshot.
Return a concise report: changed files, validation results, build status, and residual risks.
```

