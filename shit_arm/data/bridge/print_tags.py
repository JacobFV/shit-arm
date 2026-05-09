"""Generate a printable PNG of ArUco tags at exact physical size.

Print at 100% / actual size (NOT "fit to page"). Each tag is sized in mm,
so it must be reproduced at the right number of dots per inch by the printer.

The script writes the PNG with embedded DPI metadata so most print dialogs
will preserve scale automatically. Verify with a ruler after printing -
the side of each black square should equal TAG_SIZE_MM.
"""
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

# ---- config ----
TAG_SIZE_MM = 40            # side length of the black square (no quiet zone)
DPI         = 300           # printer resolution; 300 is standard
ARUCO_DICT  = cv2.aruco.DICT_4X4_50

TAGS = [
    (0, "BASE — stick on robot base plate, top-center"),
    (1, "TARGET 1 — stick on object A"),
    (2, "TARGET 2 — stick on object B"),
    (3, "TARGET 3 — stick on object C"),
    (4, "TARGET 4"),
    (5, "TARGET 5"),
]

OUT = "/Users/owner/code/robot/aruco_sheet.png"
# ---- end config ----


def mm_to_px(mm: float) -> int:
    return int(round(mm * DPI / 25.4))


def main():
    aruco = cv2.aruco.getPredefinedDictionary(ARUCO_DICT)
    tag_px = mm_to_px(TAG_SIZE_MM)
    quiet_px = mm_to_px(5)            # 5mm white border
    label_h = mm_to_px(8)             # 8mm tall label area
    cell_w = tag_px + 2 * quiet_px
    cell_h = tag_px + 2 * quiet_px + label_h

    cols = 2
    rows = (len(TAGS) + cols - 1) // cols
    page = Image.new("RGB", (cols * cell_w, rows * cell_h), "white")
    draw = ImageDraw.Draw(page)

    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", mm_to_px(3))
    except OSError:
        font = ImageFont.load_default()

    for i, (tid, label) in enumerate(TAGS):
        r, c = divmod(i, cols)
        marker = cv2.aruco.generateImageMarker(aruco, tid, tag_px)
        m_img = Image.fromarray(marker).convert("RGB")
        x = c * cell_w + quiet_px
        y = r * cell_h + quiet_px
        page.paste(m_img, (x, y))
        # corner crop ticks (small black L's at each corner of the quiet zone)
        for dx, dy in [(-2, -2), (tag_px + 2, -2), (-2, tag_px + 2), (tag_px + 2, tag_px + 2)]:
            draw.rectangle([x + dx, y + dy, x + dx + 1, y + dy + 1], fill="black")
        # label
        draw.text(
            (x, y + tag_px + mm_to_px(2)),
            f"id={tid}  ({TAG_SIZE_MM}mm)  {label}",
            fill="black",
            font=font,
        )

    page.save(OUT, dpi=(DPI, DPI))
    print(f"wrote {OUT}")
    print(f"  page: {page.width}×{page.height} px at {DPI} dpi")
    print(f"  page: {page.width / DPI * 25.4:.0f} × {page.height / DPI * 25.4:.0f} mm")
    print(f"  tag side: {TAG_SIZE_MM} mm  ({tag_px} px)")
    print(f"\nprint at 100%% / 'actual size' (NOT 'fit to page').")
    print(f"after printing, measure a tag with a ruler. it must read {TAG_SIZE_MM}mm exactly.")


if __name__ == "__main__":
    main()
