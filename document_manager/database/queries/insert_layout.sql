INSERT INTO public.template_layout_versions
    (code, name, version_number, content_html, page_settings, style_config)
VALUES (%s, %s, 1, %s, %s, '{}'::jsonb)
RETURNING layout_version_id, name, version_number;
