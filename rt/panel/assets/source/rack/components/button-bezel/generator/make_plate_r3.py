"""Assemble the p84 r3 button material, typography, geometry, and LED plate."""

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CANON = HERE.parent / "renders"
COMPARE = ROOT / "design-lab/scratchdiag"
OUT = (
    Path(sys.argv[1]).expanduser().resolve()
    if len(sys.argv) > 1
    else ROOT / "design-lab/plates/p84-screen-bevel-buttons-r3.png"
)

W, H = 1600, 1400
BG = (13, 16, 20)
CARD = (28, 32, 38)
EDGE = (73, 82, 94)
TEXT = (240, 243, 246)
MUTED = (157, 168, 181)
CYAN = (82, 217, 255)
RED = (255, 72, 52)
GREEN = (65, 235, 104)
BLUE = (42, 142, 255)
PURPLE = (190, 78, 255)
COLORS = (RED, GREEN, BLUE, PURPLE)

plate = Image.new("RGB", (W, H), BG)
draw = ImageDraw.Draw(plate)


def font(size, bold=False):
    candidates = (
        ["/System/Library/Fonts/Supplemental/Arial Bold.ttf"] if bold else []
    ) + [
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    return ImageFont.load_default()


def alpha_crop(name, pad=6):
    root = COMPARE if name.startswith("p84-r3-metal-") else CANON
    image = Image.open(root / name).convert("RGBA")
    bbox = image.getchannel("A").getbbox()
    if bbox is None:
        raise ValueError(f"render has no alpha content: {name}")
    x0, y0, x1, y1 = bbox
    return image.crop((
        max(0, x0 - pad), max(0, y0 - pad),
        min(image.width, x1 + pad), min(image.height, y1 + pad),
    ))


def paste_fitted(name, area):
    x, y, w, h = area
    image = alpha_crop(name)
    image.thumbnail((w, h), Image.Resampling.LANCZOS)
    px = x + (w - image.width) // 2
    py = y + (h - image.height) // 2
    alpha = image.getchannel("A")
    shadow = Image.new("L", (image.width + 24, image.height + 24), 0)
    shadow.paste(alpha, (12, 12))
    shadow = shadow.filter(ImageFilter.GaussianBlur(7))
    plate.paste((0, 0, 0), (px - 12, py - 6), shadow)
    plate.paste(image, (px, py), image)


def audit_image(name, height=32):
    image = alpha_crop(name)
    width = max(1, round(image.width * height / image.height))
    return image.resize((width, height), Image.Resampling.LANCZOS)


def card(box, accent):
    x, y, w, h = box
    draw.rounded_rectangle((x, y, x + w, y + h), 22, fill=CARD, outline=EDGE, width=2)
    draw.rounded_rectangle((x, y, x + w, y + 8), 4, fill=accent)


def centered(text, cx, y, size=14, color=MUTED):
    fnt = font(size, True)
    bbox = draw.textbbox((0, 0), text, font=fnt)
    draw.text((cx - (bbox[2] - bbox[0]) // 2, y), text, font=fnt, fill=color)


def material_card(title, active, inactive, x, accent):
    card((x, 150, 740, 300), accent)
    draw.text((x + 24, 174), title, font=font(24, True), fill=TEXT)
    paste_fitted(active, (x + 28, 218, 324, 126))
    paste_fitted(inactive, (x + 388, 218, 324, 126))
    centered("ACTIVE", x + 190, 354, 14, accent)
    centered("INACTIVE", x + 550, 354, 14)
    draw.text((x + 24, 397), "bold mono · flush screen print · non-glossy black", font=font(16), fill=MUTED)


def geometry_card(title, active, inactive, x, accent):
    card((x, 535, 740, 245), accent)
    draw.text((x + 24, 559), title, font=font(23, True), fill=TEXT)
    paste_fitted(active, (x + 28, 605, 324, 118))
    paste_fitted(inactive, (x + 388, 605, 324, 118))
    centered("ACTIVE", x + 190, 729, 14, accent)
    centered("INACTIVE", x + 550, 729, 14)


def compact_card(number, x, accent):
    card((x, 865, 350, 300), accent)
    draw.text((x + 22, 889), f"NUMBER {number}", font=font(22, True), fill=TEXT)
    paste_fitted(f"compact-{number}-active.png", (x + 86, 928, 178, 190))
    centered("ACTIVE", x + 175, 1124, 14, accent)


draw.text((54, 38), "P84 · SCREEN-BEVEL BUTTONS · R3", font=font(41, True), fill=TEXT)
draw.text(
    (56, 91),
    "bold monospace screen print · matte plastic / blackened metal · saturated LED lenses + confined glow · balanced wide labels",
    font=font(20), fill=MUTED,
)

draw.text((52, 122), "MATERIAL A/B", font=font(20, True), fill=(194, 202, 212))
material_card("MATTE BLACK MOULDED PLASTIC", "wide-left-active.png", "wide-left-inactive.png", 50, CYAN)
material_card("BEAD-BLASTED BLACKENED METAL", "p84-r3-metal-source-active.png", "p84-r3-metal-source-inactive.png", 810, (151, 164, 181))

draw.text((52, 493), "WIDE GEOMETRY / MIRRORED END BARS", font=font(20, True), fill=(194, 202, 212))
geometry_card(
    "SOURCE · LEFT LED",
    "wide-left-active.png",
    "wide-left-inactive.png",
    50, CYAN,
)
geometry_card(
    "BYPASS · RIGHT LED",
    "wide-right-active.png",
    "wide-right-inactive.png",
    810, RED,
)
draw.text(
    (56, 802),
    "10.4 mm LED height · 2.4 mm LED/text clearance · 1.6 mm extra breathing room opposite the LED",
    font=font(17), fill=MUTED,
)

draw.text((52, 832), "COMPACT / SATURATED ACTIVE PALETTE", font=font(20, True), fill=(194, 202, 212))
for number, x, accent in zip((1, 2, 3, 4), (50, 425, 800, 1175), COLORS):
    compact_card(number, x, accent)

card((50, 1200, 1500, 145), CYAN)
draw.text((76, 1223), "LITERAL 32 PX FINISHED-HEIGHT AUDIT", font=font(22, True), fill=TEXT)
audit_names = [
    *(f"compact-{number}-active.png" for number in (1, 2, 3, 4)),
    "wide-left-active.png",
    "wide-left-inactive.png",
    "p84-r3-metal-source-active.png",
    "p84-r3-metal-source-inactive.png",
    "wide-right-active.png",
    "wide-right-inactive.png",
]
x = 82
for name in audit_names:
    image = audit_image(name, 32)
    plate.paste(image, (x, 1280), image)
    x += image.width + 30

draw.text(
    (56, 1371),
    "RGBA · Cycles · AgX Medium High Contrast · dead-on 85 mm perspective · no host bezel baked in",
    font=font(17), fill=(126, 138, 154),
)

OUT.parent.mkdir(parents=True, exist_ok=True)
plate.save(OUT, optimize=True)
print(f"wrote {OUT}")
