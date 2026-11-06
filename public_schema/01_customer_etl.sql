CREATE TABLE IF NOT EXISTS public.customers (
    customer_id INTEGER PRIMARY KEY,
    first_name VARCHAR(100) NOT NULL,
    surname VARCHAR(100) NOT NULL
);

TRUNCATE TABLE public.customers;

COPY public.customers (customer_id, first_name, surname)
FROM '/docker-entrypoint-initdb.d/customer.csv'
WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

CREATE TABLE IF NOT EXISTS public.document_templates (
    template_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    version INTEGER NOT NULL,
    template_text TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE (name, version)
);

INSERT INTO public.document_templates (
    name,
    version,
    template_text,
    is_active
)
VALUES (
    'customer_details',
    1,
    'CUSTOMER DETAILS

Customer name: {{first_name}}
Customer surname: {{surname}}
Date: {{current_date}}',
    TRUE
)
ON CONFLICT (name, version) DO UPDATE
SET template_text = EXCLUDED.template_text,
    is_active = EXCLUDED.is_active;
