from pathlib import Path
from math import atan2, cos, sin

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
SIZE = (1080, 1350)
BG = "#08111f"
SURFACE = "#101c30"
SURFACE_ALT = "#142745"
BLUE = "#4a8cff"
BLUE_LIGHT = "#86b4ff"
TEXT = "#f3f7ff"
MUTED = "#91a2bd"


def font(path, size):
    return ImageFont.truetype(path, size)


EN_FONT = r"C:\Windows\Fonts\segoeui.ttf"
EN_BOLD = r"C:\Windows\Fonts\segoeuib.ttf"
ZH_FONT = r"C:\Windows\Fonts\msjh.ttc"
ZH_BOLD = r"C:\Windows\Fonts\msjhbd.ttc"


def centered(draw, xy, text, fnt, fill):
    box = draw.textbbox((0, 0), text, font=fnt)
    w = box[2] - box[0]
    h = box[3] - box[1]
    draw.text((xy[0] - w / 2, xy[1] - h / 2 - box[1]), text, font=fnt, fill=fill)


def arrow(draw, start, end, fill=BLUE, width=8):
    angle = atan2(end[1] - start[1], end[0] - start[0])
    head = 20
    shaft_end = (end[0] - cos(angle) * head, end[1] - sin(angle) * head)
    draw.line((start, shaft_end), fill=fill, width=width)
    left = (
        end[0] - cos(angle - 0.7) * head,
        end[1] - sin(angle - 0.7) * head,
    )
    right = (
        end[0] - cos(angle + 0.7) * head,
        end[1] - sin(angle + 0.7) * head,
    )
    draw.polygon((end, left, right), fill=fill)


def render(lang):
    is_zh = lang == "zh-tw"
    regular = ZH_FONT if is_zh else EN_FONT
    bold = ZH_BOLD if is_zh else EN_BOLD
    copy = {
        "title": "FAFE 全自動循環" if is_zh else "FAFE FULL AUTO LOOP",
        "subtitle": (
            "競速 → 購車 → 解鎖 → 賣車 → 轉輪 → 重複"
            if is_zh
            else "RACE → BUY → UNLOCK → SELL → SPIN → REPEAT"
        ),
        "steps": (
            ["掛機競速", "批次購車", "解鎖熟練度", "賣出車輛", "幸運轉盤"]
            if is_zh
            else ["AFK RACES", "BUY CARS", "UNLOCK MASTERY", "SELL CARS", "WHEELSPINS"]
        ),
        "center": "重複循環" if is_zh else "REPEAT",
        "footer": "完成後自動回到競速，持續循環" if is_zh else "FINISH THE CYCLE, RETURN TO RACING, REPEAT",
    }

    im = Image.new("RGB", SIZE, BG)
    draw = ImageDraw.Draw(im)

    # Subtle speed-line background.
    for y, x, length in [
        (88, 72, 220), (130, 760, 210), (225, 130, 150), (300, 810, 175),
        (555, 42, 145), (650, 830, 180), (1000, 70, 190), (1080, 775, 235),
        (1200, 140, 170), (1260, 720, 180),
    ]:
        draw.line((x, y, x + length, y), fill="#173a72", width=2)

    centered(draw, (540, 100), copy["title"], font(bold, 56 if not is_zh else 54), TEXT)
    centered(draw, (540, 165), copy["subtitle"], font(regular, 23 if not is_zh else 25), MUTED)
    draw.line((250, 205, 830, 205), fill=BLUE, width=4)

    centers = [(540, 330), (830, 540), (720, 890), (360, 890), (250, 540)]
    box_size = (300, 120)
    half_w, half_h = box_size[0] // 2, box_size[1] // 2

    # Closed loop arrows, drawn behind the cards.
    arrow(draw, (660, 372), (760, 462))
    arrow(draw, (815, 600), (760, 810))
    arrow(draw, (610, 890), (510, 890))
    arrow(draw, (305, 810), (260, 610))
    arrow(draw, (320, 462), (440, 372))

    for i, ((cx, cy), label) in enumerate(zip(centers, copy["steps"]), start=1):
        rect = (cx - half_w, cy - half_h, cx + half_w, cy + half_h)
        draw.rounded_rectangle(rect, radius=22, fill=SURFACE_ALT if i == 1 else SURFACE, outline=BLUE, width=3)
        draw.rounded_rectangle((rect[0] + 18, rect[1] + 18, rect[0] + 54, rect[1] + 54), radius=8, fill=BLUE)
        centered(draw, (rect[0] + 36, rect[1] + 36), str(i), font(bold, 20), BG)
        centered(draw, (cx, cy + 8), label, font(bold, 29 if not is_zh else 31), TEXT)

    draw.ellipse((410, 555, 670, 815), fill="#0d203d", outline=BLUE_LIGHT, width=4)
    centered(draw, (540, 675), copy["center"], font(bold, 42 if not is_zh else 40), BLUE_LIGHT)

    draw.rounded_rectangle((150, 1120, 930, 1220), radius=20, fill=SURFACE, outline="#27466f", width=2)
    centered(draw, (540, 1170), copy["footer"], font(bold, 24 if not is_zh else 27), TEXT)
    centered(draw, (540, 1285), "FULL AUTO FORZA EDITION", font(bold, 20), "#54739f")

    out = ROOT / f"threads-full-auto-loop-{lang}.png"
    im.save(out, "PNG", optimize=True)
    print(out)


if __name__ == "__main__":
    render("en")
    render("zh-tw")
