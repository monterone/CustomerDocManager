from database import get_customer_list, get_template_tables


SOURCE_LOADERS = {
    "customer_list": get_customer_list,
}


def build_table_context(template_version_id):
    settings = get_template_tables(template_version_id)
    tables = {}

    for setting in settings:
        source_key = setting["source_key"]
        if source_key not in SOURCE_LOADERS:
            raise ValueError(f"Unsupported table data source: {source_key}")

        rows = SOURCE_LOADERS[source_key]()
        tables[setting["placeholder_name"]] = {
            "columns": setting["columns_config"],
            "rows": rows,
            "style": setting["style"],
        }

    return tables
