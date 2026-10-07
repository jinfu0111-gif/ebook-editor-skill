#!/usr/bin/env python3
"""Read-only EPUB link/note audit and heuristic reader-preference CSS hints.

Not a substitute for EPUBCheck, source proofreading, or reader testing.
Uses only Python 3.10+ standard-library modules; never fetches remote resources.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from pathlib import Path
from urllib.parse import unquote, urlsplit
from xml.etree import ElementTree as ET

from epub_archive import inspect_epub, local_name, resolve_member

EPUB_TYPE = "{http://www.idpf.org/2007/ops}type"
XML_ID = "{http://www.w3.org/XML/1998/namespace}id"
XLINK_HREF = "{http://www.w3.org/1999/xlink}href"
CHINESE = r"[\u3400-\u9fff]"


def types(element: ET.Element) -> set[str]:
    return set(element.attrib.get(EPUB_TYPE, "").split())


def local_target(source: str, href: str) -> tuple[str, str] | None:
    parts = urlsplit(href)
    if parts.scheme or parts.netloc:
        return None
    member = resolve_member(source, href)
    return (member or "", unquote(parts.fragment))


def css_hints(css: str, source: str) -> list[dict[str, str]]:
    """Conservative candidate rules, not complete CSS parsing or computed styling."""
    hints = []
    cleaned = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    for match in re.finditer(r"([^{}]+)\{([^{}]*)\}", cleaned):
        selector, declarations = match.groups()
        selector = selector.strip()
        if selector.startswith("@"):
            continue
        tokens = re.split(r"[\s,>+~.#:\[\]]+", selector)
        if not any(token in {"html", "body", "p", "*"} for token in tokens):
            continue
        for declaration in declarations.split(";"):
            key, separator, value = declaration.partition(":")
            if not separator:
                continue
            key, value = key.strip().lower(), value.strip()
            normalized = re.sub(r"\s*!important\s*$", "", value, flags=re.I).lower()
            inherited = normalized in {"inherit", "unset", "revert", "revert-layer"}
            reason = ""
            if key == "line-height" and not inherited and normalized != "normal":
                reason = "Declared line height may override the reader's setting."
            elif key == "font-family" and not inherited:
                reason = "Declared font may limit font selection; verify scope and reader behavior."
            elif key in {"color", "background", "background-color"} and not inherited and normalized not in {"transparent", "currentcolor", "none"}:
                reason = "Declared text/background color needs light/dark theme testing."
            elif key == "font-size" and not inherited and normalized not in {"1em", "100%"}:
                reason = "Declared text size needs reader-size testing; special passages may be intentional."
            elif key in {"height", "width", "min-height", "min-width"} and re.search(r"\d\s*(?:px|pt)\b", normalized):
                reason = "Fixed text dimensions may clip content at large font sizes."
            if reason:
                hints.append({"file": source, "selector": selector, "property": key, "value": value, "message": reason})
    return hints


def audit_epub(path: Path) -> dict:
    base = inspect_epub(path)
    report = {
        "file": str(path.resolve()),
        "scope": "Basic package, XHTML IDs/resources/links, marked note backlinks, heuristic CSS. Not EPUBCheck or proofreading.",
        "errors": list(base["errors"]),
        "warnings": list(base["warnings"]),
        "package": base.get("package", {}),
        "stats": {"xhtml_documents": 0, "internal_references": 0, "noterefs": 0, "notes": 0},
        "css_hints": [],
        "text_candidates": [],
    }
    if report["errors"]:
        return report
    try:
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
            documents = {}
            targets = {}
            notes = {}
            refs = []
            for name in sorted(names):
                if name.lower().endswith(".css"):
                    report["css_hints"].extend(css_hints(archive.read(name).decode("utf-8-sig", errors="replace"), name))
                if not name.lower().endswith((".xhtml", ".html", ".htm", ".svg")):
                    continue
                try:
                    root = ET.fromstring(archive.read(name))
                except ET.ParseError as exc:
                    report["errors"].append(f"Invalid XML content: {name}: {exc}")
                    continue
                documents[name] = root
                index = {}
                for element in root.iter():
                    element_id = element.attrib.get("id") or element.attrib.get(XML_ID)
                    if element_id:
                        if element_id in index:
                            report["errors"].append(f"Duplicate content ID: {name}#{element_id}")
                        index[element_id] = element
                    if types(element) & {"footnote", "endnote"}:
                        if element_id:
                            notes[(name, element_id)] = element
                        else:
                            report["warnings"].append(f"Marked note has no ID: {name}")
                    if "noteref" in types(element) or element.attrib.get("role") == "doc-noteref":
                        refs.append((name, element))
                    if local_name(element.tag) == "style":
                        report["css_hints"].extend(css_hints("".join(element.itertext()), name + " (style)"))
                    if element.attrib.get("style") and local_name(element.tag) in {"html", "body", "p"}:
                        report["css_hints"].extend(css_hints(local_name(element.tag) + "{" + element.attrib["style"] + "}", name + " (inline)"))
                    if local_name(element.tag) == "p":
                        text = "".join(element.itertext()).strip()
                        if re.search(CHINESE + r"\.(?:\s|$|[”’）])", text):
                            report["text_candidates"].append({"file": name, "id": element_id, "kind": "chinese_ascii_period", "text": text[:160]})
                targets[name] = index

            report["stats"]["xhtml_documents"] = sum(name.lower().endswith((".xhtml", ".html", ".htm")) for name in documents)
            report["stats"]["notes"] = len(notes)
            report["stats"]["noterefs"] = len(refs)
            for source, root in documents.items():
                for element in root.iter():
                    for attribute in ("href", "src", "poster", XLINK_HREF):
                        href = element.attrib.get(attribute)
                        if href is None or href == "":
                            continue
                        target = local_target(source, href)
                        if target is None:
                            continue
                        report["stats"]["internal_references"] += 1
                        member, fragment = target
                        if not member or member not in names:
                            report["errors"].append(f"Missing/unsafe resource: {source} -> {href}")
                        elif fragment and member in targets and fragment not in targets[member]:
                            report["errors"].append(f"Missing fragment: {source} -> {href}")
                        elif fragment and member not in targets:
                            report["warnings"].append(f"Fragment not audited for this resource type: {source} -> {href}")

            reached_notes = set()
            for source, ref in refs:
                href = ref.attrib.get("href", "")
                target = local_target(source, href) if href else None
                if not target or target not in notes:
                    report["warnings"].append(f"Note reference has no marked note target: {source} -> {href}")
                    continue
                reached_notes.add(target)
                ref_id = ref.attrib.get("id") or ref.attrib.get(XML_ID)
                if not ref_id:
                    report["warnings"].append(f"Note reference has no return anchor: {source} -> {href}")
                    continue
                note_source, _ = target
                note = notes[target]
                backlinks = [local_target(note_source, a.attrib["href"]) for a in note.iter() if local_name(a.tag) == "a" and "href" in a.attrib]
                if (source, ref_id) not in backlinks:
                    report["warnings"].append(f"No explicit backlink to reference: {source}#{ref_id} -> {href}")
            for member, fragment in sorted(set(notes) - reached_notes):
                report["warnings"].append(f"Marked note has no detected noteref: {member}#{fragment}")
    except (OSError, ValueError, RuntimeError, zipfile.BadZipFile) as exc:
        report["errors"].append(f"Could not audit EPUB: {exc}")
    if report["css_hints"]:
        report["warnings"].append(f"Reader-preference CSS candidates: {len(report['css_hints'])}; inspect css_hints in context.")
    if report["text_candidates"]:
        report["warnings"].append(f"Source-proofreading candidates: {len(report['text_candidates'])}; no automatic text changes.")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("epub", type=Path)
    parser.add_argument("--json", action="store_true", help="Print the full machine-readable report")
    args = parser.parse_args()
    report = audit_epub(args.epub)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(report["scope"])
        print(json.dumps(report["stats"], ensure_ascii=False))
        for level in ("errors", "warnings"):
            for message in report[level]:
                print(f"{level[:-1].upper()}: {message}")
        for hint in report["css_hints"]:
            print(f"CSS: {hint['file']} | {hint['selector']} | {hint['property']}: {hint['value']}")
        if not report["errors"]:
            print("No errors in the audited scope.")
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
