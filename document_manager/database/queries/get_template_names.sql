SELECT t.code
FROM public.templates AS t
JOIN public.template_versions AS v ON v.template_id = t.template_id
WHERE t.is_archived = FALSE
  AND v.status = 'published'
ORDER BY t.code;
