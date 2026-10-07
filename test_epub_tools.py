"""Synthetic, original fixtures only. No copyrighted books or network needed."""

import json
import subprocess
import sys
import tempfile
import unittest
import warnings
import zipfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import epub_archive as archive
import epub_audit as audit

CONTAINER = '''<?xml version="1.0"?>
<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container" version="1.0">
<rootfiles><rootfile full-path="EPUB/package.opf" media-type="application/oebps-package+xml"/></rootfiles></container>'''
OPF = '''<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="book-id">
<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
<dc:identifier id="book-id">urn:uuid:synthetic-fixture</dc:identifier>
<dc:title>原创测试小样</dc:title><dc:language>zh-CN</dc:language>
<dc:date>2026</dc:date><meta property="dcterms:modified">2026-10-07T00:00:00Z</meta>
</metadata><manifest>
<item id="chapter" href="chapter.xhtml" media-type="application/xhtml+xml"/>
<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>
<item id="css" href="reader.css" media-type="text/css"/>
</manifest><spine><itemref idref="chapter"/></spine></package>'''
NAV = '''<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" lang="zh-CN">
<head><title>目录</title></head><body><nav epub:type="toc" id="toc"><h1>目录</h1>
<ol><li><a href="chapter.xhtml#chapter-1">测试章</a></li></ol></nav></body></html>'''


class EpubToolsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        self.source.mkdir()
        self.write("mimetype", archive.MIMETYPE)
        self.write("META-INF/container.xml", CONTAINER)
        self.write("EPUB/package.opf", OPF)
        self.write("EPUB/nav.xhtml", NAV)
        self.chapter = (ROOT / "assets/footnotes.xhtml").read_text(encoding="utf-8")
        self.write("EPUB/chapter.xhtml", self.chapter)
        self.write("EPUB/reader.css", (ROOT / "assets/reader.css").read_bytes())
        self.epub = self.root / "sample.epub"

    def write(self, name, content):
        path = self.source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content.encode("utf-8") if isinstance(content, str) else content)

    def pack(self):
        archive.pack_epub(self.source, self.epub)
        return self.epub

    def raw_zip(self, entries):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with zipfile.ZipFile(self.epub, "w") as z:
                for name, content in entries:
                    if isinstance(name, str):
                        info = zipfile.ZipInfo("placeholder")
                        info.filename = name
                        name = info
                    z.writestr(name, content)

    def cli(self, script, *args):
        return subprocess.run([sys.executable, str(ROOT / "scripts" / script), *map(str, args)],
                              capture_output=True, encoding="utf-8", env=self.utf8_env())

    @staticmethod
    def utf8_env():
        import os
        return {**os.environ, "PYTHONUTF8": "1"}

    def test_pack_mimetype_and_metadata(self):
        self.pack()
        with zipfile.ZipFile(self.epub) as z:
            self.assertEqual(z.infolist()[0].filename, "mimetype")
            self.assertEqual(z.infolist()[0].compress_type, zipfile.ZIP_STORED)
            self.assertEqual(z.read("mimetype"), archive.MIMETYPE)
        report = archive.inspect_epub(self.epub)
        self.assertEqual(report["errors"], [])
        self.assertEqual(report["package"]["metadata"]["date"], ["2026"])

    def test_byte_preserving_roundtrip_including_nested_mimetype(self):
        self.write("EPUB/mimetype", b"This is an unrelated resource.")
        before = {p.relative_to(self.source).as_posix(): p.read_bytes() for p in self.source.rglob("*") if p.is_file()}
        self.pack()
        destination = self.root / "extracted"
        archive.extract_epub(self.epub, destination)
        after = {p.relative_to(destination).as_posix(): p.read_bytes() for p in destination.rglob("*") if p.is_file()}
        self.assertEqual(before, after)

    def test_no_output_overwrite(self):
        self.epub.write_bytes(b"user file")
        with self.assertRaises(ValueError):
            self.pack()
        self.assertEqual(self.epub.read_bytes(), b"user file")

    def test_nonempty_extraction_destination_preserved(self):
        self.pack()
        destination = self.root / "existing"
        destination.mkdir()
        (destination / "owned.txt").write_bytes(b"keep")
        with self.assertRaises(ValueError):
            archive.extract_epub(self.epub, destination)
        self.assertEqual(list(destination.iterdir()), [destination / "owned.txt"])

    def test_unsafe_paths_preflight_before_writing(self):
        self.assertFalse(archive.safe_archive_name("a\\b"))
        # Windows ZipInfo normalizes backslashes while reading, so test raw
        # name rejection separately from ZIP fixtures on every platform.
        for name in ("../escaped", "/absolute", "C:/drive", "a/../b", "CON.txt", "trailing. "):
            with self.subTest(name=name):
                self.raw_zip([("safe.txt", b"safe"), (name, b"bad")])
                destination = self.root / ("not-created-" + str(len(list(self.root.iterdir()))))
                with self.assertRaises(ValueError):
                    archive.extract_epub(self.epub, destination)
                self.assertFalse(destination.exists())

    def test_duplicate_and_case_colliding_paths_rejected(self):
        for names in (("same", "same"), ("same", "SAME")):
            self.raw_zip([(name, b"data") for name in names])
            self.assertTrue(any("colliding" in e for e in archive.inspect_epub(self.epub)["errors"]))

    def test_symlink_archive_rejected(self):
        info = zipfile.ZipInfo("link")
        info.create_system = 3
        info.external_attr = (0o120777 << 16)
        self.raw_zip([(info, b"../outside")])
        self.assertTrue(any("Symbolic link" in e for e in archive.inspect_epub(self.epub)["errors"]))

    def test_archive_limits_enforced(self):
        self.pack()
        with patch.object(archive, "MAX_ARCHIVE_BYTES", 1):
            self.assertTrue(any("bytes" in e for e in archive.inspect_epub(self.epub)["errors"]))
        with patch.object(archive, "MAX_ARCHIVE_ENTRIES", 1):
            self.assertTrue(any("entries" in e for e in archive.inspect_epub(self.epub)["errors"]))

    def test_allow_invalid_is_not_a_safety_bypass(self):
        self.raw_zip([("mimetype", b"wrong"), ("safe.txt", b"repair me")])
        destination = self.root / "repair"
        result = self.cli("epub_archive.py", "extract", self.epub, destination, "--allow-invalid")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((destination / "safe.txt").read_bytes(), b"repair me")
        self.raw_zip([("../bad", b"never")])
        result = self.cli("epub_archive.py", "extract", self.epub, self.root / "unsafe", "--allow-invalid")
        self.assertEqual(result.returncode, 2)
        self.assertFalse((self.root / "unsafe").exists())

    def test_failed_pack_leaves_no_output_or_temp(self):
        self.write("EPUB/package.opf", OPF.replace('properties="nav"', ""))
        with self.assertRaises(ValueError):
            self.pack()
        self.assertFalse(self.epub.exists())
        self.assertEqual(list(self.root.glob("*.tmp")), [])

    def test_required_identifier_checked(self):
        self.write("EPUB/package.opf", OPF.replace('unique-identifier="book-id"', 'unique-identifier="missing"'))
        with self.assertRaisesRegex(ValueError, "unique-identifier"):
            self.pack()

    def test_valid_notes_and_reader_template(self):
        result = audit.audit_epub(self.pack())
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["stats"]["noterefs"], 1)
        self.assertEqual(result["stats"]["notes"], 1)
        self.assertEqual(result["css_hints"], [])
        self.assertFalse(any("backlink" in w or "noteref" in w for w in result["warnings"]))

    def test_missing_fragment_is_error(self):
        self.write("EPUB/chapter.xhtml", self.chapter.replace('href="#note-1"', 'href="#missing"'))
        result = audit.audit_epub(self.pack())
        self.assertTrue(any("Missing fragment" in e for e in result["errors"]))

    def test_missing_backlink_is_warning(self):
        self.write("EPUB/chapter.xhtml", self.chapter.replace('href="#ref-1"', 'href="#chapter-1"'))
        result = audit.audit_epub(self.pack())
        self.assertEqual(result["errors"], [])
        self.assertTrue(any("No explicit backlink" in w for w in result["warnings"]))

    def test_duplicate_content_ids(self):
        self.write("EPUB/chapter.xhtml", self.chapter.replace("</body>", '<p id="ref-1">重复标识。</p></body>'))
        self.assertTrue(any("Duplicate content ID" in e for e in audit.audit_epub(self.pack())["errors"]))

    def test_malformed_xhtml(self):
        self.write("EPUB/chapter.xhtml", "<html><body>")
        self.assertTrue(any("Invalid XML" in e for e in audit.audit_epub(self.pack())["errors"]))

    def test_unicode_percent_encoded_links(self):
        self.write("EPUB/注释 空格.xhtml", '<html xmlns="http://www.w3.org/1999/xhtml"><head><title>附页</title></head><body><p id="标识">原创。</p></body></html>')
        self.write("EPUB/chapter.xhtml", self.chapter.replace("</body>", '<p><a href="%E6%B3%A8%E9%87%8A%20%E7%A9%BA%E6%A0%BC.xhtml#%E6%A0%87%E8%AF%86">附页</a></p></body>'))
        self.assertEqual(audit.audit_epub(self.pack())["errors"], [])
        self.assertIsNone(archive.resolve_member("EPUB/chapter.xhtml", "%2e%2e/%2e%2e/outside"))

    def test_css_candidates_and_no_text_mutation(self):
        self.write("EPUB/reader.css", 'body {line-height: 24px !important; color: black; font-family: serif;}')
        self.write("EPUB/chapter.xhtml", self.chapter.replace("</body>", '<p>待核对的中文.</p></body>'))
        self.pack()
        before = self.epub.read_bytes()
        result = audit.audit_epub(self.epub)
        self.assertEqual(len(result["css_hints"]), 3)
        self.assertEqual(len(result["text_candidates"]), 1)
        self.assertEqual(before, self.epub.read_bytes())

    def test_multiple_references_to_one_note(self):
        chapter = self.chapter.replace("</body>", '<p>再次引用<a id="ref-2" epub:type="noteref" href="#note-1">[1]</a>。</p></body>')
        chapter = chapter.replace("</aside>", '<a href="#ref-2">返回第二处</a></aside>')
        self.write("EPUB/chapter.xhtml", chapter)
        result = audit.audit_epub(self.pack())
        self.assertEqual(result["stats"]["noterefs"], 2)
        self.assertFalse(any("backlink" in w for w in result["warnings"]))

    def test_cli_json_and_exit_codes(self):
        self.pack()
        for script, args in (("epub_archive.py", ["inspect"]), ("epub_audit.py", [])):
            result = self.cli(script, *args, self.epub, "--json")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["errors"], [])
            result = self.cli(script, *args, self.root / "missing.epub", "--json")
            self.assertEqual(result.returncode, 1)
            self.assertTrue(json.loads(result.stdout)["errors"])


if __name__ == "__main__":
    unittest.main()
