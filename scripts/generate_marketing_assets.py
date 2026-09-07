#!/usr/bin/env python3
"""
scripts/generate_marketing_assets.py — PHASE M PART 7.

Generates every veloura-branded image asset with PIL (no external
services):

  dashboard/public/
    og-image.png                     1200x630 open-graph card

  dashboard/marketing/
    aurelia-logo-512.png             square logo (bot lists)
    aurelia-logo-1024.png            hi-res square logo
    aurelia-icon-transparent.png     star icon only, transparent bg
    aurelia-banner-1920x1080.png     landscape banner
    aurelia-banner-2000x1000.png     discord-style banner
    aurelia-features-collage.png     2x3 feature tiles
    aurelia-dashboard-preview.png    stylized dashboard mockup
    aurelia-chat-preview.png         chat conversation mockup
    aurelia-welcome-preview.png      welcome embed card mockup
    aurelia-mod-preview.png          moderation case card mockup

The "preview" images are stylized mockups in the exact veloura
palette (not literal screenshots) — they're listing-safe placeholders
that can be replaced with real captures later (noted in
MARKETING_ASSETS_README.md). Fonts: Liberation Serif (headings,
Playfair-like) + Liberation Sans (body, Inter-like) — the closest
metric equivalents installed locally.

Re-run any time: python scripts/generate_marketing_assets.py
"""
import os

from PIL import Image, ImageDraw, ImageFilter, ImageFont

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUB = os.path.join(REPO, "dashboard", "public")
MKT = os.path.join(REPO, "dashboard", "marketing")

# veloura palette
NAVY = (26, 29, 41)          # #1A1D29
NAVY_DEEP = (18, 20, 29)     # #12141D
CARD = (36, 41, 56)          # #242938
CARD_HOVER = (43, 49, 69)    # #2B3145
BORDER = (51, 58, 78)        # #333A4E
PINK = (255, 192, 203)       # #FFC0CB
PINK_SOFT = (244, 168, 184)  # #F4A8B8
LAVENDER = (230, 230, 250)   # #E6E6FA
TEXT = (245, 245, 245)       # #F5F5F5
MUTED = (156, 163, 175)      # #9CA3AF
SUCCESS = (168, 230, 207)    # #A8E6CF
DANGER = (244, 168, 168)     # #F4A8A8

SERIF_B = "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf"
SERIF_R = "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf"
SANS_B = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
SANS_R = "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"


def font(path, size):
    return ImageFont.truetype(path, size)


def star_points(cx, cy, r_out, r_in=None):
    """Four-pointed sparkle star (the aurelia mark)."""
    r_in = r_in or r_out * 0.18
    pts = []
    for i in range(8):
        ang = i * 45 - 90
        import math
        rad = math.radians(ang)
        r = r_out if i % 2 == 0 else r_in
        pts.append((cx + r * math.cos(rad), cy + r * math.sin(rad)))
    return pts


def draw_star(draw, cx, cy, r, fill, glow=False):
    if glow:
        draw.polygon(star_points(cx, cy, r * 1.25), fill=(fill[0], fill[1], fill[2], 40))
    draw.polygon(star_points(cx, cy, r), fill=fill)


