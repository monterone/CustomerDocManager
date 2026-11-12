SELECT DISTINCT name
FROM public.document_templates
WHERE is_active = TRUE
ORDER BY name;
