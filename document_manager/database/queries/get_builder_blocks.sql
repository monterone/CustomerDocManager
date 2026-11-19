SELECT version.block_version_id, version.block_id, version.block_type,
       version.version_number, version.content_html, block.name, block.code
FROM public.template_block_versions AS version
JOIN public.template_blocks AS block ON block.block_id = version.block_id
ORDER BY block.name, version.version_number DESC;
