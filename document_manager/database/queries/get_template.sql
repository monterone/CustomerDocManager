SELECT v.template_text,
       v.version_number AS version,
       v.template_format,
       v.template_file,
       v.template_version_id
FROM public.templates AS t
JOIN public.template_versions AS v ON v.template_id = t.template_id
WHERE t.code = %s
  AND t.is_archived = FALSE
  AND v.status = 'published';
