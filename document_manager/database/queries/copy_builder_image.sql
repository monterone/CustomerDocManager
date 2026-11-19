INSERT INTO public.template_version_images
    (template_version_id, placeholder_name, image_id, width_mm, height_mm)
SELECT %s, %s, image_id, width_mm, height_mm
FROM public.template_version_images
WHERE image_binding_id = %s
RETURNING image_id;
