# Customer Document Manager

This project uses Docker Compose for PostgreSQL and pgAdmin, and Streamlit for
the customer document interface. PostgreSQL initialization creates the
`customers` and `document_templates` tables and loads synthetic CSV data.

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
- Creates and seeds `public.document_templates`.
- Loads `public_schema/customer.csv` directly into `public.customers`.
- Preserves Armenian Unicode text because the CSV and PostgreSQL connection
  use UTF-8.

Initialization scripts run only on a new PostgreSQL data volume. To rerun the
ETL manually:

```bash
docker compose exec postgres psql -U customer_app -d customer_doc_manager -f /docker-entrypoint-initdb.d/01_customer_etl.sql
```
