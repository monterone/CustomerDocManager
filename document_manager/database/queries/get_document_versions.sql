SELECT version.template_version_id, version.template_id, template.name, template.code,
       version.version_number, version.status, version.storage_mode, version.template_format,
       layout.name AS layout_name, layout.version_number AS layout_version_number
FROM public.template_versions AS version
JOIN public.templates AS template USING (template_id)
LEFT JOIN public.template_layout_versions AS layout USING (layout_version_id)
WHERE template.is_archived = FALSE
  AND version.status IN ('draft', 'published')
ORDER BY template.name, template.template_id, version.version_number DESC;
