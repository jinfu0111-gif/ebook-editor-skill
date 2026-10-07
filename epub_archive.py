#!/usr/bin/env python3
"""Safely inspect, extract, and repack EPUB archives using the standard library."""

from __future__ import annotations

import argparse
import json
import os
import posixpath
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit
from xml.etree import ElementTree as ET

MIMETYPE = b"application/epub+zip"
MAX_ARCHIVE_BYTES = 1024 * 1024 * 1024
MAX_ARCHIVE_ENTRIES = 10000


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def safe_archive_name(name: str) -> bool:
    if not name or "\x00" in name or "\\" in name:
        return False
    path = PurePosixPath(name)
    if path.is_absolute() or any(part in ("", ".", "..") for part in name.split("/")):
        return False
    reserved = {"CON", "PRN", "AUX", "NUL"} | {f"{prefix}{i}" for prefix in ("COM", "LPT") for i in range(1, 10)}
    return not any(":" in part or part.endswith((".", " ")) or part.split(".")[0].upper() in reserved for part in path.parts)


def resolve_member(base: str, href: str) -> str | None:
    if not href or "\x00" in href:
        return None
    parts = urlsplit(href)
    if parts.scheme or parts.netloc:
        return None
    decoded = unquote(parts.path)
    if decoded.startswith("/") or "\\" in decoded or "\x00" in decoded:
        return None
    joined = posixpath.normpath(posixpath.join(posixpath.dirname(base), decoded)) if decoded else base
    if joined.startswith("../") or joined.startswith("/") or joined in (".", ".."):
        return None
    return joined


def archive_safety_errors(archive: zipfile.ZipFile) -> list[str]:
    """Preflight before reading/extracting members; preserve portable filename safety."""
    infos = archive.infolist()
    errors = []
    if len(infos) > MAX_ARCHIVE_ENTRIES:
        errors.append(f"Archive exceeds {MAX_ARCHIVE_ENTRIES} entries.")
    if sum(info.file_size for info in infos) > MAX_ARCHIVE_BYTES:
        errors.append(f"Archive exceeds {MAX_ARCHIVE_BYTES} uncompressed bytes.")
    seen = set()
    for info in infos:
        name = info.filename.rstrip("/")
        key = name.casefold()
        if not safe_archive_name(name):
            errors.append(f"Unsafe or non-portable archive entry: {info.filename}")
        if key in seen:
            errors.append(f"Duplicate or case-colliding archive entry: {info.filename}")
        seen.add(key)
        if (info.external_attr >> 16) & 0o170000 == 0o120000:
            errors.append(f"Symbolic link in archive: {info.filename}")
        if info.flag_bits & 1:
            errors.append(f"Encrypted ZIP member is unsupported: {info.filename}")
    return errors


def text_of(parent: ET.Element, wanted: str) -> list[str]:
    values = []
    for element in parent.iter():
        if local_name(element.tag) == wanted and element.text and element.text.strip():
            values.append(element.text.strip())
    return values


