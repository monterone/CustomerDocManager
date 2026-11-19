"""Format-independent HTML structure and page settings for document exporters."""

from dataclasses import dataclass, field
from html.parser import HTMLParser
from math import isfinite


DEFAULT_PAGE_SETTINGS = {
    "page_width_mm": 210,
    "page_height_mm": 297,
    "margin_top_mm": 25,
    "margin_bottom_mm": 25,
    "margin_left_mm": 25,
    "margin_right_mm": 25,
    "header_distance_mm": 10,
    "footer_distance_mm": 10,
}

_BLOCKS = {"p", "h1", "h2", "h3"}
_INLINE = {"strong", "b", "em", "i", "u", "br", "span", "img"}
_VOID = {"meta", "br", "img"}
_CHILDREN = {
    "document": {"html"},
    "html": {"head", "body"},
    "head": {"meta"},
    "body": {"header", "main", "footer"},
    "header": _BLOCKS | {"table", "img"},
    "main": _BLOCKS | {"table", "img"},
    "footer": _BLOCKS | {"table", "img"},
    "table": {"thead", "tbody", "tr"},
    "thead": {"tr"},
    "tbody": {"tr"},
    "tr": {"th", "td"},
    "th": _INLINE | {"p"},
    "td": _INLINE | {"p"},
    **{tag: _INLINE for tag in _BLOCKS | {"strong", "b", "em", "i", "u"}},
    "span": set(),
    "br": set(),
    "meta": set(),
    "img": set(),
}
ALIGNMENT_NAMES = frozenset({"left", "center", "right", "justify"})


@dataclass
class HtmlElement:
    """One format-independent HTML node with attributes and ordered children."""

    tag: str
    attrs: dict = field(default_factory=dict)
    children: list = field(default_factory=list)


class _Parser(HTMLParser):

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = HtmlElement("document")
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        if tag not in _CHILDREN:
            raise ValueError(f"Unsupported HTML element: <{tag}>.")
        if tag not in _CHILDREN[self.stack[-1].tag]:
            raise ValueError(f"Element <{tag}> is not allowed inside <{self.stack[-1].tag}>.")
        attributes = dict(attrs)
        if len(attributes) != len(attrs):
            raise ValueError(f"Duplicate attributes on <{tag}>.")
        allowed = set()
        if tag in _BLOCKS:
            allowed = {"data-align"}
            if attributes.get("data-align", "left") not in ALIGNMENT_NAMES:
                raise ValueError("Paragraph alignment must be left, center, right, or justify.")
        elif tag == "meta":
            allowed = {"charset"}
            if (attributes.get("charset") or "").lower() != "utf-8":
                raise ValueError("Only <meta charset='utf-8'> is supported.")
        elif tag in {"header", "main", "footer"}:
            allowed = {"data-region"}
            role = "body" if tag == "main" else tag
            if attributes.get("data-region", role) != role:
                raise ValueError(f"Invalid data-region for <{tag}>.")
        elif tag == "span":
            allowed = {"data-field"}
            if attributes.get("data-field") != "page-number":
                raise ValueError("Only the page-number field is supported in <span>.")
            if not any(node.tag in {"header", "footer"} for node in self.stack):
                raise ValueError("Page-number fields must be in a header or footer.")
        elif tag == "img":
            allowed = {"src", "alt", "data-width-mm", "data-height-mm"}
            source = attributes.get("src") or ""
            if not source.startswith("asset:") or not source[6:].strip():
                raise ValueError("Images must use a non-empty internal asset: reference.")
            if "alt" in attributes and attributes["alt"] is None:
                raise ValueError("Image alt text must have a value.")
        if attributes.keys() - allowed:
            raise ValueError(f"Unsupported attributes on <{tag}>.")
        if len(self.stack) >= 32:
            raise ValueError("HTML nesting is too deep.")
        element = HtmlElement(tag, attributes)
        self.stack[-1].children.append(element)
        if tag not in _VOID:
            self.stack.append(element)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in _VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if len(self.stack) == 1 or self.stack[-1].tag != tag:
            raise ValueError(f"Unexpected closing tag: </{tag}>.")
        self.stack.pop()

    def handle_data(self, data):
        parent = self.stack[-1]
        if parent.tag not in _BLOCKS | {"strong", "b", "em", "i", "u", "th", "td"}:
            if data.strip():
                raise ValueError(f"Text is not allowed directly inside <{parent.tag}>.")
            return
        parent.children.append(data)

    def handle_decl(self, decl):
        if decl.lower() != "doctype html" or self.root.children:
            raise ValueError("Only an initial HTML doctype is supported.")

    def handle_pi(self, data):
        raise ValueError("Processing instructions are not supported.")

    def unknown_decl(self, data):
        raise ValueError("Unsupported HTML declaration.")

    def regions(self):
        if len(self.stack) != 1:
            raise ValueError(f"Unclosed HTML element: <{self.stack[-1].tag}>.")
        if len(self.root.children) != 1:
            raise ValueError("Exactly one <html> document is required.")
        html = self.root.children[0]
        tags = [node.tag for node in html.children]
        if tags not in (["body"], ["head", "body"]):
            raise ValueError("Expected an optional <head> followed by one <body>.")
        body = html.children[-1]
        result = {}
        for region in body.children:
            if region.tag in result:
                raise ValueError(f"Duplicate <{region.tag}> region.")
            result[region.tag] = region
        if "main" not in result:
            raise ValueError("Exactly one <main> region is required.")
        for region in result.values():
            for element in region.children:
                if element.tag == "table":
                    get_table_rows(element)
        return result


