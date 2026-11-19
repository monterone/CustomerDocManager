from psycopg import sql
from psycopg.rows import dict_row

from document_manager.database.connection import get_connection
from document_manager.database.metadata import validate_table_request


def fetch_table_rows(table_definition, document_context=None):
    metadata = validate_table_request(table_definition, document_context)
    source = metadata["source"]
    fields = sql.SQL(", ").join(
        sql.Identifier(column["field"]) for column in table_definition["columns"]
    )
    query = sql.SQL("SELECT {} FROM {}").format(
        fields, sql.Identifier(source["schema"], source["table"])
    )
    parameters = []

    relation = metadata["relation"]
    if relation is not None:
        conditions = []
        for source_field, context_field in zip(
            relation["columns"], relation["referenced_columns"]
        ):
            conditions.append(sql.SQL("{} = %s").format(sql.Identifier(source_field)))
            parameters.append(document_context["key"][context_field])
        query += sql.SQL(" WHERE ") + sql.SQL(" AND ").join(conditions)

    order_by = table_definition.get("order_by", [])
    if order_by:
        ordering = [
            sql.SQL("{} {}").format(
                sql.Identifier(item["field"]), sql.SQL(item["direction"].upper())
            )
            for item in order_by
        ]
        query += sql.SQL(" ORDER BY ") + sql.SQL(", ").join(ordering)

    with get_connection() as connection:
        connection.read_only = True
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(query, parameters)
            return cursor.fetchall()
