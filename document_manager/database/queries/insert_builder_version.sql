INSERT INTO public.template_versions
    (template_id, version_number, status, template_format, storage_mode,
     layout_version_id, change_note)
SELECT %s, COALESCE(MAX(version_number), 0) + 1,
       'draft', 'docx', 'blocks', %s, 'Created with the block template builder'
FROM public.template_versions
WHERE template_id = %s
RETURNING template_version_id, template_id, version_number;
