SELECT template_text, version, template_format, template_file
FROM public.document_templates
WHERE name = %s AND is_active = TRUE
ORDER BY version DESC
LIMIT 1;
