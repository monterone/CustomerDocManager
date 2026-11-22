"""Readable template names for user-facing selectors."""

from collections import Counter


def template_labels(templates):
    counts = Counter(item["name"] for item in templates.values())
    return {
        identifier: item["name"] if counts[item["name"]] == 1 else f"{item['name']} (#{identifier})"
        for identifier, item in templates.items()
    }
