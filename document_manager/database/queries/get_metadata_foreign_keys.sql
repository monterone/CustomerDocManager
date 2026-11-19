SELECT constraint_info.conname AS name,
       array_agg(source_column.attname ORDER BY key_pair.position) AS columns,
       target_namespace.nspname AS referenced_schema,
       target.relname AS referenced_table,
       array_agg(target_column.attname ORDER BY key_pair.position) AS referenced_columns
FROM pg_catalog.pg_constraint AS constraint_info
JOIN pg_catalog.pg_class AS source ON source.oid = constraint_info.conrelid
JOIN pg_catalog.pg_namespace AS source_namespace ON source_namespace.oid = source.relnamespace
JOIN pg_catalog.pg_class AS target ON target.oid = constraint_info.confrelid
JOIN pg_catalog.pg_namespace AS target_namespace ON target_namespace.oid = target.relnamespace
CROSS JOIN LATERAL unnest(constraint_info.conkey, constraint_info.confkey)
    WITH ORDINALITY AS key_pair(source_number, target_number, position)
JOIN pg_catalog.pg_attribute AS source_column
  ON source_column.attrelid = source.oid AND source_column.attnum = key_pair.source_number
JOIN pg_catalog.pg_attribute AS target_column
  ON target_column.attrelid = target.oid AND target_column.attnum = key_pair.target_number
WHERE source_namespace.nspname = %s
  AND source.relname = %s
  AND constraint_info.contype = 'f'
GROUP BY constraint_info.oid, constraint_info.conname,
         target_namespace.nspname, target.relname
ORDER BY constraint_info.conname;
