from html import escape
from html.parser import HTMLParser
from math import isfinite
import re


_PLACEHOLDER = re.compile(r"{{(.*?)}}", re.DOTALL)
_FIELD_NAME = re.compile(r"[a-zA-Z_][a-zA-Z0-9_]*")


def _scalar_text(value):
    if value is None or (isinstance(value, str) and not value.strip()):
        value = "None"
    return escape(str(value), quote=True)


def render_html_table(columns, rows, style="Table Grid"):
    if not isinstance(columns, list) or not columns:
        raise ValueError("At least one output column is required.")
    if not isinstance(rows, list):
        raise ValueError("Table rows must be a list of dictionaries.")
    if style != "Table Grid":
        raise ValueError("HTML tables currently support only the Table Grid style.")
    for column in columns:
        if not isinstance(column, dict) or not isinstance(column.get("key"), str) or not column["key"].strip():
            raise ValueError("Each column must have a non-empty string key.")
        if not isinstance(column.get("title"), str):
            raise ValueError("Each column must have a string title.")
    parts = ["<table><thead><tr>"]
    parts.extend(f'<th>{escape(column["title"], quote=True)}</th>' for column in columns)
    parts.append("</tr></thead><tbody>")
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Each table row must be a dictionary.")
        parts.append("<tr>")
        parts.extend(f'<td>{_scalar_text(row.get(column["key"]))}</td>' for column in columns)
        parts.append("</tr>")
    parts.append("</tbody></table>")
    return "".join(parts)


def render_html_image(name, definition):
    if not isinstance(name, str) or not _FIELD_NAME.fullmatch(name):
        raise ValueError("Image placeholder names must be valid field names.")
    if not isinstance(definition, dict):
        raise ValueError(f"Image '{name}' must have a dictionary definition.")
    attributes = [f'src="asset:{name}"', f'alt="{name}"']
    for dimension in ("width", "height"):
        value = definition.get(f"{dimension}_mm")
        if value is None:
            continue
        try:
            size = float(value)
        except (TypeError, ValueError, OverflowError) as error:
            raise ValueError(f"Invalid {dimension} for image '{name}'.") from error
        if isinstance(value, bool) or not isfinite(size) or size <= 0:
            raise ValueError(f"Image {dimension} must be a positive finite number.")
        attributes.append(f'data-{dimension}-mm="{size:.15g}"')
    return '<img ' + ' '.join(attributes) + '>'


class _ObjectPlacementParser(HTMLParser):
    def __init__(self, tables, images):
        super().__init__(convert_charrefs=False)
        self.stack = []
        self.tables = tables
        self.images = images
        self.counts = dict.fromkeys(tables.keys() | images.keys(), 0)

    def handle_starttag(self, tag, attrs):
        if tag not in {"meta", "br", "img", "hr", "input", "link"}:
            self.stack.append(tag)

    def handle_startendtag(self, tag, attrs):
        pass

    def handle_endtag(self, tag):
        if self.stack and self.stack[-1] == tag:
            self.stack.pop()

    def handle_data(self, data):
        matches = list(_PLACEHOLDER.finditer(data))
        names = [match.group(1).strip() for match in matches]
        objects = [name for name in names if name in self.counts]
        if not objects:
            return
        if any(name in self.tables for name in objects) and (
                not self.stack or self.stack[-1] not in {"header", "main", "footer"}
                or _PLACEHOLDER.sub("", data).strip()
                or any(name not in self.counts for name in names)):
            raise ValueError("Table placeholders must be standalone blocks directly in header, main, or footer.")
        if any(name in self.images for name in objects) and (
                not self.stack or self.stack[-1] not in {
                    "header", "main", "footer", "p", "h1", "h2", "h3",
                    "strong", "b", "em", "i", "u", "td", "th",
                }):
            raise ValueError("Image placeholders must be in a region, paragraph, or table cell.")
        for name in objects:
            self.counts[name] += 1


def render_html_template(template_html, values, tables=None, images=None):
    if not isinstance(template_html, str) or not template_html.strip():
        raise ValueError("The HTML template must be a non-empty string.")
    if not isinstance(values, dict):
        raise ValueError("Placeholder values must be a dictionary.")
    if tables is None:
        tables = {}
    if not isinstance(tables, dict):
        raise ValueError("Tables must be a dictionary keyed by placeholder names.")
    if images is None:
        images = {}
    if not isinstance(images, dict):
        raise ValueError("Images must be a dictionary keyed by placeholder names.")
    remainder = _PLACEHOLDER.sub("", template_html)
    if "{{" in remainder or "}}" in remainder:
        raise ValueError("The HTML template contains an unclosed placeholder.")
    if "{%" in template_html or "{#" in template_html:
        raise ValueError("Only named placeholders are supported in HTML templates.")

    matches = list(_PLACEHOLDER.finditer(template_html))
    names = [match.group(1).strip() for match in matches]
    for name in names:
        if not _FIELD_NAME.fullmatch(name):
            raise ValueError(f"Invalid placeholder: {name!r}.")
    for name in tables:
        if not isinstance(name, str) or not _FIELD_NAME.fullmatch(name):
            raise ValueError("Table placeholder names must be valid field names.")
        if name not in names:
            raise ValueError(f"Table placeholder not found in template: {name}.")
        if name in values:
            raise ValueError(f"Placeholder '{name}' cannot be both a scalar and a table.")
    for name in images:
        if not isinstance(name, str) or not _FIELD_NAME.fullmatch(name):
            raise ValueError("Image placeholder names must be valid field names.")
        if name not in names:
            raise ValueError(f"Image placeholder not found in template: {name}.")
        if name in values or name in tables:
            raise ValueError(f"Placeholder '{name}' cannot have multiple content types.")
    if tables or images:
        parser = _ObjectPlacementParser(tables, images)
        parser.feed(template_html)
        parser.close()
        if any(parser.counts[name] != names.count(name) for name in parser.counts):
            raise ValueError("Table and image placeholders cannot appear in attributes, comments, or tag names.")
    rendered_tables = {}
    for name, definition in tables.items():
        if not isinstance(definition, dict) or not {"columns", "rows"} <= definition.keys():
            raise ValueError(f"Table '{name}' must define columns and rows.")
        rendered_tables[name] = render_html_table(
            definition["columns"], definition["rows"], definition.get("style", "Table Grid")
        )
    rendered_images = {name: render_html_image(name, definition)
                       for name, definition in images.items()}

    def replace(match):
        name = match.group(1).strip()
        if name in rendered_tables:
            return rendered_tables[name]
        if name in rendered_images:
            return rendered_images[name]
        return _scalar_text(values.get(name))

    return _PLACEHOLDER.sub(replace, template_html)
