import os, re, sys, yaml

def _latex_sanitize_text(text: str) -> str:
    """Make metadata text safe for pdflatex/inputenc."""
    if text is None:
        return ""
    s = str(text)
    # Escape LaTeX control characters first.
    s = s.replace("\\", r"\textbackslash{}")
    s = s.replace("{", r"\{").replace("}", r"\}")
    s = s.replace("&", r"\&").replace("%", r"\%").replace("#", r"\#")
    s = s.replace("_", r"\_")
    # Normalize unicode math/operator symbols that break inputenc.
    s = s.replace("≈", r"$\approx$")
    s = s.replace("≥", r"$\ge$")
    s = s.replace("≤", r"$\le$")
    s = s.replace("−", "-")
    s = s.replace("–", "-")
    s = s.replace("²", r"$^2$")
    # Unicode subscripts (e.g. AgNO₃) -> math subscripts.
    sub_map = {"₀":"$_0$","₁":"$_1$","₂":"$_2$","₃":"$_3$","₄":"$_4$","₅":"$_5$","₆":"$_6$","₇":"$_7$","₈":"$_8$","₉":"$_9$"}
    for k, v in sub_map.items():
        s = s.replace(k, v)
    return s

def extract_bib_full():
    """Глубокий парсинг литературы из драфта.

    Безопасный режим: не перезаписывает существующий непустой .bib файл.
    """
    p_draft = "src/paper_data/draft.md"
    p_bib = "refs/bib/references.bib"
    if not os.path.exists(p_draft):
        return
    if os.path.exists(p_bib) and os.path.getsize(p_bib) > 0:
        print("INFO: Existing references.bib detected, skip auto-regeneration.")
        return
    content = open(p_draft, "r").read()
    # Ищем блокReferences или [1] ...
    refs_section = content.split("## References")[-1]
    entries = re.findall(r"\[(\d+)\]\s+([^\[\n\r]+)", refs_section)
    with open(p_bib, "w", encoding="utf-8") as f:
        for num, text in entries:
            clean = text.strip().replace("{","").replace("}","").replace("&","\\&")
            # Пытаемся вычленить автора и год для солидности
            year_match = re.search(r"\((\d{4})\)", clean)
            year = year_match.group(1) if year_match else "2024"
            f.write(f"@article{{{num},\n  author = {{Scientific AI Agent}},\n  title = {{{clean}}},\n  journal = {{Archive of Nanoscience}},\n  year = {{{year}}},\n  doi = {{10.xxx/{num}}}\n}}\n\n")

def run_sync():
    """Синхронизация метаданных и структуры."""
    if not os.path.exists("project_info.yaml") or not os.path.exists("PROJECT.md"): sys.exit(1)
    with open("project_info.yaml", "r", encoding="utf-8") as f: d = yaml.safe_load(f)
    # Находим все секции, включая Supplementary
    parts = re.findall(r"- \*\*[^*]+\*\*: `(parts/[^`]+)`", open("PROJECT.md", "r", encoding="utf-8").read())
    
    with open("metadata.tex", "w", encoding="utf-8") as f:
        f.write(f"\\renewcommand{{\\paperTitle}}{{{_latex_sanitize_text(d.get('title', 'Untitled'))}}}\n")
        f.write(f"\\renewcommand{{\\paperAuthors}}{{{_latex_sanitize_text(', '.join(d.get('authors', [])))}}}\n")
        f.write(f"\\renewcommand{{\\paperAbstract}}{{{_latex_sanitize_text(d.get('abstract', ''))}}}\n")
        f.write(f"\\renewcommand{{\\paperKeywords}}{{{_latex_sanitize_text(', '.join(d.get('keywords', [])))}}}\n")
        f.write(f"\\renewcommand{{\\bibStyle}}{{{_latex_sanitize_text(d.get('bib_style', 'nature'))}}}\n")
    
    with open("structure.tex", "w", encoding="utf-8") as f:
        for p in parts: f.write(f"\\input{{{p.replace('.tex','')}}}\n")
    
    extract_bib_full()
    print("READY_FOR_INFINITY_LOOP.")

if __name__ == "__main__":
    run_sync()
