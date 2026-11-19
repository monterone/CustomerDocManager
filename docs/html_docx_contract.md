# HTML document export contract: version 1

Status: controlled HTML export is implemented for DOCX and RTF. Some target
features below, including explicit page breaks and custom styles, remain deferred.
Existing whole-file DOCX generation remains available through docxtpl.

## Current implementation

`document_manager/documents/html_document.py` contains the shared `HtmlElement` tree,
`parse_html_document`, `get_table_rows`, and `validate_page_settings` APIs.
It depends only on the Python standard library. HTML grammar, structural table
validation, and page settings are defined there, independently of output format.
`document_manager/documents/exporters/docx.py` retains Word-specific writing, image insertion, and styles.
`iter_inline_tokens` also provides shared traversal of inline text and inherited
formatting. Both output formats use these common parsing rules.

### RTF export

`html_rtf_export.export_html_to_rtf(html, page_settings=None, assets=None)` returns RTF bytes
directly, without DOCX conversion, external processes, or database access.
The implementation supports main-region paragraphs, Heading 1-3 styles,
alignment, nested bold/italic/underline, line breaks, page settings, and Unicode.
Text is escaped as RTF, including literal backslashes/braces and signed UTF-16
Unicode escapes with surrogate pairs for non-BMP characters.

Header/footer regions become native RTF destinations. PAGE fields are interpreted
by the reading editor. Rectangular tables use explicit widths and 2 mm horizontal
cell padding; the first all-th row repeats through `\\trhdr`. Body rows can split
across pages. Adjacent tables are separated by a minimal structural paragraph.
PNG/JPEG bytes are embedded directly, preserving source transparency and resolving
requested/intrinsic dimensions through shared `document_images.prepare_image`.
DOCX uses the same asset validation. Both formats reject oversized images.
The preview interface supports DOCX and RTF. The existing plain-text `generate_rtf`
remains a separate generation path; whole-file DOCX-to-RTF conversion is not added.

#### RTF regression checks

The regular unit suite covers literal RTF commands, braces/backslashes, nested
formatting, whitespace and line breaks, empty paragraphs, 1000-record text, page
validation, and 50 seeded Unicode samples, including supplementary-plane text.

Independent reader checks are optional because they require LibreOffice and
`pypdf`. Enable them in PowerShell with:

```powershell
$env:RUN_RTF_ROUNDTRIP = "1"
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_html_rtf_roundtrip.py -v
```

`RTF_TEST_SOFFICE` can override the executable path. These tests generate RTF
directly, import it through LibreOffice, and inspect the resulting DOCX. They
verify 19 text/layout/asset fixtures and a reader-control fixture, including exact
paragraph text, nested character formatting, font sizes, heading styles, page
dimensions and body margins. A PDF check verifies every record in a 200-record
document appears once and in order. A separate multipage table check verifies
all 120 rows, repeating column headings, a visible logo, and current page numbers
on each page. It also checks PNG transparency, JPEG sizing, cell paragraphs,
separate tables, and tables inside headers/footers. Artifacts are kept under
`output/rtf_export_regression_*` for manual inspection.

LibreOffice normalizes header/footer distances to zero when those regions are
absent. The RTF still contains their requested values. A separate control fixture
with explicit RTF regions confirms those values are read correctly once the
regions exist. The exporter now supports these native regions itself.
Exact visual pagination and glyph rendering in Word still require manual checks.

`document_service.generate_document_from_blocks(template_version_id, values,
document_context=None, document_format="DOCX")` connects SQL assembly, the existing
table/image loaders, HTML rendering, and the selected DOCX/RTF exporter.
`generate_docx_from_blocks` remains a compatibility wrapper. All configurations use the requested template
version. The caller supplies scalar values and the context needed by related
tables; the method returns document bytes without writing a file or publishing the
template. Non-empty `style_config` is explicitly rejected until custom style
profiles are implemented. `pages/1_Block_preview.py` uses this service to preview
draft/published block versions and download either format. The main page retains its
existing whole-file generation path. The preview page does not edit or publish.

`html_rendering.render_html_template(template_html, values, tables=None, images=None)` fills scalar
placeholders such as `{{first_name}}` before export. Names follow
`[a-zA-Z_][a-zA-Z0-9_]*`; surrounding whitespace and repeated placeholders are
supported. Missing, null, or blank values become `None`; zero and false are
preserved. Scalar values are HTML-escaped, including quotes, and substituted
once. Use placeholders in text or quoted attribute values, never as tag names,
attribute names, scripts, or CSS. The template itself is trusted application
content and is subsequently checked against the exporter's HTML grammar.
Expressions and loops are deferred. The renderer has no database
access or application integration; callers can pass the existing
`document_service.build_query_tables` result unchanged as `tables`.

### Dynamic table placeholders

A table placeholder occupies a standalone block position directly in `header`,
`main`, or `footer`, for example `<main><h1>Report</h1>{{entries}}</main>`.
Do not wrap it in a `p` element or put it in an attribute. The DOCX-specific
`{{p entries}}` syntax is rejected. Table names and scalar names cannot collide.
Configured tables missing from the template are rejected. Repeated table
placeholders and multiple independently configured tables are supported.

