SELECT a.attname AS column_name
FROM pg_catalog.pg_constraint AS constraint_info
JOIN pg_catalog.pg_class AS t ON t.oid = constraint_info.conrelid
JOIN pg_catalog.pg_namespace AS n ON n.oid = t.relnamespace
CROSS JOIN LATERAL unnest(constraint_info.conkey)
    WITH ORDINALITY AS key_column(attribute_number, position)
JOIN pg_catalog.pg_attribute AS a
  ON a.attrelid = t.oid AND a.attnum = key_column.attribute_number
WHERE n.nspname = %s
  AND t.relname = %s
  AND constraint_info.contype = 'p'
ORDER BY key_column.position;
