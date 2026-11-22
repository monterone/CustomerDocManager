# Customer Document Manager architecture backlog

Status as of 2026-11-20: issue 2 is resolved for preview. The other numbered issues
remain open; their proposed solutions describe future work.

The application can generate documents and assemble templates from existing
versioned components. Operators still need manual database or code changes to
create layouts, block content, and new data bindings. The objective is a complete
authoring workflow that operators can use without writing Python, SQL, or HTML.

The existing template/version relationships, pinned block and layout versions,
SQL assembly, and exporters provide a foundation for that workflow.

Priority meanings:

- P0: incorrect document output that needs correction.
- P1: a current architectural problem or a missing part of the core authoring workflow.
- P2: an extension to address after the core workflow or when a concrete use case requires it.

## 1 Plain text PDF pagination

**Priority:** P0. **Type:** confirmed generation defect.

The plain-text PDF generator draws lines at decreasing coordinates without wrapping
long lines or creating additional pages. A local in-memory check with a title and
100 rows produced one page, with 69 text fragments below the page boundary.
This is the older text-template path; it is separate from the HTML PDF exporter.

**Direction:** implement wrapping and pagination, or route text through a supported
pagination engine while preserving the intended text-template behavior.

**Done when:** long text remains visible across multiple pages, long lines fit the
available width, and short documents retain their expected content.

Source: [generation.py](../document_manager/documents/generation.py), `generate_pdf`.

## 2 Preview without temporary database records

**Priority:** P1. **Type:** coupling between preview and persistence.
**Status:** resolved on 2026-11-20.

Previously, unsaved preview inserted temporary templates, versions, and bindings,
then rolled back. PostgreSQL identity values were still consumed.

The shared `public.assemble_composition(layout_version_id, blocks)` SQL function
now assembles a composition directly from selected layout/block versions.
Saved-version `public.assemble_template` delegates to this same function.
Preview reads selected table/image settings with SELECT queries over a read-only
connection, closes that connection, and renders the PDF without temporary records.
Save draft retains its separate write transaction.

Verification covered repeated previews, optional header/footer, repeated body
blocks, invalid selections, missing settings, export errors, and the Update preview
button. Row counts in all 13 existing public tables and all public identity sequence
values remained unchanged. Assembly of all four saved block versions was preserved;
the preview matched the saved PDF's text, images, and page geometry.

Source: [template_builder.py](../document_manager/services/template_builder.py),
[SQL assembly](../public_schema/02_assemble_template.sql).
Local regression checks are in `tests/test_read_only_preview.py`.
Tests that intentionally save drafts still require a separate test database.

## 3 Explicit placeholder definitions and scalar bindings

**Priority:** P1. **Type:** missing field model and editor.

The builder discovers names in existing HTML. It does not insert placeholders or
persist a complete definition for ordinary text/number fields. Scalar replacement
currently depends on the placeholder name matching a key in the supplied values.
The UI content-type choices for scalars are not stored as independent field metadata.

A useful definition would describe the technical name, readable label, value type,
source field, required/optional rule, default, and display format. For example,
`client_name` could map to `customers.first_name` instead of requiring identical names.

**Direction:** agree on this field contract before designing its storage and editor.
Reuse the same definitions for insertion, binding, validation, and rendering.

**Done when:** an operator can insert a field, choose its source and presentation,
save those choices, and reopen them without editing HTML or Python.

Keep the agreed `None` behavior for missing values. Diagnostics must distinguish
an empty source value from an unknown or incorrectly configured field; optional
fields should not become errors merely because a value is absent.

Sources: [html_rendering.py](../document_manager/documents/html_rendering.py),
[Template builder](../pages/2_Template_builder.py).

## 4 Layout creation and versioning

**Priority:** P1. **Type:** missing service and interface over existing storage.

`template_layout_versions` already stores layout HTML, page settings, and versions.
The interface can select a layout and display settings, but cannot create a layout
such as Form 0 or save a new version with different page geometry.

**Direction:** start with a name, page size, orientation, margins, and header/footer
distances. Generate the supported HTML skeleton and reuse `validate_page_settings`.
A parameterized INSERT and a service are sufficient for basic creation; a separate
stored procedure is not inherently required.

