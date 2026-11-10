"""Named placeholder substitution in text templates."""

import re


def render_template(template_text, values):
    pattern = r"{{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*}}"

    placeholders = set(re.findall(pattern, template_text))
    missing = placeholders - values.keys()

    if missing:
        raise ValueError(
            f"Нет данных для полей: {', '.join(sorted(missing))}"
        )

    return re.sub(
        pattern,
        lambda match: str(values[match.group(1)]),
        template_text,
    )