def inspect_epub(path: Path) -> dict:
    report = {
        "file": str(path.resolve()),
        "errors": [],
        "warnings": [],
        "package": {},
    }
    if not path.is_file():
        report["errors"].append("File does not exist or is not a regular file.")
        return report
    if not zipfile.is_zipfile(path):
        report["errors"].append("File is not a readable ZIP/EPUB archive.")
        return report

    try:
        with zipfile.ZipFile(path) as archive:
            report["errors"].extend(archive_safety_errors(archive))
            if report["errors"]:
                return report
            infos = archive.infolist()
            names = {info.filename for info in infos}
            if not infos or infos[0].filename != "mimetype":
                report["errors"].append("The first ZIP entry is not mimetype.")
            if "mimetype" not in names:
                report["errors"].append("Missing mimetype entry.")
            else:
                mime_info = archive.getinfo("mimetype")
                if mime_info.compress_type != zipfile.ZIP_STORED:
                    report["errors"].append("mimetype is compressed; it must be stored.")
                if archive.read("mimetype") != MIMETYPE:
                    report["errors"].append("mimetype content is not exactly application/epub+zip.")

            container_name = "META-INF/container.xml"
            if container_name not in names:
                report["errors"].append("Missing META-INF/container.xml.")
                return report
            try:
                container = ET.fromstring(archive.read(container_name))
            except ET.ParseError as exc:
                report["errors"].append(f"Invalid container.xml: {exc}")
                return report

            rootfiles = [e for e in container.iter() if local_name(e.tag) == "rootfile"]
            if not rootfiles:
                report["errors"].append("container.xml has no rootfile declaration.")
                return report
            opf_path = rootfiles[0].attrib.get("full-path", "")
            report["package"]["opf_path"] = opf_path
            if not safe_archive_name(opf_path):
                report["errors"].append("The OPF path is unsafe or invalid.")
                return report
            if opf_path not in names:
                report["errors"].append(f"Package document is missing: {opf_path}")
                return report

            try:
                package = ET.fromstring(archive.read(opf_path))
            except ET.ParseError as exc:
                report["errors"].append(f"Invalid OPF package document: {exc}")
                return report

            report["package"]["version"] = package.attrib.get("version")
            metadata = next((e for e in package if local_name(e.tag) == "metadata"), None)
            legacy_cover_ids = []
            if metadata is not None:
                report["package"]["metadata"] = {
                    "title": text_of(metadata, "title"),
                    "creator": text_of(metadata, "creator"),
                    "language": text_of(metadata, "language"),
                    "identifier": text_of(metadata, "identifier"),
                    "publisher": text_of(metadata, "publisher"),
                    "date": text_of(metadata, "date"),
                    "description": text_of(metadata, "description"),
                }
                for required in ("title", "language", "identifier"):
                    if not report["package"]["metadata"][required]:
                        report["errors"].append(f"Missing required metadata: {required}")
                unique_id = package.attrib.get("unique-identifier")
                if not unique_id or not any(local_name(e.tag) == "identifier" and e.attrib.get("id") == unique_id and (e.text or "").strip() for e in metadata):
                    report["errors"].append("unique-identifier does not identify a nonempty dc:identifier.")
                for element in metadata:
                    if (
                        local_name(element.tag) == "meta"
                        and element.attrib.get("name") == "cover"
                        and element.attrib.get("content")
                    ):
                        legacy_cover_ids.append(element.attrib["content"])
            else:
                report["errors"].append("OPF package has no metadata element.")

            manifest_element = next((e for e in package if local_name(e.tag) == "manifest"), None)
            spine_element = next((e for e in package if local_name(e.tag) == "spine"), None)
            manifest = {}
            nav_ids = []
            cover_ids = []
            ncx_ids = []
            if manifest_element is None:
                report["errors"].append("OPF package has no manifest element.")
            else:
                for item in manifest_element:
                    if local_name(item.tag) != "item":
                        continue
                    item_id = item.attrib.get("id", "")
                    href = item.attrib.get("href", "")
                    media_type = item.attrib.get("media-type", "")
                    properties = item.attrib.get("properties", "").split()
                    if not item_id:
                        report["errors"].append("A manifest item has no id.")
                        continue
                    if item_id in manifest:
                        report["errors"].append(f"Duplicate manifest id: {item_id}")
                    member = resolve_member(opf_path, href)
                    manifest[item_id] = {"href": href, "member": member, "media_type": media_type}
                    remote = bool(urlsplit(href).scheme or urlsplit(href).netloc)
                    if remote:
                        report["warnings"].append(f"Remote manifest resource: {href}")
                    elif member is None:
                        report["errors"].append(f"Manifest item {item_id} has an unsafe href: {href}")
                    elif member not in names:
                        report["errors"].append(f"Manifest item {item_id} is missing: {member}")
                    if "nav" in properties:
                        nav_ids.append(item_id)
                    if "cover-image" in properties:
                        cover_ids.append(item_id)
                    if media_type == "application/x-dtbncx+xml":
                        ncx_ids.append(item_id)

            spine_ids = []
            if spine_element is None:
                report["errors"].append("OPF package has no spine element.")
            else:
                for itemref in spine_element:
                    if local_name(itemref.tag) != "itemref":
                        continue
                    idref = itemref.attrib.get("idref", "")
                    spine_ids.append(idref)
                    if idref not in manifest:
                        report["errors"].append(f"Spine references unknown manifest id: {idref}")

            version = str(report["package"].get("version") or "")
            if version.startswith("3") and metadata is not None and not any(local_name(e.tag) == "meta" and e.attrib.get("property") == "dcterms:modified" and (e.text or "").strip() for e in metadata):
                report["errors"].append("EPUB 3 metadata has no dcterms:modified value.")
            if version.startswith("3") and not nav_ids:
                report["errors"].append("EPUB 3 package has no manifest item with the nav property.")
            if not version.startswith("3") and not ncx_ids:
                report["warnings"].append("No NCX navigation item detected for a pre-EPUB 3 package.")
            if version.startswith("3") and not cover_ids:
                report["warnings"].append("No EPUB 3 cover-image property detected.")
            if not version.startswith("3") and not legacy_cover_ids:
                report["warnings"].append("No legacy cover metadata detected.")

            report["package"].update(
                {
                    "manifest_items": len(manifest),
                    "spine_items": len(spine_ids),
                    "navigation_items": nav_ids or ncx_ids,
                    "cover_items": cover_ids or legacy_cover_ids,
                }
            )
    except (OSError, ValueError, zipfile.BadZipFile, RuntimeError) as exc:
        report["errors"].append(f"Could not inspect archive: {exc}")
    return report


