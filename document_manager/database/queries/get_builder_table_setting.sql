SELECT columns_config, query_config, style
FROM public.template_version_tables
WHERE table_id = %s AND query_config IS NOT NULL;
