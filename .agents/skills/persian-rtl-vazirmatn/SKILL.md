---
name: persian-rtl-vazirmatn
description: Enforce Persian (Farsi) RTL text direction, UTF-8 encoding, Vazirmatn font selection, and anti-tofu (no square boxes) rendering across all generated files, scripts, images, videos, charts, web apps, and documents. Use whenever generating or editing Persian content, code that renders Persian text (Pillow, OpenCV, Matplotlib, Chromium), HTML/CSS, PDF, Word, PowerPoint, or Excel files.
---

Persian RTL Vazirmatn

Ensure all Persian (Farsi) text across every output format is encoded in UTF-8, aligned Right-to-Left (RTL), styled with the Vazirmatn (وزیرمتن) typeface wherever selectable, and rendered with proper cursive shaping and glyph coverage so characters never appear as square boxes (□□□) or disconnected LTR letters.

When to Use
Generating or editing any file, document, web app, image, video, chart, or script containing Persian (Farsi) text
Writing Python scripts that draw text on images or videos using Pillow (PIL), OpenCV (cv2), or Matplotlib
Creating HTML/CSS web apps, PDFs, Word (.docx), PowerPoint (.pptx), Excel (.xlsx), or CSV files with Persian text
Steps
1. Enforce UTF-8 Encoding Everywhere
Add # -*- coding: utf-8 -*- at the top of Python scripts and always pass encoding="utf-8" when reading or writing files (encoding="utf-8-sig" for CSV files opened in Excel).
Add <meta charset="UTF-8"> as the first tag inside <head> in all HTML templates.
Pass ensure_ascii=False to JSON serialization calls so Persian strings remain readable UTF-8 rather than escaped Unicode sequences.
2. Apply Right-to-Left (RTL) Direction and Vazirmatn Typeface by Format

HTML / CSS / Chromium PDF / Web Apps:

Set <html lang="fa" dir="rtl">.

Apply global RTL rules with Vazirmatn as the primary typeface while isolating inline code blocks:

html, body {
  direction: rtl;
  text-align: right;
  font-family: 'Vazirmatn', 'Noto Sans Arabic', 'Tahoma', sans-serif;
}
pre, code, .ltr {
  direction: ltr;
  text-align: left;
  unicode-bidi: isolate;
}


Word (.docx), PowerPoint (.pptx), and Excel (.xlsx):

Set the primary typeface to "Vazirmatn", enable right-to-left paragraph/sheet direction (<w:bidi/> in Word, rtl="1" in PowerPoint, rightToLeft = True in Excel), and align text to the right.
3. Eliminate Square Boxes (□□□) in Pillow & OpenCV Image/Video Rendering

Never use cv2.putText() for Persian text because OpenCV built-in fonts only support ASCII and render question marks or boxes. Always render via Pillow (PIL.ImageDraw) with the Raqm layout engine (ImageFont.Layout.RAQM) and a font file that covers both Persian (آ-ی, گ چ پ ژ ک ی, ۰-۹) and Latin/ASCII (A-Z, 0-9, (, ), /, -):

Prioritize Vazirmatn: Check for local Vazirmatn-Bold.ttf and Vazirmatn-Regular.ttf first.
Build a Unified Fallback Font Offline: In offline Linux containers where Vazirmatn is not pre-installed, NotoSansArabic-Bold.ttf has Persian glyphs but lacks ASCII/Latin glyphs (A-Z, (, ), /), causing square boxes (□□□) on mixed Persian/English strings. Merge NotoSansArabic-Bold.ttf with NotoSans-Bold.ttf using fontTools.merge.Merger before loading with ImageFont.Layout.RAQM.
Draw with RTL Direction and Auto-Fit Right Anchor: Always pass direction="rtl", language="fa", and anchor="ra" positioned at x = canvas_width - right_margin, scaling down the font size if textbbox width exceeds canvas_width - 2 * margin.
Gotchas
Mixed Persian + English Strings: Passing English words (AI, Node 01) or ASCII punctuation ((, ), /) to a pure Arabic/Persian font like NotoSansArabic-Bold.ttf produces square boxes (□□□). Always use Vazirmatn or the merged NotoSansArabic + NotoSans font.
Left-Edge Clipping on RTL Text: When using anchor="ra" at right_x, long strings extend leftward (right_x - text_width). Always verify text_width <= max_width before drawing.