Each table definition contains `columns` (`key`/`title` dictionaries), `rows`
(dictionaries keyed by source fields), and optional `style`. Currently only
`Table Grid` is supported. `render_html_table(columns, rows, style="Table Grid")`
creates a header row and all data rows, escaping titles and cell values.
An empty data selection produces a header-only table. Inserted content is not
evaluated as another template. Query configuration and row loading are unchanged.

### Image placeholders

Pass the existing `document_service.load_image_definitions` result as `images`.
The renderer replaces `{{demo_logo}}` with an internal `<img>` element, copying
optional `width_mm` and `height_mm` settings into its attributes. No dimension
means intrinsic size; one dimension preserves proportions during export.
`render_html_image(name, definition)` constructs this markup without loading data.

Image placeholders can appear directly in a region, in a paragraph/heading,
or in a table cell. They cannot appear in attributes, comments, or tag names.
Each configured image must occur in the template and its name cannot also name
a scalar or table. Repeated placeholders and multiple images are supported.
The same `images` dictionary must be passed as `assets` to the selected exporter;
the exporter validates the actual bytes and embeds the image. Scalar values and
table cell values remain escaped text and cannot inject image markup.

`export_html_to_docx(html, page_settings=None, assets=None)` returns DOCX bytes. It currently
supports paragraphs, headings, bold/italic/underline, line breaks, alignment,
header/main/footer regions, PAGE fields in headers/footers, and rectangular tables
with a repeating first header row, and PNG/JPEG images. Explicit page breaks
and custom style profiles are not implemented yet and
unsupported HTML is rejected. The block preview page uses the exporter through
`generate_docx_from_blocks`.

The default page is A4 portrait with 25 mm margins and 10 mm header/footer
distances. The default font is Arial; that font must be available in the target
editor. Page overrides use these keys (all measured in millimetres):
`page_width_mm`, `page_height_mm`, `margin_top_mm`, `margin_bottom_mm`,
`margin_left_mm`, `margin_right_mm`, `header_distance_mm`, `footer_distance_mm`.
Unknown settings are rejected. Word stores page measurements in discrete units,
so small rounding differences on save are expected.

Assets are supplied as `{"logo": {"data": image_bytes, "mime_type": "image/png"}}`.
Use `<img src="asset:logo" data-width-mm="35" alt="Company logo">`.
Images can appear inline, directly in a region (creating a paragraph), or in a
table cell. Input bytes are verified and embedded unchanged, preserving existing
transparency. Images wider than their content area or taller than the body height
are rejected; full page and header/footer fit still needs visual verification.
Tables have explicit 2 mm left/right cell margins, included in image width checks.

## Pipeline

### Database storage

`template_block_versions.content_html` stores non-empty HTML fragments as TEXT.
`template_layout_versions.content_html` stores the HTML layout shell as TEXT.
Layout versions also store `page_settings` and `style_config` as JSONB objects,
defaulting to `{}`. Page setting keys correspond to the exporter API above.
Custom style profiles are stored for future support; the exporter currently uses
its fixed styles and does not apply `style_config`. Database constraints check
non-empty content and JSON object shape, not HTML grammar or individual settings.
These require validation before use. SQL assembly is implemented by
`public.assemble_template` and is used by the block preview page.
Whole-file DOCX data in `template_versions.template_file` is unchanged.

### SQL assembly

`public_schema/02_assemble_template.sql` installs the procedure after schema
creation. It reads data only and does not save a generated file or fill values.
Draft versions can be assembled for preview; publication is not required.

```sql
CALL public.assemble_template(12, NULL, NULL, NULL);
```

Replace `12` with an actual block-based version ID. The three NULL arguments
are output parameter placeholders. The result is one row containing
`html_template`, `page_settings`, and `style_config`. Styles are returned for
future use; the exporter still uses its fixed style profile.

The layout contains these exact markers once each, replacing whole regions:

```html
<html>
  <head><meta charset="utf-8"></head>
  <body>
    <!-- slot:header -->
    <!-- slot:body -->
    <!-- slot:footer -->
  </body>
</html>
```

Blocks contain fragments such as `<p>{{first_name}}</p>`, without their own
header/main/footer wrappers. The procedure supplies those wrappers. At least
one body block is required; body fragments are joined by a newline in `position`
order. Missing header/footer blocks produce empty header/footer regions.
Slot markers are reserved for layouts and forbidden inside blocks, preventing
inserted fragments from being interpreted as further assembly instructions.

The procedure rejects nonexistent versions, whole-file versions, absent layouts,
missing body blocks, whitespace-only blocks, and missing/duplicate/unknown slot
markers. Layout and blocks are read in one SQL statement snapshot. Full HTML
grammar, placeholder bindings, and export settings are checked later by Python.
No sample blocks are created by this script.

1. SQL assembles the selected layout and pinned block versions into an HTML
   template, preserving header, body, and footer roles.
