# Customer Document Manager

This project uses Docker Compose for PostgreSQL and pgAdmin, and Streamlit for
the customer document interface. PostgreSQL initialization creates the
`customers`, `templates`, and `template_versions`
tables and loads synthetic CSV data.

## Prerequisites

- Docker Engine or Docker Desktop with Docker Compose
- Python 3.11 or newer

## Setup

### Windows PowerShell

1. Create the environment file:

   ```powershell
   Copy-Item .env.example .env
   ```

2. Create the virtual environment and install dependencies:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   ```

### Linux and macOS

1. Create the environment file:

   ```bash
   cp .env.example .env
   ```

2. Create the virtual environment and install dependencies:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   python -m pip install -r requirements.txt
   ```

Replace the example passwords and credentials in `.env` with your own values
before starting the services.

### Start the database and pgAdmin

Run this command on Windows, Linux, or macOS:

```bash
docker compose up -d
```

Verify the data:

```bash
docker compose exec postgres psql -U customer_app -d customer_doc_manager -c "SELECT COUNT(*) FROM customers;"
```

If you changed `POSTGRES_USER` or `POSTGRES_DB`, use those values in this
command instead.

Open pgAdmin at `http://localhost:5050`. Use the email and password from
`.env` in `PGADMIN_DEFAULT_EMAIL` and `PGADMIN_DEFAULT_PASSWORD`.

Register the PostgreSQL server in pgAdmin with:

- Host: `postgres`
- Port: `5432`
- Maintenance database: value of `POSTGRES_DB`
- Username: value of `POSTGRES_USER`
- Password: value of `POSTGRES_PASSWORD`

Stop the containers while preserving their data with:

```bash
docker compose down
```

PostgreSQL and pgAdmin keep their data in the named volumes `postgres_data`
and `pgadmin_data`. Start the services again with `docker compose up -d`;
the existing database is reused.

## Project organization

Application code lives in `document_manager/`: database access and SQL in
`database/`, workflows in `services/`, rendering and exporters in `documents/`.
Streamlit screens remain in `pages/`; `app.py` is the application entry point.
Docker Compose runs only PostgreSQL and pgAdmin. Document generation runs in
the local Streamlit process and does not require a separate HTTP API.
Local source templates are in `examples/docx/` and `examples/html/`, while
generated documents and conversion reports are in `output/`.

See [the project structure guide](docs/project_structure.md) for the file map.
Open issues and proposed next steps are tracked in the
[architecture backlog](docs/architecture_backlog.md).

## Streamlit application

### Windows PowerShell

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

### Linux and macOS

```bash
source .venv/bin/activate
streamlit run app.py
```

Open the Streamlit URL shown in the terminal, usually
`http://localhost:8501`.

### Create documents

The sidebar has two sections: **Create document** and **Template builder**.
On **Create document**, choose a template, a version, a customer, and an output
format, then click **Generate document**. Published versions are shown by default;
check **Include draft versions** to inspect drafts. Retired versions and archived
templates are not selectable.

The application chooses the existing generation path automatically:

- Text templates: PDF or RTF.
- Whole DOCX templates: DOCX.
- Templates assembled from blocks: PDF, DOCX, or RTF.

PDFs are displayed on the page and all outputs can be downloaded. For block
versions, **Template composition** shows the layout and ordered blocks. Changing
the customer, version, or format clears the previous result. This page reads saved
versions and does not create, edit, or publish templates.

## SQL initialization

`public_schema/01_customer_etl.sql`:

- Creates `public.customers` if missing.
- Seeds `public.customers` from `customer.csv`.
- Creates `public.templates` and `public.template_versions`, including their
  constraints and indexes.
- Seeds the `customer_details` catalog entry and its first published text version.
- Loads `public_schema/customer.csv` directly into `public.customers`.
- Preserves Armenian Unicode text because the CSV and PostgreSQL connection
  use UTF-8.

`public_schema/02_assemble_template.sql` installs the read-only assembly function
`public.assemble_composition` and the saved-version procedure
`public.assemble_template`. It does not seed blocks or modify stored template data.
For an existing database, apply this script to update the assembly routines;
do not rerun the customer initialization ETL.

New databases are initialized directly with the current schema. No legacy
`document_templates` table is created. Scripts in `public_schema` run automatically
only when the PostgreSQL data volume is empty; restarting an existing database
does not rerun initialization.

The application queries use non-archived catalog entries and their published
versions.

Do not rerun `01_customer_etl.sql` to upgrade an existing database: it truncates
and reloads customers from CSV. Additional templates, uploaded DOCX files, and
customer columns added manually to a development database are not exported by
these initialization scripts; back them up separately when moving that data.

### PDF export for block templates

Create document supports DOCX, RTF, and PDF for block-based versions. PDF is generated directly from rendered HTML using the existing ReportLab dependency; no DOCX conversion, LibreOffice, or additional system packages are needed. The shared HTML subset, page settings, asset validation, and database data pipeline apply to all three formats.

PDF supports repeating table headings, PNG/JPEG images, headers, footers, and page numbers. Header/footer content must fit the reserved margins. Embedded fonts cover Latin and Armenian with a bundled Vera fallback; unsupported characters or unavailable italic glyphs raise an explicit error rather than disappearing. Arbitrary HTML/CSS is not supported.

### Block template builder

Open **Build a template from reusable blocks** on the main page, or **Template builder** in the sidebar.

1. Choose **New template** and enter a name, or add a new version to an existing template.
2. Select a layout version and optional header/footer block versions.
3. Add body blocks and use **Up**, **Down**, and **Remove** to arrange them. Repeated blocks are supported.
4. Review each placeholder's content type. Text/numbers use generation values; tables and images reuse settings from the catalog. When multiple settings share a name, choose the intended source explicitly.
5. In the right-hand **Document preview** panel, select a customer and click **Update preview**. The PDF is displayed on the page, without saving or downloading.
6. Click **Save draft** when ready. **Open saved draft** opens **Create document**, enables draft versions, and selects the new version automatically.

The builder reads all catalogs from PostgreSQL, without hard-coded document names or business tables. It pins the selected layout/block versions and copies selected table/image bindings into the new draft. Saving uses one transaction, the existing SQL assembly procedure, and an HTML/assets preflight; a validation failure rolls back the whole save. Published versions are never edited or published by this screen.

This first stage assembles existing layouts, blocks, and configured tables/images. Creating or editing those catalog entries is not yet included. Generation preview currently uses customers as its record selector; the builder does not add new data-source or relation capabilities. No schema migration or reseeding is required.

### Inline preview in the builder

The builder uses two columns: a scrollable composition editor on the left and an
embedded PDF viewer on the right. A template name is not required for preview.
Changing blocks, their order, content bindings, or the preview customer discards
the stale PDF; click **Update preview** to regenerate it. Editing only the template
name does not discard the preview. The PDF can also be downloaded if needed.

Install the PDF viewer along with the project requirements (`streamlit[pdf]` is
included). If it was installed while Streamlit was running, stop the server and
start it again; a browser refresh alone does not discover the new component.
When viewer registration is unavailable, the builder shows a restart message
and keeps the generated PDF available for download.
Preview calls `public.assemble_composition` with a layout version ID and the
selected block versions, roles, and positions. It reads table/image settings
directly and uses the same data queries and PDF exporter as saved documents.
The preview connection is read-only: no temporary records are inserted and no
identity sequences are consumed, including when generation fails.
`public.assemble_template` delegates saved-version assembly to the same function.
Save draft remains a separate write transaction. No table schema changes are required.
