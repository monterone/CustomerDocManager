SELECT placeholder_name, columns_config, style, query_config
FROM public.template_version_tables
WHERE template_version_id = %s
ORDER BY placeholder_name;
