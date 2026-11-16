SELECT binding.placeholder_name, binding.width_mm, binding.height_mm,
       asset.image_data, asset.mime_type
FROM public.template_version_images AS binding
JOIN public.image_assets AS asset ON asset.image_id = binding.image_id
WHERE binding.template_version_id = %s
ORDER BY binding.placeholder_name;
