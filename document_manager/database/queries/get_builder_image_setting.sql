SELECT binding.width_mm, binding.height_mm, asset.image_data, asset.mime_type
FROM public.template_version_images AS binding
JOIN public.image_assets AS asset USING (image_id)
WHERE binding.image_binding_id = %s;