def print_report(report: dict, as_json: bool) -> None:
    if as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return
    print(f"File: {report['file']}")
    package = report.get("package", {})
    if package:
        print(f"OPF: {package.get('opf_path', '-')}")
        print(f"EPUB version: {package.get('version', '-')}")
        metadata = package.get("metadata", {})
        for key in ("title", "creator", "language", "identifier"):
            values = metadata.get(key) or []
            print(f"{key.title()}: {', '.join(values) if values else '-'}")
        print(f"Manifest items: {package.get('manifest_items', 0)}")
        print(f"Spine items: {package.get('spine_items', 0)}")
    for error in report["errors"]:
        print(f"ERROR: {error}")
    for warning in report["warnings"]:
        print(f"WARNING: {warning}")
    if not report["errors"]:
        print("Basic EPUB archive/package checks passed.")


def extract_epub(source: Path, destination: Path) -> None:
    if destination.exists() and any(destination.iterdir()):
        raise ValueError("Destination exists and is not empty; choose a new directory.")
    with zipfile.ZipFile(source) as archive:
        errors = archive_safety_errors(archive)
        if errors:
            raise ValueError("; ".join(errors))
        destination.mkdir(parents=True, exist_ok=True)
        root = destination.resolve()
        for info in archive.infolist():
            clean_name = info.filename.rstrip("/")
            if not safe_archive_name(clean_name):
                raise ValueError(f"Unsafe archive entry: {info.filename}")
            mode = (info.external_attr >> 16) & 0o170000
            if mode == 0o120000:
                raise ValueError(f"Symbolic links are not allowed: {info.filename}")
            target = (root / Path(*PurePosixPath(info.filename).parts)).resolve()
            if os.path.commonpath([str(root), str(target)]) != str(root):
                raise ValueError(f"Archive entry escapes destination: {info.filename}")
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info) as src, target.open("wb") as dst:
                    shutil.copyfileobj(src, dst)


def validate_source_tree(source: Path) -> None:
    mime = source / "mimetype"
    container = source / "META-INF" / "container.xml"
    if not source.is_dir():
        raise ValueError("Source is not a directory.")
    if not mime.is_file() or mime.read_bytes() != MIMETYPE:
        raise ValueError("Source must contain an exact mimetype file at its root.")
    if not container.is_file():
        raise ValueError("Source is missing META-INF/container.xml.")


def pack_epub(source: Path, output: Path) -> None:
    validate_source_tree(source)
    if output.exists():
        raise ValueError("Output already exists; choose a new filename.")
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=output.stem + "-", suffix=".tmp", dir=output.parent)
    os.close(fd)
    temp_path = Path(temp_name)
    try:
        with zipfile.ZipFile(temp_path, "w") as archive:
            archive.writestr("mimetype", MIMETYPE, compress_type=zipfile.ZIP_STORED)
            paths = list(source.rglob("*"))
            if any(p.is_symlink() for p in paths):
                raise ValueError("Source tree contains a symbolic link; use regular local files.")
            files = sorted(p for p in paths if p.is_file() and p.relative_to(source).as_posix() != "mimetype")
            for file_path in files:
                arcname = file_path.relative_to(source).as_posix()
                archive.write(file_path, arcname, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
        report = inspect_epub(temp_path)
        if report["errors"]:
            raise ValueError("Packed EPUB failed checks: " + "; ".join(report["errors"]))
        # Exclusive creation also protects a file appearing after the initial check.
        # Avoid hard-link requirements on removable filesystems and sandboxed Windows.
        with output.open("xb") as destination:
            try:
                with temp_path.open("rb") as prepared:
                    shutil.copyfileobj(prepared, destination)
            except BaseException:
                destination.close()
                output.unlink()
                raise
    finally:
        if temp_path.exists():
            temp_path.unlink()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    inspect_parser = subparsers.add_parser("inspect", help="Inspect archive and package consistency")
    inspect_parser.add_argument("epub", type=Path)
    inspect_parser.add_argument("--json", action="store_true", help="Print JSON")
    extract_parser = subparsers.add_parser("extract", help="Safely extract to an empty directory")
    extract_parser.add_argument("epub", type=Path)
    extract_parser.add_argument("destination", type=Path)
    extract_parser.add_argument("--allow-invalid", action="store_true", help="Allow package errors for deliberate repair; ZIP safety checks still apply")
    pack_parser = subparsers.add_parser("pack", help="Pack an extracted EPUB tree")
    pack_parser.add_argument("source", type=Path)
    pack_parser.add_argument("output", type=Path)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.command == "inspect":
            report = inspect_epub(args.epub)
            print_report(report, args.json)
            return 1 if report["errors"] else 0
        if args.command == "extract":
            report = inspect_epub(args.epub)
            if report["errors"] and not args.allow_invalid:
                raise ValueError("Input EPUB failed checks: " + "; ".join(report["errors"]))
            extract_epub(args.epub, args.destination)
            print(f"Extracted to: {args.destination.resolve()}")
            return 0
        if args.command == "pack":
            pack_epub(args.source, args.output)
            print(f"Created: {args.output.resolve()}")
            return 0
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
