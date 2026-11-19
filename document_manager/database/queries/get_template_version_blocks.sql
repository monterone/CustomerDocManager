SELECT binding.block_type, binding.position, block.name,
       version.version_number
FROM public.template_version_blocks AS binding
JOIN public.template_block_versions AS version
    ON version.block_version_id = binding.block_version_id
JOIN public.template_blocks AS block ON block.block_id = version.block_id
WHERE binding.template_version_id = %s
ORDER BY CASE binding.block_type
             WHEN 'header' THEN 1 WHEN 'body' THEN 2 ELSE 3 END,
         binding.position;
