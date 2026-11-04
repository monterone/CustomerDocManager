CREATE TABLE IF NOT EXISTS public.customers (
    customer_id INTEGER PRIMARY KEY,
    first_name VARCHAR(100) NOT NULL,
    surname VARCHAR(100) NOT NULL
);

TRUNCATE TABLE public.customers;

COPY public.customers (customer_id, first_name, surname)
FROM '/docker-entrypoint-initdb.d/customer.csv'
WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');