**Done when:** an operator can create and select a new layout, reuse it in several
templates, and change it through a new version without modifying previous versions.
The first editor should retain the existing header/body/footer structure.

Sources: [schema](../public_schema/01_customer_etl.sql),
[page validation](../document_manager/documents/html_document.py).

## 5 Creating and editing block content

**Priority:** P1. **Type:** missing authoring workflow.

The builder can arrange existing block versions but cannot create a block or edit
its contents. A fresh installation without layouts and body blocks cannot start
authoring through the interface.

**Direction:** add a controlled content editor for supported paragraphs, headings,
field insertion, tables, and images. Produce HTML that the existing parser accepts.
Saving edits to a reused block should create a new block version.

**Done when:** a new block can be created from the interface, previewed, saved,
selected in a template, and revised without changing existing template outputs.

Sources: [Template builder](../pages/2_Template_builder.py),
[supported HTML](../document_manager/documents/html_document.py).

## 6 Independent table definitions

**Priority:** P1. **Type:** missing reusable definition model and editor.

The table catalog is derived from settings already bound to template versions.
Creating the first configuration for a new table still requires manual work.
Selecting an existing block does not automatically bring its table requirements.

**Direction:** separate a reusable table definition from its use in a template.
Define ownership of the source, output columns, headings, filtering, sorting, and
per-use overrides before choosing whether to extend existing storage or add entities.

**Done when:** an operator can configure a new table without an earlier template
as its source, reuse it in another template, and understand the selected data scope.
Rows should continue to be retrieved from business data rather than duplicated
for every customer/template combination.

Sources: [table catalog query](../document_manager/database/queries/get_builder_table_options.sql),
[table loader](../document_manager/services/document_service.py).

## 7 Image catalog and image settings

**Priority:** P1. **Type:** missing authoring interface and binding workflow.

Image assets can be stored in the database, but the builder offers existing
template-version image bindings rather than an independently usable asset catalog.
An asset without an existing binding is not selectable there. Uploading a new logo
and editing its dimensions are not implemented in the interface.

**Direction:** expose asset upload and selection, with separate per-use size and
placement settings. Keep image validation shared with generation.

**Done when:** a new uploaded image is immediately available for use in a template,
and operators can adjust its supported dimensions without SQL.

Sources: [image catalog query](../document_manager/database/queries/get_builder_image_options.sql),
[image validation](../document_manager/documents/images.py).

## 8 Loading and revising existing versions

**Priority:** P1. **Type:** incomplete editing workflow.

New version of an existing template selects the parent catalog entry only. It does
not load or clone the previous composition. Saving attaches the current on-screen
composition to that parent and always creates a new block-based draft.

For a whole-file template, this creates a replacement block-based version; it
does not convert the existing DOCX into blocks. Saved drafts currently reopen for
generation, not for continued editing in the builder.

**Direction:** make the starting point explicit: load a draft, copy a selected
version, or start a new composition. Define whether saving draft edits updates that
draft or creates another version; never silently replace a published version.

**Done when:** operators can reopen a composition with its layout, block order,
and bindings intact, and distinguish copying from file-to-block replacement.

Sources: [Template builder](../pages/2_Template_builder.py),
[version insert](../document_manager/database/queries/insert_builder_version.sql).

## 9 Publication and historical stability

**Priority:** P1. **Type:** missing lifecycle workflow and dependency rules.

The schema defines draft/published/retired and permits at most one published
version per template. The application has no publication/retirement workflow.
Constructor saves append drafts, but there is not yet a complete policy protecting
published content and its layout, block, binding, and asset dependencies.

In particular, copying an image binding copies its image ID. Updating that asset's
bytes would change output for older versions that reference it. Pinning IDs alone
does not freeze the contents of referenced records.

**Direction:** validate a draft before publication, atomically retire the previous
published version and publish the new one, and maintain publication timestamps.
Adopt new-version or new-asset rules for changes to dependencies used by published
templates. Version selection must remain separate from publication.

**Done when:** operators can publish through the interface, and normal editing
operations cannot unexpectedly change output from an existing published version.

Sources: [schema](../public_schema/01_customer_etl.sql),
[image binding copy](../document_manager/database/queries/copy_builder_image.sql).

## 10 Validation before saving and publishing

**Priority:** P1. **Type:** incomplete validation coverage.

