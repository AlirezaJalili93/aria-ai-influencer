#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check the native RTL dependency and render with the bundled Persian fonts."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, features


def check_typography():
    if not features.check("raqm"):
        raise RuntimeError(
            "Pillow RAQM is unavailable. Install the FriBiDi runtime "
            "(AlmaLinux/RHEL: dnf install -y fribidi; Debian/Ubuntu: "
            "apt-get install -y libfribidi0), then rerun in a new Python process. "
            "A custom Pillow build may also need replacement with an official wheel."
        )
    root = Path(__file__).resolve().parents[1]
    canvas = Image.new("RGB", (1080, 240), "#07101f")
    draw = ImageDraw.Draw(canvas)
    for weight, y in (("Regular", 60), ("Bold", 150)):
        font = ImageFont.truetype(
            str(root / "assets/fonts" / ("Vazirmatn-" + weight + ".ttf")),
            size=36, layout_engine=ImageFont.Layout.RAQM,
        )
        draw.text(
            (1000, y), "آریا؛ استودیوی ابری تهران (AI / Node 01) ۱۲۳",
            font=font, direction="rtl", language="fa", anchor="ra", fill="white",
        )
    return canvas


if __name__ == "__main__":
    try:
        check_typography()
    except (RuntimeError, OSError) as exc:
        raise SystemExit(str(exc))
    print("Persian RTL render passed: Pillow RAQM + bundled Vazirmatn Regular/Bold.")
