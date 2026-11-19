SELECT version.template_version_id, template.name, template.code,
       version.version_number, version.status,
       layout.name AS layout_name, layout.version_number AS layout_version_number
FROM public.template_versions AS version
JOIN public.templates AS template ON template.template_id = version.template_id
JOIN public.template_layout_versions AS layout
    ON layout.layout_version_id = version.layout_version_id
WHERE version.storage_mode = 'blocks'
  AND version.status IN ('draft', 'published')
  AND template.is_archived = FALSE
ORDER BY template.name, version.version_number DESC;
