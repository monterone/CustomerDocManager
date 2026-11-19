SELECT template_id, code, name
FROM public.templates
WHERE is_archived = FALSE
ORDER BY name, template_id;
