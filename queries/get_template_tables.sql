SELECT placeholder_name, columns_config, style, source_key
FROM public.template_version_tables
WHERE template_version_id = %s
ORDER BY placeholder_name;
