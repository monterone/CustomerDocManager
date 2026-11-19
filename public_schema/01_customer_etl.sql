BEGIN;

CREATE TABLE IF NOT EXISTS public.customers (
    customer_id INTEGER PRIMARY KEY,
    first_name VARCHAR(100) NOT NULL,
    surname VARCHAR(100) NOT NULL
);

TRUNCATE TABLE public.customers;

COPY public.customers (customer_id, first_name, surname)
FROM '/docker-entrypoint-initdb.d/customer.csv'
WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

CREATE TABLE IF NOT EXISTS public.templates (
    template_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code VARCHAR(100) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS public.template_versions (
    template_version_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    template_id INTEGER NOT NULL
        REFERENCES public.templates (template_id) ON DELETE RESTRICT,
    version_number INTEGER NOT NULL CHECK (version_number > 0),
    status VARCHAR(20) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'published', 'retired')),
    template_format VARCHAR(10) NOT NULL
        CHECK (template_format IN ('text', 'docx')),
    template_text TEXT,
    template_file BYTEA,
    change_note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    published_at TIMESTAMPTZ,
    CONSTRAINT template_versions_template_version_key
        UNIQUE (template_id, version_number),
    CONSTRAINT template_versions_content_check CHECK (
        (template_format = 'text'
         AND template_text IS NOT NULL AND template_file IS NULL)
        OR
        (template_format = 'docx'
         AND template_text IS NULL AND template_file IS NOT NULL
         AND octet_length(template_file) > 0)
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS template_versions_one_published_idx
    ON public.template_versions (template_id)
    WHERE status = 'published';

CREATE TABLE IF NOT EXISTS public.template_version_tables (
    table_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    template_version_id INTEGER NOT NULL
        REFERENCES public.template_versions (template_version_id) ON DELETE RESTRICT,
    placeholder_name VARCHAR(100) NOT NULL CHECK (btrim(placeholder_name) <> ''),
    columns_config JSONB NOT NULL,
    style VARCHAR(100) NOT NULL DEFAULT 'Table Grid' CHECK (btrim(style) <> ''),
    query_config JSONB,
    CONSTRAINT template_version_tables_query_config_check
        CHECK (query_config IS NULL OR jsonb_typeof(query_config) = 'object'),
    CONSTRAINT template_version_tables_placeholder_key
        UNIQUE (template_version_id, placeholder_name),
    CONSTRAINT template_version_tables_columns_check CHECK (
        CASE WHEN jsonb_typeof(columns_config) = 'array'
             THEN jsonb_array_length(columns_config) > 0
             ELSE FALSE END
    )
);

CREATE TABLE IF NOT EXISTS public.image_assets (
    image_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name VARCHAR(255) NOT NULL CHECK (btrim(name) <> ''),
    mime_type VARCHAR(100) NOT NULL
        CHECK (mime_type IN ('image/png', 'image/jpeg')),
    image_data BYTEA NOT NULL CHECK (octet_length(image_data) > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS public.template_version_images (
    image_binding_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    template_version_id INTEGER NOT NULL
        REFERENCES public.template_versions (template_version_id) ON DELETE RESTRICT,
    placeholder_name VARCHAR(100) NOT NULL CHECK (btrim(placeholder_name) <> ''),
    image_id INTEGER NOT NULL
        REFERENCES public.image_assets (image_id) ON DELETE RESTRICT,
    width_mm NUMERIC(10, 2) CHECK (width_mm > 0 AND width_mm <> 'NaN'::numeric),
    height_mm NUMERIC(10, 2) CHECK (height_mm > 0 AND height_mm <> 'NaN'::numeric),
    CONSTRAINT template_version_images_placeholder_key
        UNIQUE (template_version_id, placeholder_name)
);

CREATE INDEX IF NOT EXISTS template_version_images_image_id_idx
    ON public.template_version_images (image_id);

CREATE TABLE IF NOT EXISTS public.template_layout_versions (
    layout_version_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code VARCHAR(100) NOT NULL CHECK (btrim(code) <> ''),
    name VARCHAR(255) NOT NULL CHECK (btrim(name) <> ''),
    version_number INTEGER NOT NULL CHECK (version_number > 0),
    content_html TEXT NOT NULL
        CONSTRAINT template_layout_versions_html_check CHECK (btrim(content_html) <> ''),
    page_settings JSONB NOT NULL DEFAULT '{}'::jsonb
        CONSTRAINT template_layout_versions_page_settings_check
        CHECK (jsonb_typeof(page_settings) = 'object'),
    style_config JSONB NOT NULL DEFAULT '{}'::jsonb
        CONSTRAINT template_layout_versions_style_config_check
        CHECK (jsonb_typeof(style_config) = 'object'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (code, version_number)
);

ALTER TABLE public.template_versions
    ADD COLUMN IF NOT EXISTS layout_version_id INTEGER
        REFERENCES public.template_layout_versions (layout_version_id) ON DELETE RESTRICT;

CREATE TABLE IF NOT EXISTS public.template_blocks (
    block_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code VARCHAR(100) NOT NULL UNIQUE CHECK (btrim(code) <> ''),
    name VARCHAR(255) NOT NULL CHECK (btrim(name) <> ''),
    block_type VARCHAR(10) NOT NULL CHECK (block_type IN ('header', 'body', 'footer')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (block_id, block_type)
);

CREATE TABLE IF NOT EXISTS public.template_block_versions (
    block_version_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    block_id INTEGER NOT NULL,
    block_type VARCHAR(10) NOT NULL,
    version_number INTEGER NOT NULL CHECK (version_number > 0),
    content_html TEXT NOT NULL
        CONSTRAINT template_block_versions_html_check CHECK (btrim(content_html) <> ''),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (block_id, block_type)
        REFERENCES public.template_blocks (block_id, block_type) ON DELETE RESTRICT,
    UNIQUE (block_id, version_number),
    UNIQUE (block_version_id, block_type)
);

CREATE TABLE IF NOT EXISTS public.template_version_blocks (
    template_version_id INTEGER NOT NULL
        REFERENCES public.template_versions (template_version_id) ON DELETE RESTRICT,
    block_version_id INTEGER NOT NULL,
    block_type VARCHAR(10) NOT NULL,
    position INTEGER NOT NULL CHECK (position > 0),
    FOREIGN KEY (block_version_id, block_type)
        REFERENCES public.template_block_versions (block_version_id, block_type)
        ON DELETE RESTRICT,
    PRIMARY KEY (template_version_id, block_type, position),
    CHECK (block_type = 'body' OR position = 1)
);

CREATE INDEX IF NOT EXISTS template_version_blocks_block_version_idx
    ON public.template_version_blocks (block_version_id, block_type);

CREATE INDEX IF NOT EXISTS template_versions_layout_version_idx
    ON public.template_versions (layout_version_id);

ALTER TABLE public.template_versions
    ADD COLUMN IF NOT EXISTS storage_mode VARCHAR(10) NOT NULL DEFAULT 'file'
        CONSTRAINT template_versions_storage_mode_check
        CHECK (storage_mode IN ('file', 'blocks'));

ALTER TABLE public.template_versions
    DROP CONSTRAINT template_versions_content_check,
    ADD CONSTRAINT template_versions_content_check CHECK (
        (
            storage_mode = 'file'
            AND layout_version_id IS NULL
            AND (
                (template_format = 'text'
                 AND template_text IS NOT NULL AND template_file IS NULL)
                OR
                (template_format = 'docx'
                 AND template_text IS NULL AND template_file IS NOT NULL
                 AND octet_length(template_file) > 0)
            )
        )
        OR
        (
            storage_mode = 'blocks'
            AND template_format = 'docx'
            AND layout_version_id IS NOT NULL
            AND template_text IS NULL
            AND template_file IS NULL
        )
    );

INSERT INTO public.templates (code, name, description)
VALUES (
    'customer_details',
    'Customer Details',
    'Basic customer information and the current date'
)
ON CONFLICT (code) DO NOTHING;

INSERT INTO public.template_versions (
    template_id, version_number, status, template_format,
    template_text, change_note, published_at
)
SELECT template_id,
    1,
    'published',
    'text',
    'CUSTOMER DETAILS

Customer name: {{first_name}}
Customer surname: {{surname}}
Date: {{current_date}}',
    'Initial template',
    CURRENT_TIMESTAMP
FROM public.templates
WHERE code = 'customer_details'
ON CONFLICT (template_id, version_number) DO NOTHING;

COMMIT;
