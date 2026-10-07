# Ebook workflows

Use only the section relevant to the current request.

## Tool discovery

On Windows, discover optional tools without installing anything:

```powershell
Get-Command ebook-convert, ebook-meta, pandoc, epubcheck, java -ErrorAction SilentlyContinue
```

Prefer the bundled Python runtime when the ordinary `python` command is unavailable.

## Inspect an existing EPUB

1. Run `epub_archive.py inspect` and save JSON output when a machine-readable report is useful.
2. Record the OPF path, EPUB version, metadata, manifest/spine counts, missing files, and navigation/cover declarations.
3. If EPUBCheck is available, run it against the untouched original to establish a baseline.
4. Do not infer that every warning requires a change; distinguish malformed packaging from reader-specific or advisory warnings.

## Edit an existing EPUB

1. Keep the original file unchanged.
2. Extract to a new, empty working directory with `epub_archive.py extract`.
3. Edit XHTML, CSS, images, navigation, or OPF metadata in the working tree.
4. Keep manifest entries, spine references, media types, and relative paths synchronized.
5. Pack to a new output name with `epub_archive.py pack`.
6. Inspect the new EPUB and run EPUBCheck when available.

For a simple metadata-only change, `ebook-meta` may be quicker, but write to a copy first because tool behavior differs by format and version.

## Create a new EPUB

Choose the highest-quality source path:

- Structured HTML/XHTML: use it directly or convert with Calibre/Pandoc.
- Markdown: prefer Pandoc when available, with an explicit title, language, CSS, cover, and EPUB version.
- DOCX: Calibre is convenient; Pandoc can preserve semantic structure better for some documents.
- PDF: treat extraction as reconstruction, not a clean conversion. Expect manual correction of reading order, headings, tables, footnotes, and images.

Example Calibre conversion:

```powershell
ebook-convert source.docx output.epub --title "Book title" --authors "Author name" --language zh
```

Example Pandoc conversion:

```powershell
pandoc chapter01.md chapter02.md -o output.epub --metadata title="Book title" --metadata author="Author name" --metadata lang=zh-CN --epub-version=3
```

Do not claim that conversion alone produces publication-quality results. Inspect navigation, chapter boundaries, image sizing, CSS, footnotes, and front matter.

## Convert EPUB to MOBI or AZW3

Use a validated EPUB as input:

```powershell
ebook-convert final.epub final.azw3
ebook-convert final.epub final.mobi
```

Keep the EPUB as the canonical deliverable. After conversion, inspect metadata and spot-check the output in a compatible reader. Expect some CSS, font, table, and navigation differences.

## Repair a damaged EPUB

1. Inspect the archive. If package errors prevent ordinary extraction, use `epub_archive.py extract broken.epub work/repair --allow-invalid` after reviewing those errors; archive safety checks cannot be bypassed.
2. Repair packaging errors first: `mimetype`, container path, OPF location, missing manifest items, broken spine references, and unsafe paths.
3. Repair reading experience next: navigation, cover, CSS, images, links, and semantics.
4. Do not silently discard files merely because they are unreferenced; determine whether the manifest or the file is wrong.
5. Repack to a new filename and validate again.

## Targeted audit

Run `python scripts/epub_audit.py book.epub --json` for XHTML parsing, IDs, local resources and fragments, marked note references and backlinks, and reader-preference CSS warnings. Inspect warnings in context; local font styling may be intentional for special passages. CSS detection is heuristic, not a full parser. The tool never changes the book or contacts remote links.

Use EPUBCheck independently for normative validation. Use source-page proofreading for OCR correctness, footnote attachment and quotation boundaries. See [ocr-proofreading.md](ocr-proofreading.md) and [reader-compatibility.md](reader-compatibility.md) when relevant.

## Completion report

Include:

- original and output paths;
- formats produced;
- content/metadata/layout changes;
- bundled inspection result;
- EPUBCheck result if run;
- conversion tool and any known lossy behavior;
- unresolved warnings or reader-specific limitations.