def get_table_rows(table):
    """Validate rectangular table structure and return its rows in source order."""
    tags = [child.tag for child in table.children]
    if "tr" in tags and any(tag != "tr" for tag in tags):
        raise ValueError("A table cannot mix direct rows and row groups.")
    groups = [tag for tag in tags if tag != "tr"]
    if groups not in ([], ["thead"], ["tbody"], ["thead", "tbody"]):
        raise ValueError("Expected at most one thead followed by at most one tbody.")
    rows = []
    for child in table.children:
        if child.tag == "thead":
            if len(child.children) != 1 or any(cell.tag != "th" for cell in child.children[0].children):
                raise ValueError("Thead must contain one row of th cells.")
        rows.extend([child] if child.tag == "tr" else child.children)
    if not rows or not rows[0].children:
        raise ValueError("A table needs at least one row with cells to define its columns.")
    columns = len(rows[0].children)
    for row in rows:
        if len(row.children) != columns:
            raise ValueError("Table rows must have the same number of cells.")
        for cell in row.children:
            paragraphs = [node for node in cell.children if isinstance(node, HtmlElement) and node.tag == "p"]
            if paragraphs and any(
                (isinstance(node, str) and node.strip()) or
                (isinstance(node, HtmlElement) and node.tag != "p")
                for node in cell.children
            ):
                raise ValueError("A cell must contain either paragraphs or inline content, not both.")
    return rows


def validate_page_settings(settings):
    """Merge page defaults and validate dimensions in millimetres."""
    if settings is None:
        settings = {}
    if not isinstance(settings, dict):
        raise ValueError("Page settings must be a dictionary.")
    if settings.keys() - DEFAULT_PAGE_SETTINGS.keys():
        raise ValueError("Unknown page setting.")
    result = {}
    for key, value in (DEFAULT_PAGE_SETTINGS | settings).items():
        try:
            number = float(value)
        except (TypeError, ValueError, OverflowError) as error:
            raise ValueError(f"Invalid page setting: {key}.") from error
        if isinstance(value, bool) or not isfinite(number) or number < 0:
            raise ValueError(f"Page setting {key} must be a finite non-negative number.")
        result[key] = number
    if result["page_width_mm"] <= result["margin_left_mm"] + result["margin_right_mm"]:
        raise ValueError("Page margins leave no body width.")
    if result["page_height_mm"] <= result["margin_top_mm"] + result["margin_bottom_mm"]:
        raise ValueError("Page margins leave no body height.")
    for region, margin in (("header", "top"), ("footer", "bottom")):
        if result[f"{region}_distance_mm"] > result[f"margin_{margin}_mm"]:
            raise ValueError(f"The {region} distance exceeds its page margin.")
    return result


def parse_html_document(html):
    """Validate supported HTML and return header/main/footer element trees."""
    if not isinstance(html, str) or not html.strip():
        raise ValueError("HTML must be a non-empty string.")
    parser = _Parser()
    parser.feed(html)
    parser.close()
    return parser.regions()


def iter_inline_tokens(element, bold=False, italic=False, underline=False):
    """Yield inline content and inherited formatting for any document exporter."""
    bold = bold or element.tag in {"strong", "b"}
    italic = italic or element.tag in {"em", "i"}
    underline = underline or element.tag == "u"
    if element.tag in {"br", "span"}:
        yield (element.tag, "", bold, italic, underline)
    elif element.tag == "img":
        yield ("img", element.attrs, bold, italic, underline)
    for child in element.children:
        if isinstance(child, str):
            yield ("text", child, bold, italic, underline)
        else:
            yield from iter_inline_tokens(child, bold, italic, underline)