def rounded(draw, box, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def radial_glow(size, center, radius, color, strength=90):
    """Soft radial glow layer."""
    glow = Image.new("RGBA", size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    cx, cy = center
    steps = 40
    for i in range(steps, 0, -1):
        r = radius * i / steps
        alpha = int(strength * (1 - i / steps))
        gd.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color + (alpha,))
    return glow.filter(ImageFilter.GaussianBlur(radius * 0.08))


def text_center(draw, xy, s, fnt, fill):
    x, y = xy
    bbox = draw.textbbox((0, 0), s, font=fnt)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    draw.text((x - w / 2, y - h / 2), s, font=fnt, fill=fill)
    return w, h


# ─── 1 · square logo (navy card + star + wordmark) ─────────────────
def make_logo(size: int, path: str):
    img = Image.new("RGB", (size, size), CARD)
    draw = ImageDraw.Draw(img)
    # border ring
    m = int(size * 0.03)
    rounded(draw, [m, m, size - m, size - m], int(size * 0.22), NAVY_DEEP,
            outline=BORDER, width=max(2, size // 256))
    # glow behind star
    img = Image.alpha_composite(img.convert("RGBA"),
                                radial_glow((size, size), (size / 2, size * 0.40),
                                            size * 0.34, PINK, 70)).convert("RGB")
    draw = ImageDraw.Draw(img)
    # big star
    draw_star(draw, size / 2, size * 0.40, size * 0.21, PINK)
    # tiny companion sparkle
    draw_star(draw, size * 0.72, size * 0.26, size * 0.055, LAVENDER)
    # wordmark
    fnt = font(SERIF_B, int(size * 0.115))
    text_center(draw, (size / 2, size * 0.78), "aurelia", fnt, TEXT)
    fnt2 = font(SANS_R, int(size * 0.035))
    text_center(draw, (size / 2, size * 0.885), "the soft, elegant discord bot ✦".replace("✦", "*"),
                fnt2, MUTED)
    img.save(path)
    print(f"wrote {path}")


# ─── 2 · transparent icon (star only) ──────────────────────────────
def make_icon(path: str, size: int = 1024):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    img = Image.alpha_composite(img, radial_glow((size, size), (size / 2, size / 2),
                                                  size * 0.4, PINK, 80))
    draw = ImageDraw.Draw(img)
    draw_star(draw, size / 2, size / 2, size * 0.42, PINK)
    # inner highlight
    draw_star(draw, size * 0.62, size * 0.36, size * 0.10, LAVENDER)
    img.save(path)
    print(f"wrote {path}")


# ─── 3 · banners ───────────────────────────────────────────────────
def make_banner(w: int, h: int, path: str):
    img = Image.new("RGB", (w, h), NAVY)
    # gradient washes: pink → lavender → navy
    glow1 = radial_glow((w, h), (w * 0.28, h * 0.30), w * 0.34, PINK, 46)
    glow2 = radial_glow((w, h), (w * 0.75, h * 0.70), w * 0.30, LAVENDER, 34)
    img = Image.alpha_composite(img.convert("RGBA"), glow1)
    img = Image.alpha_composite(img, glow2).convert("RGB")
    draw = ImageDraw.Draw(img)

    # scattered tiny stars
    seeds = [(0.12, 0.20, 0.012), (0.42, 0.12, 0.008), (0.62, 0.82, 0.010),
             (0.86, 0.25, 0.014), (0.25, 0.75, 0.007), (0.55, 0.45, 0.006),
             (0.9, 0.6, 0.008), (0.08, 0.55, 0.009)]
    for fx, fy, fr in seeds:
        draw_star(draw, w * fx, h * fy, w * fr, (LAVENDER[0], LAVENDER[1], LAVENDER[2]))

    # hero star
    star_cx, star_cy, star_r = w * 0.5, h * 0.34, w * 0.075
    draw_star(draw, star_cx, star_cy, star_r, PINK)
    draw_star(draw, w * 0.62, h * 0.22, w * 0.018, LAVENDER)

    # wordmark + tagline
    f1 = font(SERIF_B, int(h * 0.115))
    text_center(draw, (w / 2, h * 0.60), "aurelia", f1, TEXT)
    f2 = font(SANS_R, int(h * 0.038))
    text_center(draw, (w / 2, h * 0.735), "the soft, elegant discord bot", f2, PINK)
    f3 = font(SANS_R, int(h * 0.028))
    text_center(draw, (w / 2, h * 0.82),
                "ai chat  ·  aesthetic moderation  ·  community  ·  free forever",
                f3, MUTED)
    img.save(path)
    print(f"wrote {path}")


# ─── 4 · og image (1200x630) ───────────────────────────────────────
def make_og(path: str):
    w, h = 1200, 630
    img = Image.new("RGB", (w, h), NAVY)
    glow1 = radial_glow((w, h), (w * 0.22, h * 0.35), w * 0.30, PINK, 40)
    glow2 = radial_glow((w, h), (w * 0.85, h * 0.75), w * 0.26, LAVENDER, 30)
    img = Image.alpha_composite(img.convert("RGBA"), glow1)
    img = Image.alpha_composite(img, glow2).convert("RGB")
    draw = ImageDraw.Draw(img)

    # left-aligned hero star
    draw_star(draw, w * 0.17, h * 0.42, 74, PINK)
    draw_star(draw, w * 0.24, h * 0.22, 22, LAVENDER)

    # headline block
    hx = w * 0.32
    draw.text((hx, h * 0.24), "aurelia", font=font(SERIF_B, 92), fill=TEXT)
    draw.text((hx, h * 0.50), "the soft, elegant discord bot", font=font(SANS_B, 40), fill=PINK)
    draw.text((hx, h * 0.63), "ai chat · aesthetic moderation · community engagement",
              font=font(SANS_R, 26), fill=MUTED)
    draw.text((hx, h * 0.72), "free forever · veloura-aurelia.vercel.app",
              font=font(SANS_R, 24), fill=LAVENDER)
    # underline flourish
    draw.line([hx, h * 0.46, hx + 430, h * 0.46], fill=(BORDER[0], BORDER[1], BORDER[2]), width=2)
    img.save(path)
    print(f"wrote {path}")


# ─── 5 · chat preview mockup ───────────────────────────────────────
def make_chat_preview(path: str, w=1200, h=630):
    img = Image.new("RGB", (w, h), NAVY)
    draw = ImageDraw.Draw(img)
    draw = _chrome(draw, w, h, "#general  ·  aurelia is typing…")
    top = 86
    pad = 34
    # user message (right, pink bubble)
    _bubble(draw, w - pad - 620, top + 24, 620, 64, CARD_HOVER, 18,
            "aurelia, remember that i love lavender?", SANS_R, 24, TEXT,
            align="right")
    # aurelia reply (left, card bubble + avatar)
    draw.ellipse([pad, top + 110, pad + 56, top + 166], fill=CARD_HOVER, outline=BORDER, width=2)
    draw_star(draw, pad + 28, top + 138, 14, PINK)
    _bubble(draw, pad + 74, top + 104, 640, 96, CARD, 18,
            "noted forever * — i already knew. you mention it when the server gets quiet *",
            SANS_R, 24, TEXT)
    _bubble(draw, pad + 74, top + 230, 560, 64, CARD, 18,
            "memory updated — 3 facts kept about you", SANS_R, 24, PINK)
    img.save(path)
    print(f"wrote {path}")


def _bubble(draw, x, y, bw, bh, fill, radius, text, fnt_path, size, color, align="left"):
    rounded(draw, [x, y, x + bw, y + bh], radius, fill)
    fnt = font(fnt_path, size)
    # wrap text
    words = text.split(" ")
    lines = []
    cur = ""
    max_w = bw - 48
    for wd in words:
        trial = (cur + " " + wd).strip()
        if draw.textlength(trial, font=fnt) <= max_w:
            cur = trial
        else:
            lines.append(cur)
            cur = wd
    lines.append(cur)
    line_h = size + 10
    ty = y + (bh - line_h * len(lines)) / 2
    for ln in lines:
        draw.text((x + 24, ty), ln, font=fnt, fill=color)
        ty += line_h


def _chrome(draw, w, h, title):
    """window chrome bar for preview mockups."""
    rounded(draw, [16, 16, w - 16, h - 16], 20, CARD, outline=BORDER, width=2)
    for i, c in enumerate((DANGER, (245, 214, 138), SUCCESS)):
        draw.ellipse([38 + i * 26, 34, 52 + i * 26, 48], fill=c)
    fnt = font(SANS_R, 20)
    tw = draw.textlength(title, font=fnt)
    rounded(draw, [w / 2 - tw / 2 - 18, 28, w / 2 + tw / 2 + 18, 54], 13, NAVY_DEEP)
    draw.text((w / 2 - tw / 2, 33), title, font=fnt, fill=MUTED)
    draw.line([16, 66, w - 16, 66], fill=BORDER, width=2)
    return draw


# ─── 6 · welcome preview mockup ────────────────────────────────────
def make_welcome_preview(path: str, w=1200, h=630):
    img = Image.new("RGB", (w, h), NAVY)
    draw = ImageDraw.Draw(img)
    draw = _chrome(draw, w, h, "#welcome  ·  live preview")
    # embed card
    ex, ey, ew, eh = 120, 130, w - 240, 320
    rounded(draw, [ex, ey, ex + ew, ey + eh], 16, CARD, outline=BORDER, width=2)
    # gradient strip
    for i in range(ew):
        t = i / ew
        col = tuple(int(PINK[c] * (1 - t) + LAVENDER[c] * t) for c in range(3))
        draw.line([ex + 4 + i, ey, ex + 4 + i, ey + 10], fill=col)
    draw.text((ex + 34, ey + 44), "♡ welcome to veloura lounge", font=font(SERIF_B, 40), fill=PINK)
    draw.text((ex + 34, ey + 116), "miyu drifted in — member #128 ✧ may the stars be kind",
              font=font(SANS_R, 26), fill=TEXT)
    # pills
    pills = [("embed mode", PINK), ("#FFC0CB", LAVENDER), ("live preview", MUTED)]
    px = ex + 34
    for label, col in pills:
        fnt = font(SANS_R, 18)
        pw = draw.textlength(label, font=fnt) + 30
        rounded(draw, [px, ey + 180, px + pw, ey + 214], 17, NAVY_DEEP, outline=BORDER, width=1)
        draw.text((px + 15, ey + 188), label, font=fnt, fill=col)
        px += pw + 14
    # avatar circle
    draw.ellipse([ex + ew - 130, ey + 40, ex + ew - 50, ey + 120], fill=CARD_HOVER,
                 outline=BORDER, width=2)
    draw_star(draw, ex + ew - 90, ey + 80, 22, PINK)
    img.save(path)
    print(f"wrote {path}")


# ─── 7 · mod preview mockup ────────────────────────────────────────
def make_mod_preview(path: str, w=1200, h=630):
    img = Image.new("RGB", (w, h), NAVY)
    draw = ImageDraw.Draw(img)
    draw = _chrome(draw, w, h, "dashboard  ·  moderation  ·  warnings")

    def case(y, title, subtitle, badge, badge_col, icon_col):
        rounded(draw, [60, y, w - 60, y + 96], 14, CARD, outline=BORDER, width=2)
        rounded(draw, [86, y + 22, 142, y + 74], 12, NAVY_DEEP)
        draw_star(draw, 114, y + 48, 15, icon_col)
        draw.text((166, y + 18), title, font=font(SANS_B, 24), fill=TEXT)
        draw.text((166, y + 52), subtitle, font=font(SANS_R, 20), fill=MUTED)
        fnt = font(SANS_R, 17)
        bw = draw.textlength(badge, font=fnt) + 34
        rounded(draw, [w - 92 - bw, y + 30, w - 92, y + 66], 17, NAVY_DEEP,
                outline=badge_col, width=1)
        draw.text((w - 92 - bw + 17, y + 36), badge, font=fnt, fill=badge_col)

    case(112, "case #7 · warning", "reason: spam in #general · 2/3 warnings before timeout",
         "warning", DANGER, DANGER)
    case(228, "ai automod · severity 2/5", "soft nudge sent · no timeout — it was just caps lock ✧",
         "nudged", LAVENDER, LAVENDER)
    case(344, "audit trail", "dashboard action by @volc · settings patched · 09:41 utc",
         "logged", SUCCESS, SUCCESS)
    draw.text((60, 480), "gentle where it matters, firm where it counts ✦",
              font=font(SERIF_R, 30), fill=PINK)
    img.save(path)
    print(f"wrote {path}")


# ─── 8 · dashboard preview mockup ──────────────────────────────────
def make_dashboard_preview(path: str, w=1600, h=900):
    img = Image.new("RGB", (w, h), NAVY)
    draw = ImageDraw.Draw(img)
    draw = _chrome(draw, w, h, "veloura-aurelia.vercel.app/servers")
    # sidebar
    rounded(draw, [40, 92, 300, h - 40], 14, CARD, outline=BORDER, width=2)
    draw.text((64, 116), "aurelia", font=font(SERIF_B, 28), fill=TEXT)
    sy = 176
    items = ["overview", "statistics", "chat & memory", "vibe & fortune",
             "qotd", "recap", "ai automod", "warnings", "logging",
             "welcome & goodbye", "leveling", "giveaways"]
    for i, it in enumerate(items):
        active = it == "welcome & goodbye"
        if active:
            rounded(draw, [56, sy - 8, 284, sy + 24], 9, (255, 192, 203, 30) if False else CARD_HOVER)
            draw.text((76, sy), it, font=font(SANS_B, 20), fill=PINK)
        else:
            draw.text((76, sy), it, font=font(SANS_R, 20), fill=MUTED)
        sy += 44
    # content header
    draw.text((340, 120), "welcome & goodbye", font=font(SERIF_B, 44), fill=TEXT)
    draw.text((340, 180), "greet every soul that drifts in", font=font(SANS_R, 24), fill=MUTED)
    # stat cards row
    stats = [("enabled", "on ♡", SUCCESS), ("mode", "embed", PINK),
             ("color", "#FFC0CB", LAVENDER), ("goodbye", "on", SUCCESS)]
    cx = 340
    for label, val, col in stats:
        rounded(draw, [cx, 230, cx + 280, 330], 14, CARD, outline=BORDER, width=2)
        draw.text((cx + 24, 252), label.upper(), font=font(SANS_R, 17), fill=MUTED)
        draw.text((cx + 24, 280), val, font=font(SERIF_B, 34), fill=col)
        cx += 300
    # preview panel
    rounded(draw, [340, 360, w - 60, h - 80], 14, CARD, outline=BORDER, width=2)
    draw.text((364, 382), "live preview", font=font(SANS_R, 19), fill=MUTED)
    rounded(draw, [364, 416, w - 84, h - 104], 10, NAVY_DEEP)
    # fake welcome embed inside preview
    for i in range(w - 84 - 364 - 8):
        t = i / (w - 84 - 364)
        col = tuple(int(PINK[c] * (1 - t) + LAVENDER[c] * t) for c in range(3))
        draw.line([368 + i, 416, 368 + i, 426], fill=col)
    draw.text((392, 448), "♡ welcome to veloura lounge", font=font(SERIF_B, 30), fill=PINK)
    draw.text((392, 500), "luna drifted in — member #129 ✧ may the stars be kind",
              font=font(SANS_R, 22), fill=TEXT)
    # save bar
    rounded(draw, [340, h - 66, 700, h - 30], 12, PINK)
    draw.text((392, h - 60), "save changes", font=font(SANS_B, 20), fill=NAVY_DEEP)
    img.save(path)
    print(f"wrote {path}")


# ─── 9 · features collage (2x3) ────────────────────────────────────
def make_features_collage(path: str, w=1600, h=1000):
    img = Image.new("RGB", (w, h), NAVY)
    draw = ImageDraw.Draw(img)
    tiles = [
        ("ai chat & memory", "she remembers you", PINK),
        ("aesthetic welcome", "greet every soul", LAVENDER),
        ("smart moderation", "gentle but firm", DANGER),
        ("engagement", "keep the vibes alive", PINK),
        ("beautiful dashboard", "manage visually", LAVENDER),
        ("privacy first", "you're in control", SUCCESS),
    ]
    cols, rows = 3, 2
    gap = 28
    tw = (w - gap * (cols + 1)) // cols
    th = (h - gap * (rows + 1)) // rows
    for idx, (title, tag, col) in enumerate(tiles):
        r, c = divmod(idx, cols)
        x = gap + c * (tw + gap)
        y = gap + r * (th + gap)
        rounded(draw, [x, y, x + tw, y + th], 18, CARD, outline=BORDER, width=2)
        draw_star(draw, x + tw / 2, y + th * 0.32, 34, col)
        text_center(draw, (x + tw / 2, y + th * 0.62), title, font(SANS_B, 30), TEXT)
        text_center(draw, (x + tw / 2, y + th * 0.76), tag, font(SANS_R, 24), col)
    img.save(path)
    print(f"wrote {path}")


def main():
    os.makedirs(PUB, exist_ok=True)
    os.makedirs(MKT, exist_ok=True)

    make_logo(512, os.path.join(MKT, "aurelia-logo-512.png"))
    make_logo(1024, os.path.join(MKT, "aurelia-logo-1024.png"))
    make_icon(os.path.join(MKT, "aurelia-icon-transparent.png"), 1024)
    make_banner(1920, 1080, os.path.join(MKT, "aurelia-banner-1920x1080.png"))
    make_banner(2000, 1000, os.path.join(MKT, "aurelia-banner-2000x1000.png"))
    make_og(os.path.join(PUB, "og-image.png"))
    make_features_collage(os.path.join(MKT, "aurelia-features-collage.png"))
    make_dashboard_preview(os.path.join(MKT, "aurelia-dashboard-preview.png"))
    make_chat_preview(os.path.join(MKT, "aurelia-chat-preview.png"))
    make_welcome_preview(os.path.join(MKT, "aurelia-welcome-preview.png"))
    make_mod_preview(os.path.join(MKT, "aurelia-mod-preview.png"))
    print("all assets generated ✦")


if __name__ == "__main__":
    main()
