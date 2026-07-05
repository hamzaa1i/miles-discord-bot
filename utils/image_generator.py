"""
utils/image_generator.py — shared Pillow helpers.

FIX 5: Centralizes safe font loading so any future image generator
(profile banners, server info cards, etc.) doesn't hardcode font paths.
Works locally AND on Render without crashing.
"""
import os
from PIL import ImageFont


def load_font(size: int):
    """Safely load a TrueType font, falling back through several paths
    and finally to PIL's default bitmap font. Works locally and on Render."""
    font_paths = [
        "assets/fonts/font.ttf",
        "assets/font.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    ]
    for path in font_paths:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()
