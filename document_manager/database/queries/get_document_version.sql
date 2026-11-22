SELECT version.template_version_id, version.storage_mode, version.template_format,
       version.template_text, version.template_file
FROM public.template_versions AS version
JOIN public.templates AS template USING (template_id)
WHERE version.template_version_id = %s
  AND template.is_archived = FALSE
  AND version.status IN ('draft', 'published');
