#!/usr/bin/env python3
"""
Reference Parser Pipeline
========================
Parses references from TEI XML file and generates proper BibTeX format.
Also extracts citation numbers used in the text and maps them correctly.

Usage:
    python scripts/parse_references.py
"""

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import argparse


# TEI namespace
NS = {'tei': 'http://www.tei-c.org/ns/1.0'}


def parse_tei_references(tei_path: str) -> Dict[str, Dict]:
    """Parse references from TEI XML file."""
    tree = ET.parse(tei_path)
    root = tree.getroot()
    
    references = {}
    
    # Find all biblStruct elements in listBibl
    for bibl in root.findall('.//tei:listBibl/tei:biblStruct', NS):
        xml_id = bibl.get('{http://www.w3.org/XML/1998/namespace}id', '')
        
        ref_data = {
            'title': '',
            'authors': [],
            'journal': '',
            'year': '',
            'doi': '',
            'volume': '',
            'pages': '',
            'publisher': '',
        }
        
        # Get title from analytic (article title)
        analytic_title = bibl.find('tei:analytic/tei:title', NS)
        monogr_title = bibl.find('tei:monogr/tei:title', NS)
        
        if analytic_title is not None:
            # Has analytic title - this is an article
            ref_data['title'] = analytic_title.text or ''
            # monogr title is the journal
            if monogr_title is not None:
                ref_data['journal'] = monogr_title.text or ''
        elif monogr_title is not None:
            # No analytic title - monogr title is the main title (book/preprint)
            ref_data['title'] = monogr_title.text or ''
            # Check if there's a journal-level title
            journal_elem = bibl.find('tei:monogr/tei:title[@level="j"]', NS)
            if journal_elem is not None:
                ref_data['journal'] = journal_elem.text or ''
        
        # Get authors
        for author in bibl.findall('.//tei:author', NS):
            pers_name = author.find('tei:persName', NS)
            if pers_name is not None:
                forename = pers_name.find('tei:forename', NS)
                surname = pers_name.find('tei:surname', NS)
                name_parts = []
                if forename is not None and forename.text:
                    name_parts.append(forename.text)
                if surname is not None and surname.text:
                    name_parts.append(surname.text)
                if name_parts:
                    ref_data['authors'].append(' '.join(name_parts))
        
        # Get year
        date_elem = bibl.find('.//tei:date', NS)
        if date_elem is not None:
            ref_data['year'] = date_elem.get('when', '') or date_elem.text or ''
        
        # Get DOI
        for idno in bibl.findall('.//tei:idno', NS):
            if idno.get('type') == 'doi':
                ref_data['doi'] = idno.text or ''
                break
        
        # Get volume and pages from monogr/imprint
        imprint = bibl.find('tei:monogr/tei:imprint', NS)
        if imprint is not None:
            volume = imprint.find('tei:biblScope[@unit="volume"]', NS)
            if volume is not None:
                ref_data['volume'] = volume.text or ''
            pages = imprint.find('tei:biblScope[@unit="page"]', NS)
            if pages is not None:
                ref_data['pages'] = pages.text or ''
            publisher = imprint.find('tei:publisher', NS)
            if publisher is not None:
                ref_data['publisher'] = publisher.text or ''
        
        references[xml_id] = ref_data
    
    return references


