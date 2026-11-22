BEGIN;

CREATE OR REPLACE FUNCTION public.assemble_composition(
    p_layout_version_id INTEGER,
    p_blocks JSONB
)
RETURNS TABLE (html_template TEXT, page_settings JSONB, style_config JSONB)
LANGUAGE plpgsql
STABLE
AS $function$
DECLARE
    selected_template RECORD;
    region_name TEXT;
    marker TEXT;
    marker_count INTEGER;
BEGIN
    IF p_layout_version_id IS NULL OR p_layout_version_id <= 0 THEN
        RAISE EXCEPTION 'Layout version ID must be a positive integer.' USING ERRCODE = '22023';
    END IF;
    IF jsonb_typeof(p_blocks) IS DISTINCT FROM 'array' THEN
        RAISE EXCEPTION 'Blocks must be a JSON array.' USING ERRCODE = '22023';
    END IF;
    IF jsonb_array_length(p_blocks) = 0 THEN
        RAISE EXCEPTION 'A composition needs at least one body block.' USING ERRCODE = '22023';
    END IF;
    IF EXISTS (
        SELECT 1 FROM jsonb_array_elements(p_blocks) AS item
        WHERE jsonb_typeof(item) IS DISTINCT FROM 'object'
           OR jsonb_typeof(item -> 'block_version_id') IS DISTINCT FROM 'number'
           OR jsonb_typeof(item -> 'block_type') IS DISTINCT FROM 'string'
           OR jsonb_typeof(item -> 'position') IS DISTINCT FROM 'number'
           OR item - ARRAY['block_version_id', 'block_type', 'position'] <> '{}'::jsonb
    ) THEN
        RAISE EXCEPTION 'Each block must specify a numeric version ID, a type, and a numeric position.'
            USING ERRCODE = '22023';
    END IF;
    IF EXISTS (
        SELECT 1
        FROM jsonb_to_recordset(p_blocks) AS binding(block_version_id INTEGER, block_type TEXT, position INTEGER)
        WHERE binding.block_version_id <= 0 OR binding.position <= 0
           OR binding.block_type NOT IN ('header', 'body', 'footer')
           OR (binding.block_type <> 'body' AND binding.position <> 1)
    ) OR EXISTS (
        SELECT 1
        FROM jsonb_to_recordset(p_blocks) AS binding(block_version_id INTEGER, block_type TEXT, position INTEGER)
        GROUP BY binding.block_type, binding.position HAVING count(*) > 1
    ) THEN
        RAISE EXCEPTION 'Block types and positions must follow the composition rules.' USING ERRCODE = '22023';
    END IF;

    -- Read the layout and requested block versions from one statement snapshot.
    SELECT layout.layout_version_id,
           layout.content_html AS layout_html,
           layout.page_settings,
           layout.style_config,
           blocks.*
    INTO selected_template
    FROM public.template_layout_versions AS layout
    LEFT JOIN LATERAL (
        SELECT count(*) FILTER (WHERE binding.block_type = 'body') AS body_count,
               count(*) <> count(block.block_version_id) AS has_missing_blocks,
               string_agg(block.content_html, E'\n' ORDER BY binding.position)
                   FILTER (WHERE binding.block_type = 'header') AS header_html,
               string_agg(block.content_html, E'\n' ORDER BY binding.position)
                   FILTER (WHERE binding.block_type = 'body') AS body_html,
               string_agg(block.content_html, E'\n' ORDER BY binding.position)
                   FILTER (WHERE binding.block_type = 'footer') AS footer_html,
               bool_or(block.content_html ~ '<!--[[:space:]]*slot:') AS has_reserved_markers,
               bool_or(btrim(block.content_html, E' \t\n\r\f') = '') AS has_blank_blocks
        FROM jsonb_to_recordset(p_blocks) AS binding(block_version_id INTEGER, block_type TEXT, position INTEGER)
        LEFT JOIN public.template_block_versions AS block
            ON block.block_version_id = binding.block_version_id AND block.block_type = binding.block_type
    ) AS blocks ON TRUE
    WHERE layout.layout_version_id = p_layout_version_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Layout version % was not found.', p_layout_version_id USING ERRCODE = 'P0002';
    END IF;
    IF selected_template.has_missing_blocks THEN
        RAISE EXCEPTION 'A selected block version is missing or has the wrong type.' USING ERRCODE = '22023';
    END IF;
    IF selected_template.body_count = 0 THEN
        RAISE EXCEPTION 'A composition needs at least one body block.'
            USING ERRCODE = '22023';
    END IF;
    IF selected_template.has_blank_blocks THEN
        RAISE EXCEPTION 'The composition contains a blank block.'
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
    RETURN NEXT;
END;
$function$;

CREATE OR REPLACE PROCEDURE public.assemble_template(
    IN p_template_version_id INTEGER,
    OUT html_template TEXT,
    OUT page_settings JSONB,
    OUT style_config JSONB
)
LANGUAGE plpgsql
AS $procedure$
DECLARE
    selected_storage_mode TEXT;
BEGIN
    IF p_template_version_id IS NULL OR p_template_version_id <= 0 THEN
        RAISE EXCEPTION 'Template version ID must be a positive integer.' USING ERRCODE = '22023';
    END IF;
    SELECT storage_mode INTO selected_storage_mode
    FROM public.template_versions WHERE template_version_id = p_template_version_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Template version % was not found.', p_template_version_id USING ERRCODE = 'P0002';
    END IF;
    IF selected_storage_mode <> 'blocks' THEN
        RAISE EXCEPTION 'Template version % does not use block storage.', p_template_version_id USING ERRCODE = '22023';
    END IF;

    -- Saved versions and unsaved previews share the read-only assembly core.
    SELECT assembled.html_template, assembled.page_settings, assembled.style_config
    INTO html_template, page_settings, style_config
    FROM public.template_versions AS version
    LEFT JOIN LATERAL (
        SELECT coalesce(jsonb_agg(jsonb_build_object(
            'block_version_id', binding.block_version_id,
            'block_type', binding.block_type,
            'position', binding.position
        )), '[]'::jsonb) AS blocks
        FROM public.template_version_blocks AS binding
        WHERE binding.template_version_id = version.template_version_id
    ) AS composition ON TRUE
    LEFT JOIN LATERAL public.assemble_composition(version.layout_version_id, composition.blocks) AS assembled ON TRUE
    WHERE version.template_version_id = p_template_version_id AND version.storage_mode = 'blocks';
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Template version % is no longer available for assembly.', p_template_version_id
            USING ERRCODE = 'P0002';
    END IF;
END;
$procedure$;

COMMIT;
