CREATE OR REPLACE PROCEDURE public.assemble_template(
    IN p_template_version_id INTEGER,
    OUT html_template TEXT,
    OUT page_settings JSONB,
    OUT style_config JSONB
)
LANGUAGE plpgsql
AS $procedure$
DECLARE
    selected_template RECORD;
    region_name TEXT;
    marker TEXT;
    marker_count INTEGER;
BEGIN
    IF p_template_version_id IS NULL OR p_template_version_id <= 0 THEN
        RAISE EXCEPTION 'Template version ID must be a positive integer.'
            USING ERRCODE = '22023';
    END IF;

    -- Read the layout and all pinned block versions from one statement snapshot.
    SELECT version.storage_mode,
           layout.layout_version_id,
           layout.content_html AS layout_html,
           layout.page_settings,
           layout.style_config,
           blocks.*
    INTO selected_template
    FROM public.template_versions AS version
    LEFT JOIN public.template_layout_versions AS layout
        ON layout.layout_version_id = version.layout_version_id
    LEFT JOIN LATERAL (
        SELECT count(*) FILTER (WHERE binding.block_type = 'body') AS body_count,
               string_agg(block.content_html, E'\n' ORDER BY binding.position)
                   FILTER (WHERE binding.block_type = 'header') AS header_html,
               string_agg(block.content_html, E'\n' ORDER BY binding.position)
                   FILTER (WHERE binding.block_type = 'body') AS body_html,
               string_agg(block.content_html, E'\n' ORDER BY binding.position)
                   FILTER (WHERE binding.block_type = 'footer') AS footer_html,
               bool_or(block.content_html ~ '<!--[[:space:]]*slot:') AS has_reserved_markers,
               bool_or(btrim(block.content_html, E' \t\n\r\f') = '') AS has_blank_blocks
        FROM public.template_version_blocks AS binding
        JOIN public.template_block_versions AS block
            ON block.block_version_id = binding.block_version_id
           AND block.block_type = binding.block_type
        WHERE binding.template_version_id = version.template_version_id
    ) AS blocks ON TRUE
    WHERE version.template_version_id = p_template_version_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Template version % was not found.', p_template_version_id
            USING ERRCODE = 'P0002';
    END IF;
    IF selected_template.storage_mode <> 'blocks' THEN
        RAISE EXCEPTION 'Template version % does not use block storage.', p_template_version_id
            USING ERRCODE = '22023';
    END IF;
    IF selected_template.layout_version_id IS NULL THEN
        RAISE EXCEPTION 'Template version % has no layout.', p_template_version_id
            USING ERRCODE = '22023';
    END IF;
    IF selected_template.body_count = 0 THEN
        RAISE EXCEPTION 'Template version % needs at least one body block.', p_template_version_id
            USING ERRCODE = '22023';
    END IF;
    IF selected_template.has_blank_blocks THEN
        RAISE EXCEPTION 'Template version % contains a blank block.', p_template_version_id
            USING ERRCODE = '22023';
    END IF;
    IF selected_template.has_reserved_markers THEN
        RAISE EXCEPTION 'Layout slot markers are not allowed inside blocks.'
            USING ERRCODE = '22023';
    END IF;

    FOREACH region_name IN ARRAY ARRAY['header', 'body', 'footer'] LOOP
        marker := '<!-- slot:' || region_name || ' -->';
        marker_count := (
            char_length(selected_template.layout_html)
            - char_length(replace(selected_template.layout_html, marker, ''))
        ) / char_length(marker);
        IF marker_count <> 1 THEN
            RAISE EXCEPTION 'Layout must contain exactly one % marker.', marker
                USING ERRCODE = '22023';
        END IF;
    END LOOP;
    IF regexp_replace(selected_template.layout_html,
                      '<!-- slot:(header|body|footer) -->', '', 'g')
       ~ '<!--[[:space:]]*slot:' THEN
        RAISE EXCEPTION 'Layout contains an unknown or malformed slot marker.'
            USING ERRCODE = '22023';
    END IF;

    html_template := replace(selected_template.layout_html, '<!-- slot:header -->',
        '<header>' || coalesce(selected_template.header_html, '') || '</header>');
    html_template := replace(html_template, '<!-- slot:body -->',
        '<main>' || selected_template.body_html || '</main>');
    html_template := replace(html_template, '<!-- slot:footer -->',
        '<footer>' || coalesce(selected_template.footer_html, '') || '</footer>');
    page_settings := selected_template.page_settings;
    style_config := selected_template.style_config;
END;
$procedure$;