Save preflight uses empty scalar values and empty table rows, then checks DOCX
generation. It does not prove that real source queries or every advertised output
format will work. PDF glyph support and header/footer fit can fail later.

**Direction:** provide a shared validation report covering structure, bindings,
source availability, required context, and supported output formats. Keep checks
that require representative data separate from structural checks.

**Done when:** actionable configuration errors are reported before publication,
and operators can distinguish validation errors from missing optional data.

Source: [save preflight](../document_manager/services/template_builder.py).

## 11 Document context and query capabilities

**Priority:** P2, with the context model agreed before supporting new document families.
**Type:** deliberate limits that need explicit extension.

Generation currently selects a customer and supplies the `public.customers` context.
Table retrieval supports all rows from one source, or filtering through one direct
foreign key to the context. It does not return joined columns, follow multiple
relations, apply general filters, or calculate grouped totals.

**Direction:** let a template declare its generation context and expose approved
business sources with readable field/relation names. Add query operations for
concrete cases instead of requiring handwritten SQL or a loader for every template.

**Done when:** a required case such as a document for a selected invoice can choose
that invoice and obtain the supported related data without changes to Python.

Sources: [generation page](../pages/1_Create_document.py),
[metadata validation](../document_manager/database/metadata.py),
[query generation](../document_manager/database/table_query.py).

## 12 Separate values for repeated block instances

**Priority:** P2. **Type:** current binding scope limitation.

Placeholder names are global to a template version. Two occurrences of `city`
receive the same value; two occurrences of `entries` use the same table settings.
Repeating a block does not create independent data bindings.

**Direction:** decide whether distinct names are sufficient or whether block
instances need scoped bindings. The billing-address/delivery-address case is a
useful example for this decision.

**Done when:** the intended repeated-block scenarios have an explicit naming and
binding rule, with no accidental reuse of the wrong value or table configuration.

Sources: [renderer](../document_manager/documents/html_rendering.py),
[binding constraints](../public_schema/01_customer_etl.sql).

## 13 Layout controls and output format differences

**Priority:** P2. **Type:** supported-format boundaries and future authoring controls.

The current HTML subset uses header/main/footer, simple formatting, rectangular
tables, and inline images. Custom style profiles are rejected. Explicit page
breaks, multiple page sections, arbitrary CSS, merged cells, and configurable
column widths are not available as general authoring capabilities.

Block templates support PDF/DOCX/RTF; whole DOCX templates currently produce DOCX
only. The PDF viewer displays an existing PDF, not a converted preview of a selected
DOCX or RTF. Different exporters/readers can paginate the same content differently.

**Direction:** specify supported controls per format and add only controls that the
exporters can handle consistently. If exact DOCX/RTF preview is required, convert
the generated artifact to a PDF viewing copy rather than rendering a different
document and claiming identical layout.

**Done when:** supported layout controls are clear to operators and new controls
have checks in every advertised output format.

Sources: [HTML parser](../document_manager/documents/html_document.py),
[format routing](../document_manager/services/document_service.py),
[export contract](html_docx_contract.md).

## Follow up decisions

These are additional considerations rather than requirements for the first editor:

- **Generated document history:** if issued documents must be retrieved later,
  define an artifact/history record. Template versions alone cannot reproduce
  historical customer values; generated files currently live in session memory.
- **Large datasets:** table queries use `fetchall` without a row limit. Define
  preview limits and generation limits before exposing large business sources.
- **Consistent data snapshots:** configuration and business-data reads span several
  connections. Decide on snapshot rules if concurrent changes must not produce
  mixed document data.
- **Safe schema upgrades:** the initialization ETL truncates/reloads customers.
  Future upgrades to existing installations need explicit non-destructive changes;
  initialization is not an upgrade command.

## Suggested implementation order

1. Correct plain-text PDF output. Preview without temporary persistence is complete.
2. Agree on placeholder definitions, reusable component ownership, and lifecycle rules.
3. Add layout creation and controlled block editing with placeholder insertion.
4. Add independent table configuration and image upload/binding workflows.
5. Add reopening/copying versions, shared validation, and transactional publication.
6. Extend query shapes, layout controls, and document history for agreed use cases.

For each completed issue, record its completion date and the relevant commit or
verification before changing its status. Keep unresolved decisions with the issue
instead of treating a proposed solution as implemented.