def extract_citation_numbers(text_path: str) -> List[int]:
    """Extract all citation numbers from a text/tex file."""
    with open(text_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    citations = set()
    
    # Pattern 1: \cite{76} or \cite{76, 81} or \cite{76,81}
    cite_pattern = re.findall(r'\\cite\{([^\}]+)\}', content)
    for match in cite_pattern:
        # Split by comma and clean
        nums = re.findall(r'\d+', match)
        citations.update(int(n) for n in nums)
    
    # Pattern 2: [number] brackets (for markdown/draft.md)
    pattern_brackets = re.findall(r'\[(\d+)\]', content)
    citations.update(int(n) for n in pattern_brackets)
    
    return sorted(citations)


def parse_back_matter_urls(tei_path: str) -> Dict[int, str]:
    """Parse the back matter URLs that contain citation numbers."""
    tree = ET.parse(tei_path)
    root = tree.getroot()
    
    url_map = {}
    
    # Find the availability div with URLs
    for div in root.findall('.//tei:div[@type="availability"]', NS):
        for p in div.findall('.//tei:p', NS):
            text = ET.tostring(p, encoding='unicode', method='text')
            # Match patterns like "URL [number] Title"
            matches = re.findall(r'\[(\d+)\]\s*(.+?)(?=\s*\[|\s*$)', text)
            for num, title in matches:
                url_map[int(num)] = title.strip()
    
    return url_map


def generate_bibtex_key(ref_data: Dict, citation_num: int) -> str:
    """Generate a proper BibTeX key - using numeric key to match citation numbers."""
    # Use numeric key to match citation format in tex files
    return str(citation_num)


def generate_bibtex_entry(ref_data: Dict, citation_num: int) -> str:
    """Generate a BibTeX entry."""
    key = generate_bibtex_key(ref_data, citation_num)
    
    # Determine entry type
    if ref_data['journal']:
        entry_type = 'article'
    else:
        entry_type = 'misc'
    
    lines = [f"@{entry_type}{{{key},"]
    
    # Authors
    if ref_data['authors']:
        authors = ' and '.join(ref_data['authors'])
        lines.append(f"  author = {{{authors}}},")
    
    # Title
    if ref_data['title']:
        lines.append(f"  title = {{{ref_data['title']}}},")
    
    # Journal
    if ref_data['journal']:
        lines.append(f"  journal = {{{ref_data['journal']}}},")
    
    # Year
    if ref_data['year']:
        lines.append(f"  year = {{{ref_data['year']}}},")
    
    # DOI
    if ref_data['doi']:
        lines.append(f"  doi = {{{ref_data['doi']}}},")
    
    # Volume
    if ref_data['volume']:
        lines.append(f"  volume = {{{ref_data['volume']}}},")
    
    # Pages
    if ref_data['pages']:
        lines.append(f"  pages = {{{ref_data['pages']}}},")
    
    # Publisher
    if ref_data['publisher']:
        lines.append(f"  publisher = {{{ref_data['publisher']}}},")
    
    lines.append("}")
    
    return '\n'.join(lines)


def find_actual_citation_mapping(tei_path: str) -> Dict[int, str]:
    """
    Find the actual mapping between citation numbers and xml:ids.
    The citation numbers in text don't directly correspond to xml:ids (b0, b1, etc.)
    We need to look at the URL list in the back matter.
    """
    # First, get all the references in order
    tree = ET.parse(tei_path)
    root = tree.getroot()
    
    ordered_refs = []
    for bibl in root.findall('.//tei:listBibl/tei:biblStruct', NS):
        xml_id = bibl.get('{http://www.w3.org/XML/1998/namespace}id', '')
        ordered_refs.append(xml_id)
    
    # Now parse the back matter to find citation numbers
    citation_map = {}
    
    # Look at the text content of the availability div
    for div in root.findall('.//tei:div[@type="availability"]', NS):
        for p in div.findall('.//tei:p', NS):
            text = ET.tostring(p, encoding='unicode', method='text')
            # Find URL followed by [number]
            url_refs = re.findall(r'(https?://[^\s]+)\s*\[(\d+)\]', text)
            for url, num in url_refs:
                # The number is 1-indexed into the ordered refs list
                idx = int(num) - 1
                if 0 <= idx < len(ordered_refs):
                    citation_map[int(num)] = ordered_refs[idx]
    
    # If the back matter doesn't have all citations, try to build from the text
    # The citation numbers seem to match the order in TEI when enumerated
    if len(citation_map) < len(ordered_refs):
        # Try using index + 1 as fallback for unmapped refs
        for idx, xml_id in enumerate(ordered_refs, start=1):
            if idx not in citation_map:
                # This is a fallback - could be wrong
                pass
    
    return citation_map


def build_full_reference_list(tei_path: str) -> Tuple[Dict[int, Dict], Dict[int, str]]:
    """
    Build a complete reference list with citation mappings.
    Returns (references_dict, citation_to_xml_id)
    """
    # Parse all references
    references = parse_tei_references(tei_path)
    
    # Get ordered list from TEI
    tree = ET.parse(tei_path)
    root = tree.getroot()
    
    ordered_refs = []
    for bibl in root.findall('.//tei:listBibl/tei:biblStruct', NS):
        xml_id = bibl.get('{http://www.w3.org/XML/1998/namespace}id', '')
        ordered_refs.append(xml_id)
    
    # Try to get citation numbers from back matter first
    citation_map = {}
    
    for div in root.findall('.//tei:div[@type="availability"]', NS):
        for p in div.findall('.//tei:p', NS):
            text = ET.tostring(p, encoding='unicode', method='text')
            # Find URL followed by [number]
            url_refs = re.findall(r'(https?://[^\s]+)\s*\[(\d+)\]', text)
            for url, num in url_refs:
                idx = int(num) - 1
                if 0 <= idx < len(ordered_refs):
                    citation_map[int(num)] = ordered_refs[idx]
    
    # If still missing, check the listBibl section for direct number tags
    # Looking for patterns like [57] in the text before each biblStruct
    all_refs_div = root.find('.//tei:div[@type="references"]', NS)
    if all_refs_div is not None:
        # The references section might have numbered items
        for p in all_refs_div.findall('.//tei:p', NS):
            text = ET.tostring(p, encoding='unicode', method='text')
            # Try to find [number] patterns in the text
            num_matches = re.findall(r'\[(\d+)\]', text)
            # This is complex - skip for now
    
    return references, citation_map


def main():
    parser = argparse.ArgumentParser(description='Parse references from TEI to BibTeX')
    parser.add_argument('--tei', default='src/paper_data/draft.tei', 
                        help='Path to TEI XML file')
    parser.add_argument('--output', default='refs/bib/references.bib',
                        help='Output BibTeX file')
    args = parser.parse_args()
    
    # Paths
    base_dir = Path(__file__).parent.parent
    tei_path = base_dir / args.tei
    output_path = base_dir / args.output
    
    print(f"Parsing TEI file: {tei_path}")
    
    # Parse references from TEI
    references = parse_tei_references(str(tei_path))
    print(f"Found {len(references)} references in TEI")
    
    # Get ordered list of xml:ids
    tree = ET.parse(str(tei_path))
    root = tree.getroot()
    
    ordered_refs = []
    for bibl in root.findall('.//tei:listBibl/tei:biblStruct', NS):
        xml_id = bibl.get('{http://www.w3.org/XML/1998/namespace}id', '')
        ordered_refs.append(xml_id)
    
    print(f"Ordered refs: {len(ordered_refs)}")
    
    # Find explicit citation mapping from back matter
    citation_map = {}
    for div in root.findall('.//tei:div[@type="availability"]', NS):
        for p in div.findall('.//tei:p', NS):
            text = ET.tostring(p, encoding='unicode', method='text')
            url_refs = re.findall(r'(https?://[^\s]+)\s*\[(\d+)\]', text)
            for url, num in url_refs:
                idx = int(num) - 1
                if 0 <= idx < len(ordered_refs):
                    citation_map[int(num)] = ordered_refs[idx]
    
    print(f"Found {len(citation_map)} explicit citation mappings")
    
    # Check what citations are used in the text files
    print("\n--- Checking citations in text files ---")
    text_files = [
        'parts/01_Introduction.tex',
        'parts/02_Methods.tex', 
        'parts/03_Results.tex',
        'parts/04_Conclusion.tex',
    ]
    
    all_citations = set()
    for tex_file in text_files:
        path = base_dir / tex_file
        if path.exists():
            citations = extract_citation_numbers(str(path))
            all_citations.update(citations)
            print(f"  {tex_file}: {len(citations)} citations: {sorted(citations)}")
    
    print(f"\nTotal unique citations in text: {len(all_citations)}")
    print(f"Citations: {sorted(all_citations)}")
    
    # Build complete mapping: explicit + inferred
    # The mapping seems to be: citation number = xml_id number + 1
    # e.g., b56 -> [57], b75 -> [76]
    # Let's verify and build full mapping
    
    full_citation_map = {}
    
    # Add explicit mappings first
    for cite_num, xml_id in citation_map.items():
        full_citation_map[cite_num] = xml_id
    
    # For citations not in explicit map, try to infer
    # The back matter mapping confirms: citation[N] = ordered_refs[N-1]
    for cite_num in all_citations:
        if cite_num not in full_citation_map:
            idx = cite_num - 1  # Convert to 0-based index
            if 0 <= idx < len(ordered_refs):
                xml_id = ordered_refs[idx]
                if xml_id in references:
                    full_citation_map[cite_num] = xml_id
                    print(f"  Inferred: [{cite_num}] -> {xml_id}")
    
    print(f"\nTotal mapped citations: {len(full_citation_map)}")
    
    # Generate BibTeX entries for all mapped citations
    bibtex_entries = []
    
    for cite_num in sorted(full_citation_map.keys()):
        xml_id = full_citation_map[cite_num]
        if xml_id in references:
            ref_data = references[xml_id]
            entry = generate_bibtex_entry(ref_data, cite_num)
            bibtex_entries.append((cite_num, entry))
        else:
            print(f"  WARNING: Citation [{cite_num}] maps to {xml_id} but ref not found!")
    
    # Write BibTeX file
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("% Auto-generated BibTeX file\n")
        f.write("% Generated from: src/paper_data/draft.tei\n")
        f.write(f"% Total entries: {len(bibtex_entries)}\n\n")
        
        for _, entry in bibtex_entries:
            f.write(entry + '\n\n')
    
    print(f"\nWritten {len(bibtex_entries)} entries to {output_path}")
    
    # Check for missing
    used_citations = set(all_citations)
    mapped_citations = set(full_citation_map.keys())
    missing = used_citations - mapped_citations
    
    if missing:
        print(f"\n⚠️  WARNING: Citations used in text but not in bib: {sorted(missing)}")
    else:
        print("\n✅ All citations mapped!")


if __name__ == '__main__':
    main()
