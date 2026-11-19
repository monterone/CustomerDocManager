SELECT layout_version_id, code, name, version_number, content_html,
       page_settings, style_config
FROM public.template_layout_versions
ORDER BY name, version_number DESC;
