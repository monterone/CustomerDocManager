INSERT INTO public.template_version_tables
    (template_version_id, placeholder_name, columns_config, query_config, style)
SELECT %s, %s, columns_config, query_config, style
FROM public.template_version_tables
WHERE table_id = %s AND query_config IS NOT NULL
RETURNING placeholder_name, columns_config, query_config, style;
