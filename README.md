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

To delete the database and pgAdmin volumes and initialize them again from
scratch, use:

```bash
docker compose down -v
docker compose up -d
```

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