2. Python loads scalar values, table rows, and image assets and renders HTML.
3. The exporter validates the rendered HTML and settings before producing DOCX
   bytes with python-docx. It does not evaluate placeholders or query the database.

The input is rendered content, not an executable template. Dynamic-table and
image placeholder syntax will be specified with the HTML renderer. Existing
DOCX-specific syntax such as `{{p table}}` is not an HTML-export instruction.

## Input

The assembly result contains `html_template` and `page_settings`. After rendering,
the exporter receives `html`, `page_settings`, and an asset mapping. Assets are
passed by internal reference, with bytes and a validated PNG/JPEG MIME type.
The exporter does not fetch URLs or read arbitrary filesystem paths.

The HTML document has exactly one `main` element and at most one `header` and
one `footer`, all direct children of `body`. Region elements cannot be nested.
A region's children form its content. There is one Word section in version 1.

```html
<html>
  <head><meta charset="utf-8"></head>
  <body>
    <header><p>Demo Company</p></header>
    <main><h1>Customer profile</h1><p>Example customer</p></main>
    <footer><p>Page <span data-field="page-number"></span></p></footer>
  </body>
</html>
```

## Supported content

| HTML | Word representation | Supported settings |
| --- | --- | --- |
| `p` | Paragraph | Left, center, right, or justify alignment |
| `h1`, `h2`, `h3` | Heading 1, 2, or 3 paragraph style | Fixed versioned style settings |
| `strong`, `b` | Bold run | Nested inline content |
| `em`, `i` | Italic run | Nested inline content |
| `u` | Underlined run | Nested inline content |
| `br` | Line break | Inside a paragraph or heading |
| `table` | Word table | Rectangular grid with automatic row heights |
| `thead`, `tbody`, `tr`, `th`, `td` | Rows and cells | First header row may repeat on subsequent pages |
| `img` | Inline picture | Internal asset reference and optional width/height in mm |
| `div data-page-break="before"` | Explicit page break | Empty element in main only |
| `span data-field="page-number"` | Word PAGE field | Empty element in header/footer only |

Tables may contain any number of rows, including an empty body. Row counts are
not part of the template schema. Version 1 supports plain text and paragraphs
with supported inline formatting in cells. Nested tables, cell spans, lists,
floating pictures, arbitrary positioning, and multiple sections are deferred.

Images use `src="asset:reference"`, with `data-width-mm` and `data-height-mm`
as optional positive finite numbers. One specified dimension preserves aspect
ratio; two specify the exact dimensions. With neither, use the image's intrinsic
size. Missing, corrupt, or unsupported assets are errors.

Paragraph alignment uses `data-align="left|center|right|justify"`.
Tables initially use the Word Table Grid style and equal column widths across
the available content width. Version 1 does not support custom cell borders,
backgrounds, or CSS-driven table layout. Oversized content must be reported
rather than silently removed. Very long cell content may flow across pages.

## Page settings and styles

`page_settings` contains explicit millimetre values for page width, height,
top/bottom/left/right margins, and header/footer distances. Body width and height
must remain positive. Header/footer distances must fit within their respective
margins. Portrait and landscape are represented by the page dimensions.

A versioned style profile defines the font family, sizes in points, and paragraph
spacing for Normal, Heading 1-3, Header, and Footer. Exporter defaults must be
explicit and stable. Free-form CSS, style attributes, scripts, event attributes,
and external stylesheets are not supported in version 1. A future HTML preview
can generate CSS from the same profile; browser and Word pagination may differ.

Headers and footers become real section header/footer parts, repeated on every
page. They are not body paragraphs. Distinct first/odd/even page variants are
deferred. Word calculates PAGE field values and automatic page breaks when it
lays out the document; python-docx does not calculate pagination.

## Validation and failure behavior

- Validate the supported element/attribute grammar, parent-child relationships,
  settings, and asset references before export. Do not silently repair malformed
  HTML or discard unsupported meaningful content or formatting.
- Decode HTML entities and preserve Unicode text, including Armenian and Russian.
  Normalize ordinary HTML whitespace; `br` provides an explicit line break.
- The HTML renderer escapes scalar text and cell values. Only application-built
  table/image markup is inserted as trusted markup. Preserve zero and false;
  represent absent or blank scalar/cell values as the literal text `None`.
- Reject missing regions, invalid dimensions, nonrectangular tables, unresolved
  assets, unsupported fields, and forbidden content with actionable errors.
- HTML validity alone does not guarantee that content fits physically on a page.
  Actual layout requires visual acceptance checks in the target Word environment.

## Acceptance criteria

Before integration, verify a complete multipage example with a logo in its header,
a PAGE field in its footer, scalar text, and a long table. Confirm all rows and
images are retained, header rows repeat, styles and page dimensions are correct,
and header/footer parts are separate from body content. Check empty tables,
missing values, Unicode, escaped special characters, and invalid inputs.

Use automated DOCX structure checks and manual inspection in the target editor.
Pin dependencies and document required fonts. Existing DOCX tests must continue
to pass. This contract does not promise identical pagination across editors.
