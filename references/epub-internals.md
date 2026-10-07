# EPUB internals and invariants

Read this reference before low-level EPUB changes.

## Archive requirements

- The first ZIP entry must be `mimetype`.
- Its content must be exactly `application/epub+zip` with no BOM or trailing newline.
- The `mimetype` entry must be stored without compression.
- `META-INF/container.xml` must identify the package document (OPF).
- Paths use forward slashes and must remain inside the archive.

## Package document

The OPF package document ties the publication together:

- metadata: title, creator, language, identifier, modified timestamp where required;
- manifest: every reading resource with a correct relative `href` and media type;
- spine: reading order through manifest item IDs;
- EPUB 3 navigation: one manifest item with the `nav` property;
- cover image: usually one image item with the `cover-image` property;
- EPUB 2 compatibility: may use NCX navigation and legacy cover metadata.

When renaming files, update every referencing location: OPF manifest, spine IDs when relevant, navigation links, XHTML links, CSS URLs, and guide/NCX entries.

## XHTML and navigation

- Use valid XML-compatible XHTML and UTF-8.
- Keep one clear heading hierarchy per chapter.
- Use semantic landmarks and accessible alternative text where practical.
- Navigation targets must exist and fragment IDs must be unique within each document.
- Avoid relying on JavaScript or remote resources for core reading functionality.

## CSS and media

- Prefer reflowable, reader-tolerant CSS over fixed pixel layouts unless fixed-layout EPUB is explicitly required.
- Avoid forcing body fonts, colors, line heights, or margins in ways that defeat reader preferences.
- Declare image dimensions or responsive constraints without stretching aspect ratios.
- Embedded fonts require appropriate licensing and correct manifest media types.

## Publication metadata

- Record publication date in `dc:date`; record EPUB 3 modification time separately in `meta property="dcterms:modified"` using UTC ISO 8601.
- Preserve known precision: if only the month is known, use `YYYY-MM` rather than inventing a day. Readers may display a placeholder day when interpreting a reduced-precision date.
- Use a stable primary identifier and a separately recognizable ISBN identifier when supplied. Do not invent an ISBN.
- Store the actual synopsis in `dc:description`; OCR process notes belong in a separately labeled front-matter page or project report.
- Metadata updates alone do not change a library application's cached record. Verify the edited file, and distinguish it from an existing imported library copy.

## Validation interpretation

The bundled helper checks archive and package consistency but is not a replacement for EPUBCheck. EPUBCheck validates more of the EPUB specification; visual reader testing catches presentation issues neither structural validator can prove.

Resolve errors before warnings. Do not rewrite content merely to eliminate an advisory warning unless the change is safe and relevant to the requested target readers.
