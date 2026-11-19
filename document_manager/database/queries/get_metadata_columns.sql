SELECT a.attname AS name,
       pg_catalog.format_type(a.atttypid, a.atttypmod) AS data_type,
       NOT a.attnotnull AS is_nullable
FROM pg_catalog.pg_attribute AS a
JOIN pg_catalog.pg_class AS t ON t.oid = a.attrelid
JOIN pg_catalog.pg_namespace AS n ON n.oid = t.relnamespace
WHERE n.nspname = %s
  AND t.relname = %s
  AND t.relkind IN ('r', 'p')
  AND a.attnum > 0
  AND NOT a.attisdropped
  AND pg_catalog.has_table_privilege(t.oid, 'SELECT')
ORDER BY a.attnum;
