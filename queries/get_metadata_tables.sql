SELECT t.relname AS table_name
FROM pg_catalog.pg_class AS t
JOIN pg_catalog.pg_namespace AS n ON n.oid = t.relnamespace
WHERE n.nspname = %s
  AND t.relkind IN ('r', 'p')
  AND pg_catalog.has_table_privilege(t.oid, 'SELECT')
ORDER BY t.relname;
