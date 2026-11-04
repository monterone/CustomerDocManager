# Customer ETL with Docker

This setup provides PostgreSQL and pgAdmin. The PostgreSQL initialization scripts
create the `customers` table and load the synthetic data from
`public_schema/customer.csv` using an idempotent staging-table ETL.

## Setup

1. Copy `.env.example` to `.env` and replace the example passwords.
2. Start the services:

   ```powershell
   docker compose up -d
   ```

3. Verify PostgreSQL initialization:

   ```powershell
   docker compose exec postgres psql -U customer_app -d customer_doc_manager -c "SELECT COUNT(*), MIN(customer_id), MAX(customer_id) FROM customers;"
   ```

   If you changed `POSTGRES_USER` or `POSTGRES_DB`, use those values instead of
   the examples above.

4. Open pgAdmin at `http://localhost:5050`.
   Use the values configured in `.env` as the login email and password.
   Add a server with host `postgres`, port `5432`, database from
   `POSTGRES_DB`, and user from `POSTGRES_USER`.

Stop the services with `docker compose down`. The `postgres_data` volume keeps
database data. To perform a clean database initialization, remove that named
volume with `docker compose down -v`.

If initialization failed before the database was ready, recreate the containers
without deleting data, then run the ETL manually:

```powershell
docker compose down
docker compose up -d postgres
docker compose exec postgres psql -U customer_app -d customer_doc_manager -f /docker-entrypoint-initdb.d/01_customer_etl.sql
docker compose up -d pgadmin
```

## SQL ETL

`public_schema/01_customer_etl.sql`:

- Creates `public.customers` if missing.
- Clears the table before loading.
- Loads `public_schema/customer.csv` directly into `public.customers`.
- Preserves Armenian Unicode text because the CSV and PostgreSQL connection
  use UTF-8.

Initialization scripts run only on a new PostgreSQL data volume. To rerun the
ETL manually:

```powershell
docker compose exec postgres psql -U customer_app -d customer_doc_manager -f /docker-entrypoint-initdb.d/01_customer_etl.sql
```
