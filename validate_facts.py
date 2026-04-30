#!/usr/bin/env python3
"""
validate_facts.py — проверка фактов, используемых в LaTeX-документе,
                   на соответствие кодам из EVIDENCE.md.

Использование:
    validate_facts.py [--evidence EVIDENCE.md] [--tex-dir parts] [--output-errors FILE]
                      [--check-usage] [--suggest] [--verbose]

Пример:
    validate_facts.py --suggest
    if [ $? -ne 0 ]; then
        echo "Неверные коды фактов, исправьте!"
        exit 1
    fi
"""

import re
import sys
import argparse
import json
from pathlib import Path
from difflib import get_close_matches
from collections import defaultdict

def extract_evidence_codes(evidence_path):
    """Извлекает все коды вида [E-...] из EVIDENCE.md."""
    evidence_path = Path(evidence_path)
    if not evidence_path.exists():
        sys.stderr.write(f"ERROR: Evidence file not found: {evidence_path}\n")
        return set()
    
    with open(evidence_path, 'r', encoding='utf-8') as f:
        content = f.read()
    # Ищем [E-...], где E- может быть любым префиксом (E-M, E-H, E-R, E-D)
    # но для простоты ищем [E-...]
    codes = re.findall(r'\[(E-[A-Z0-9]+)\]', content)
    return set(codes)

def extract_source_comments(tex_path):
    """Извлекает коды фактов из файла.

    Поддерживаемые форматы:
    - % Source: [E-...]
    - inline: [E-...] (например, \textbf{[E-R1]})
    """
    with open(tex_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    sources = defaultdict(list)
    for line_num, line in enumerate(lines, 1):
        # 1) Ищем % Source: [E-...]
        source_match = re.search(r'% Source:\s*\[(E-[A-Z0-9]+)\]', line)
        if source_match:
            code = source_match.group(1)
            sources[code].append(line_num)

        # 2) Ищем inline-коды [E-...]
        inline_matches = re.findall(r'\[(E-[A-Z0-9]+)\]', line)
        for code in inline_matches:
            sources[code].append(line_num)
    return sources

def find_tex_files(tex_dir):
    """Рекурсивно ищет все .tex файлы в директории."""
    tex_dir = Path(tex_dir)
    if not tex_dir.exists():
        sys.stderr.write(f"ERROR: Directory not found: {tex_dir}\n")
        return []
    return list(tex_dir.glob('**/*.tex'))

def fuzzy_match(code, available_codes, cutoff=0.8):
    """Предлагает близкие коды из доступных."""
    matches = get_close_matches(code, available_codes, n=3, cutoff=cutoff)
    return matches

def validate_facts(tex_files, evidence_codes, suggest=False, cutoff=0.8):
    """Проверяет, что все используемые коды есть в evidence_codes.
       Возвращает:
         - errors: dict {tex_file: {code: [line_numbers]}}
         - usage: dict {code: count_of_uses}
         - suggestions: dict {tex_file: {code: [suggestions]}} (если suggest=True)
    """
    errors = defaultdict(lambda: defaultdict(list))
    usage = defaultdict(int)
    if suggest:
        suggestions = defaultdict(lambda: defaultdict(list))
    
    for tex_file in tex_files:
        sources = extract_source_comments(tex_file)
        for code, lines in sources.items():
            usage[code] += len(lines)
            if code not in evidence_codes:
                errors[tex_file][code] = lines
                if suggest:
                    sugg = fuzzy_match(code, evidence_codes, cutoff)
                    if sugg:
                        suggestions[tex_file][code] = sugg
    
    if suggest:
        return errors, usage, suggestions
    else:
        return errors, usage

def generate_report(errors, usage, evidence_codes, suggestions=None, check_usage=False, verbose=False):
    """
    Печатает отчёт об ошибках.
    Возвращает True, если есть ошибки.
    """
    has_errors = bool(errors)
    if has_errors:
        print("ERROR: Invalid fact codes found:")
        for tex_file, missing in errors.items():
            print(f"\n  File: {tex_file}")
            for code, lines in missing.items():
                lines_str = ', '.join(str(l) for l in lines)
                if suggestions and tex_file in suggestions and code in suggestions[tex_file]:
                    sugg_str = ', '.join(suggestions[tex_file][code])
                    print(f"    - {code} (lines {lines_str}) -> suggestions: {sugg_str}")
                else:
                    print(f"    - {code} (lines {lines_str})")
    else:
        print("OK: All fact codes are valid.")
    
    # Если check_usage, покажем, какие коды не использованы
    if check_usage:
        unused = evidence_codes - usage.keys()
        if unused:
            print("\nWarning: The following codes from EVIDENCE.md are never used:")
            for code in sorted(unused):
                print(f"    - {code}")
    
    if verbose:
        print(f"\nTotal fact code occurrences: {sum(usage.values())}")
        print(f"Unique codes used: {len(usage)}")
    
    return has_errors

def save_error_report(errors, suggestions, usage, output_file):
    """Сохраняет отчёт в JSON."""
    data = {
        "errors": {},
        "suggestions": {},
        "usage": usage
    }
    for tex_file, missing in errors.items():
        data["errors"][str(tex_file)] = {k: lines for k, lines in missing.items()}
    if suggestions:
        for tex_file, sugg_dict in suggestions.items():
            data["suggestions"][str(tex_file)] = {k: list(v) for k, v in sugg_dict.items()}
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def main():
    parser = argparse.ArgumentParser(description="Validate facts used in LaTeX against EVIDENCE.md.")
    parser.add_argument('--evidence', default='EVIDENCE.md',
                        help='Path to EVIDENCE.md (default: EVIDENCE.md)')
    parser.add_argument('--tex-dir', default='parts',
                        help='Directory containing .tex files (default: parts)')
    parser.add_argument('--output-errors', help='Save error report to this file (JSON)')
    parser.add_argument('--check-usage', action='store_true',
                        help='Check which codes from EVIDENCE.md are never used')
    parser.add_argument('--suggest', action='store_true',
                        help='Suggest replacements for invalid codes')
    parser.add_argument('--verbose', action='store_true', help='Verbose output')
    parser.add_argument('--cutoff', type=float, default=0.8,
                        help='Similarity cutoff for suggestions (0.0-1.0, default 0.8)')
    args = parser.parse_args()
    
    evidence_codes = extract_evidence_codes(args.evidence)
    if not evidence_codes:
        sys.stderr.write("Warning: No codes found in EVIDENCE.md.\n")
    
    tex_files = find_tex_files(args.tex_dir)
    if not tex_files:
        sys.stderr.write(f"Warning: No .tex files found in {args.tex_dir}\n")
    
    if args.suggest:
        errors, usage, suggestions = validate_facts(tex_files, evidence_codes,
                                                    suggest=True, cutoff=args.cutoff)
    else:
        errors, usage = validate_facts(tex_files, evidence_codes,
                                       suggest=False, cutoff=args.cutoff)
        suggestions = None
    
    has_errors = generate_report(errors, usage, evidence_codes, suggestions,
                                  check_usage=args.check_usage, verbose=args.verbose)
    
    if args.output_errors and has_errors:
        save_error_report(errors, suggestions, usage, args.output_errors)
    
    sys.exit(1 if has_errors else 0)

if __name__ == "__main__":
    main()