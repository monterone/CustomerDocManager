SELECT setting.table_id, setting.placeholder_name, setting.columns_config,
       setting.query_config, setting.style, template.name AS template_name,
       version.version_number, version.template_version_id
FROM public.template_version_tables AS setting
JOIN public.template_versions AS version USING (template_version_id)
JOIN public.templates AS template USING (template_id)
WHERE template.is_archived = FALSE AND setting.query_config IS NOT NULL
ORDER BY setting.placeholder_name, template.name, version.version_number DESC;
