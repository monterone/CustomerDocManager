SELECT binding.image_binding_id, binding.placeholder_name, asset.name AS image_name,
       binding.width_mm, binding.height_mm, template.name AS template_name,
       version.version_number, version.template_version_id
FROM public.template_version_images AS binding
JOIN public.image_assets AS asset USING (image_id)
JOIN public.template_versions AS version USING (template_version_id)
JOIN public.templates AS template USING (template_id)
WHERE template.is_archived = FALSE
ORDER BY binding.placeholder_name, template.name, version.version_number DESC;
