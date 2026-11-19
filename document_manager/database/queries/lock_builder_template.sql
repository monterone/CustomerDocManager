SELECT template_id FROM public.templates
WHERE template_id = %s AND is_archived = FALSE
FOR UPDATE;
