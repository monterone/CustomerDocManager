"""Validate embedded assets and resolve their display size for document exporters."""

from dataclasses import dataclass
from io import BytesIO
from math import isfinite

from PIL import Image


@dataclass(frozen=True)
class PreparedImage:
    data: bytes
    mime_type: str
    pixel_width: int
    pixel_height: int
    width_mm: float
    height_mm: float
    alt: str


def prepare_image(attributes, assets, max_width_mm, max_height_mm):
    reference = attributes["src"][6:]
    asset = assets.get(reference)
    if not isinstance(asset, dict):
        raise ValueError(f"Image asset '{reference}' was not supplied.")
    data = asset.get("data")
    if not isinstance(data, (bytes, bytearray, memoryview)) or not data:
        raise ValueError(f"Image asset '{reference}' must contain non-empty bytes.")
    mime_type = asset.get("mime_type")
    if mime_type not in {"image/png", "image/jpeg"}:
        raise ValueError(f"Image asset '{reference}' must be PNG or JPEG.")
    data = bytes(data)
    try:
        with Image.open(BytesIO(data)) as image:
            actual_mime = {"PNG": "image/png", "JPEG": "image/jpeg"}.get(image.format)
            if actual_mime is None:
                raise ValueError("Only PNG and JPEG images are supported.")
            pixels = image.size
            dpi = image.info.get("dpi", (72, 72))
            image.verify()
        with Image.open(BytesIO(data)) as image:
            image.load()
    except (OSError, ValueError, SyntaxError, Image.DecompressionBombError) as error:
        raise ValueError(f"Image asset '{reference}' is not a readable PNG/JPEG.") from error
    if actual_mime != mime_type:
        raise ValueError(f"Image asset '{reference}' does not match its MIME type.")
    try:
        dpi_x, dpi_y = (round(float(value)) for value in dpi)
        if dpi_x <= 0 or dpi_y <= 0:
            raise ValueError("Invalid resolution")
    except (TypeError, ValueError, OverflowError):
        dpi_x = dpi_y = 72
    native_width = pixels[0] / dpi_x * 25.4
    native_height = pixels[1] / dpi_y * 25.4
    dimensions = {}
    for dimension in ("width", "height"):
        key = f"data-{dimension}-mm"
        if key not in attributes:
            continue
        try:
            value = float(attributes[key])
        except (TypeError, ValueError, OverflowError) as error:
            raise ValueError(f"Invalid {dimension} for image '{reference}'.") from error
        if isinstance(attributes[key], bool) or not isfinite(value) or value <= 0:
            raise ValueError(f"Image {dimension} must be a positive finite number.")
        dimensions[dimension] = value
    width = dimensions.get("width")
    height = dimensions.get("height")
    if width is None and height is None:
        width, height = native_width, native_height
    elif width is None:
        width = height * native_width / native_height
    elif height is None:
        height = width * native_height / native_width
    if not isfinite(width) or not isfinite(height) or width > max_width_mm or height > max_height_mm:
        raise ValueError(f"Image '{reference}' exceeds its available content dimensions.")
    return PreparedImage(data, mime_type, *pixels, width, height, attributes.get("alt", ""))
