#!/usr/bin/env python3
r"""
validate_citations.py — проверка ссылок \cite{...} в .tex файлах на соответствие ключам из .bib.

Использование:
    validate_citations.py [--bib BIBFILE] [--tex-dir TEXDIR] [--output-errors FILE] [--suggest] [--verbose]
"""

import re
import sys
import argparse
import json
from pathlib import Path
from difflib import get_close_matches
from collections import defaultdict

def extract_bib_keys(bib_path):
    """Извлекает все ключи из .bib файла."""
    bib_path = Path(bib_path)
    if not bib_path.exists():
        sys.stderr.write(f"ERROR: Bib file not found: {bib_path}\n")
        return set()
    
    with open(bib_path, 'r', encoding='utf-8') as f:
        content = f.read()
    # Ищем строки типа @article{Key123, или @book{Key123,
    keys = re.findall(r'@\w+\{([^,]+),', content)
    return set(keys)

def extract_cite_keys(tex_path):
    r"""Извлекает все ключи из \cite{...} в .tex файле."""
    with open(tex_path, 'r', encoding='utf-8') as f:
        content = f.read()
    # \cite{key1,key2} или \cite{key}
    # Поддерживаем также \citep{}, \citet{} (для стилей natbib)
    matches = re.findall(r'\\(?:cite|citep|citet)\{([^}]+)\}', content)
    keys = []
    for group in matches:
        for k in group.split(','):
            k = k.strip()
            if k:
                keys.append(k)
    return set(keys)

def find_tex_files(tex_dir):
    """Рекурсивно ищет все .tex файлы в директории."""
    tex_dir = Path(tex_dir)
    if not tex_dir.exists():
        sys.stderr.write(f"ERROR: Directory not found: {tex_dir}\n")
        return []
    return list(tex_dir.glob('**/*.tex'))

def fuzzy_match(missing_key, available_keys, cutoff=0.8):
    """Предлагает близкие ключи из списка."""
    matches = get_close_matches(missing_key, available_keys, n=3, cutoff=cutoff)
    return matches

def check_citations(tex_files, bib_keys, suggest=False, cutoff=0.8):
    """
    Проверяет все .tex файлы на наличие несуществующих ключей.
    Возвращает dict: {tex_file: {missing_key: [line_numbers, suggestions]}}.
    Также собирает статистику по использованию.
    """
    errors = defaultdict(lambda: defaultdict(list))
    if suggest:
        suggestions = defaultdict(lambda: defaultdict(list))
    
    for tex_file in tex_files:
        with open(tex_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # Ищем \cite{...} с номерами строк
        for line_num, line in enumerate(lines, 1):
            # Находим все вхождения \cite{...}
            for match in re.finditer(r'\\(?:cite|citep|citet)\{([^}]+)\}', line):
                keys_str = match.group(1)
                for key in keys_str.split(','):
                    key = key.strip()
                    if key and key not in bib_keys:
                        errors[tex_file][key].append(line_num)
                        if suggest:
                            sugg = fuzzy_match(key, bib_keys, cutoff)
                            if sugg:
                                suggestions[tex_file][key].extend(sugg)
    
    if suggest:
        return errors, suggestions
    else:
        return errors

def generate_report(errors, suggestions=None, verbose=False):
    """
    Печатает отчёт об ошибках в читаемом формате.
    Возвращает True, если есть ошибки, иначе False.
    """
    if not errors:
        print("OK: All citations are valid.")
        return False
    
    print("ERROR: Invalid citations found:")
    for tex_file, missing in errors.items():
        print(f"\n  File: {tex_file}")
        for key, lines in missing.items():
            lines_str = ', '.join(str(l) for l in lines)
            if suggestions and tex_file in suggestions and key in suggestions[tex_file]:
                sugg_str = ', '.join(suggestions[tex_file][key])
                print(f"    - {key} (lines {lines_str}) -> suggestions: {sugg_str}")
            else:
                print(f"    - {key} (lines {lines_str})")
    
    # Если verbose, вывести статистику
    if verbose:
        total_errors = sum(len(missing) for missing in errors.values())
        print(f"\nTotal invalid citations: {total_errors}")
    return True

def save_error_report(errors, suggestions, output_file):
    """Сохраняет отчёт в JSON для дальнейшей обработки."""
    data = {
        "errors": {},
        "suggestions": {}
    }
    for tex_file, missing in errors.items():
        data["errors"][str(tex_file)] = {k: lines for k, lines in missing.items()}
    if suggestions:
        for tex_file, sugg_dict in suggestions.items():
            data["suggestions"][str(tex_file)] = {k: list(v) for k, v in sugg_dict.items()}
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def main():
    parser = argparse.ArgumentParser(description="Validate LaTeX citations against a BibTeX file.")
    parser.add_argument('--bib', default='refs/bib/references.bib',
                        help='Path to BibTeX file (default: refs/bib/references.bib)')
    parser.add_argument('--tex-dir', default='parts',
                        help='Directory containing .tex files (default: parts)')
    parser.add_argument('--output-errors', help='Save error report to this file (JSON)')
    parser.add_argument('--suggest', action='store_true', help='Suggest replacements for invalid keys')
    parser.add_argument('--verbose', action='store_true', help='Verbose output')
    parser.add_argument('--cutoff', type=float, default=0.8,
                        help='Similarity cutoff for suggestions (0.0-1.0, default 0.8)')
    args = parser.parse_args()
    
    bib_keys = extract_bib_keys(args.bib)
    if not bib_keys:
        sys.stderr.write("Warning: No keys found in BibTeX file.\n")
    
    tex_files = find_tex_files(args.tex_dir)
    if not tex_files:
        sys.stderr.write(f"Warning: No .tex files found in {args.tex_dir}\n")
    
    errors = check_citations(tex_files, bib_keys, suggest=args.suggest, cutoff=args.cutoff)
    if args.suggest:
        errors, suggestions = errors
    else:
        suggestions = None
    
    has_errors = generate_report(errors, suggestions, args.verbose)
    
    if args.output_errors and has_errors:
        save_error_report(errors, suggestions or {}, args.output_errors)
    
    sys.exit(1 if has_errors else 0)

if __name__ == "__main__":
    main()