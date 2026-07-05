"""
utils/rank_card.py — rank card / leaderboard card / profile card image
generators (Pillow-based).

FIX 5: All font loading goes through `load_font()` which falls back
gracefully through several candidate paths and finally to PIL's default
bitmap font — so the bot works locally AND on Render without crashing.
"""
import io
import os
import aiohttp
from PIL import Image, ImageDraw, ImageFont, ImageOps

CONFIG = {
    "canvas": {"width": 934, "height": 282},
    "card": {"x": 20, "y": 20, "w": 894, "h": 242, "radius": 25, "bg": "#16161e"},
    "avatar": {"x": 60, "y": 81, "size": 120},
    "status": {"x": 152, "y": 173, "size": 28},
    "username": {"x": 210, "y": 95, "font_size": 38, "color": "#ffffff"},
    "rank_label": {"x": 750, "y": 35, "font_size": 24, "color": "#a0a0aa"},
    "rank_value": {"x": 815, "y": 60, "font_size": 38, "color": "#ffffff"},
    "level_label": {"x": 580, "y": 35, "font_size": 24},
    "level_value": {"x": 650, "y": 60, "font_size": 38, "color": "#ffffff"},
    "xp_text": {"x": 874, "y": 160, "font_size": 22, "color": "#a0a0aa"},
    "progress_bar": {"x": 210, "y": 190, "w": 664, "h": 16, "bg": "#28283a", "radius": 8},
    "percentage": {"x": 542, "y": 215, "font_size": 18, "color": "#a0a0aa"}
}

STATUS_COLORS = {
    "online": "#43b581",
    "idle": "#faa61a",
    "dnd": "#f04747",
    "offline": "#747f8d"
}


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


# Backward-compat alias used by older code in this module
get_font = load_font


async def generate_rank_card(
    username: str,
    avatar_url: str,
    level: int,
    current_xp: int,
    required_xp: int,
    rank: int,
    status: str = "online",
    accent_color: tuple = (99, 102, 241)
) -> io.BytesIO:
    """Generate rank card image"""

    avatar_bytes = None
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(str(avatar_url)) as resp:
                if resp.status == 200:
                    avatar_bytes = await resp.read()
    except:
        pass

    base = Image.new("RGBA", (CONFIG["canvas"]["width"], CONFIG["canvas"]["height"]), "#0f0f14")
    draw = ImageDraw.Draw(base)

    c = CONFIG["card"]
    draw.rounded_rectangle(
        [c["x"], c["y"], c["x"] + c["w"], c["y"] + c["h"]],
        radius=c["radius"],
        fill=c["bg"]
    )

    font_main = load_font(CONFIG["username"]["font_size"])
    font_sub = load_font(CONFIG["rank_label"]["font_size"])
    font_bold = load_font(CONFIG["rank_value"]["font_size"])
    font_small = load_font(CONFIG["xp_text"]["font_size"])
    font_pct = load_font(CONFIG["percentage"]["font_size"])

    if avatar_bytes:
        try:
            avatar_img = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
            size = CONFIG["avatar"]["size"]
            avatar_img = avatar_img.resize((size, size), Image.Resampling.LANCZOS)
            mask = Image.new("L", (size, size), 0)
            ImageDraw.Draw(mask).ellipse((0, 0, size, size), fill=255)
            avatar_final = ImageOps.fit(avatar_img, mask.size, centering=(0.5, 0.5))
            avatar_final.putalpha(mask)
            base.paste(avatar_final, (CONFIG["avatar"]["x"], CONFIG["avatar"]["y"]), avatar_final)
        except Exception:
            pass

    s_color = STATUS_COLORS.get(status.lower(), STATUS_COLORS["offline"])
    sx, sy, ss = CONFIG["status"]["x"], CONFIG["status"]["y"], CONFIG["status"]["size"]
    draw.ellipse(
        [sx, sy, sx + ss, sy + ss],
        fill=s_color,
        outline=CONFIG["card"]["bg"],
        width=4
    )

    draw.text(
        (CONFIG["username"]["x"], CONFIG["username"]["y"]),
        username,
        font=font_main,
        fill=CONFIG["username"]["color"]
    )

    draw.text(
        (CONFIG["level_label"]["x"], CONFIG["level_label"]["y"]),
        "LEVEL",
        font=font_sub,
        fill=accent_color
    )
    draw.text(
        (CONFIG["level_value"]["x"], CONFIG["level_value"]["y"]),
        str(level),
        font=font_bold,
        fill=CONFIG["level_value"]["color"]
    )

    draw.text(
        (CONFIG["rank_label"]["x"], CONFIG["rank_label"]["y"]),
        "RANK",
        font=font_sub,
        fill=CONFIG["rank_label"]["color"]
    )
    draw.text(
        (CONFIG["rank_value"]["x"], CONFIG["rank_value"]["y"]),
        f"#{rank}",
        font=font_bold,
        fill=CONFIG["rank_value"]["color"]
    )

    xp_str = f"{current_xp:,} / {required_xp:,} XP"
    draw.text(
        (CONFIG["xp_text"]["x"], CONFIG["xp_text"]["y"]),
        xp_str,
        font=font_small,
        fill=CONFIG["xp_text"]["color"],
        anchor="ra"
    )

    pb = CONFIG["progress_bar"]
    draw.rounded_rectangle(
        [pb["x"], pb["y"], pb["x"] + pb["w"], pb["y"] + pb["h"]],
        radius=pb["radius"],
        fill=pb["bg"]
    )

    if required_xp > 0:
        progress_width = (current_xp / required_xp) * pb["w"]
        if progress_width > 10:
            draw.rounded_rectangle(
                [pb["x"], pb["y"], pb["x"] + progress_width, pb["y"] + pb["h"]],
                radius=pb["radius"],
                fill=accent_color
            )

    percentage = int((current_xp / required_xp) * 100) if required_xp > 0 else 0
    draw.text(
        (CONFIG["percentage"]["x"], CONFIG["percentage"]["y"]),
        f"{percentage}%",
        font=font_pct,
        fill=CONFIG["percentage"]["color"],
        anchor="ma"
    )

    buffer = io.BytesIO()
    base.save(buffer, "PNG")
    buffer.seek(0)
    return buffer


async def generate_leaderboard_card(
    title: str,
    users: list,
    accent_color: tuple = (99, 102, 241)
) -> io.BytesIO:
    """Generate leaderboard image card.

    users = [
        {"name": "volc", "value": "$15,000", "avatar_url": "...", "rank": 1},
        ...
    ]
    """
    row_height = 70
    padding = 20
    header_height = 80
    max_users = min(len(users), 10)
    canvas_height = header_height + (max_users * row_height) + (padding * 2)
    canvas_width = 700

    base = Image.new("RGBA", (canvas_width, canvas_height), "#0f0f14")
    draw = ImageDraw.Draw(base)

    draw.rounded_rectangle(
        [padding, padding, canvas_width - padding, canvas_height - padding],
        radius=20,
        fill="#16161e"
    )

    font_title = load_font(28)
    font_name = load_font(22)
    font_value = load_font(20)
    font_rank = load_font(18)

    draw.text(
        (padding + 25, padding + 20),
        title,
        font=font_title,
        fill="#ffffff"
    )

    medal_colors = {
        1: (255, 215, 0),
        2: (192, 192, 192),
        3: (205, 127, 50),
    }

    for i, user_data in enumerate(users[:max_users]):
        y = header_height + (i * row_height) + padding
        rank_num = user_data.get("rank", i + 1)

        circle_x = padding + 30
        circle_y = y + 10
        circle_size = 40

        circle_color = medal_colors.get(rank_num, (40, 40, 50))
        draw.ellipse(
            [circle_x, circle_y, circle_x + circle_size, circle_y + circle_size],
            fill=circle_color
        )

        rank_text = str(rank_num)
        rank_text_color = "#0f0f14" if rank_num <= 3 else "#a0a0aa"
        draw.text(
            (circle_x + circle_size // 2, circle_y + circle_size // 2),
            rank_text,
            font=font_rank,
            fill=rank_text_color,
            anchor="mm"
        )

        avatar_x = circle_x + circle_size + 15
        avatar_size = 40

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(str(user_data.get("avatar_url", ""))) as resp:
                    if resp.status == 200:
                        av_bytes = await resp.read()
                        av_img = Image.open(io.BytesIO(av_bytes)).convert("RGBA")
                        av_img = av_img.resize((avatar_size, avatar_size), Image.Resampling.LANCZOS)
                        mask = Image.new("L", (avatar_size, avatar_size), 0)
                        ImageDraw.Draw(mask).ellipse((0, 0, avatar_size, avatar_size), fill=255)
                        av_final = ImageOps.fit(av_img, mask.size, centering=(0.5, 0.5))
                        av_final.putalpha(mask)
                        base.paste(av_final, (avatar_x, circle_y), av_final)
                        draw = ImageDraw.Draw(base)
        except Exception:
            draw.ellipse(
                [avatar_x, circle_y, avatar_x + avatar_size, circle_y + avatar_size],
                fill="#28283a"
            )

        name_x = avatar_x + avatar_size + 15
        draw.text(
            (name_x, circle_y + 8),
            user_data.get("name", "Unknown"),
            font=font_name,
            fill="#ffffff"
        )

        value_text = user_data.get("value", "$0")
        draw.text(
            (canvas_width - padding - 30, circle_y + 10),
            value_text,
            font=font_value,
            fill=accent_color,
            anchor="ra"
        )

        if i < max_users - 1:
            line_y = y + row_height - 5
            draw.line(
                [(padding + 25, line_y), (canvas_width - padding - 25, line_y)],
                fill="#28283a",
                width=1
            )

    buffer = io.BytesIO()
    base.save(buffer, "PNG")
    buffer.seek(0)
    return buffer


async def generate_profile_card(
    username: str,
    avatar_url: str,
    balance: int,
    bank: int,
    total_earned: int,
    rank: int,
    level: int,
    streak: int,
    gems: int,
    accent_color: tuple = (99, 102, 241)
) -> io.BytesIO:
    """Generate economy profile card"""

    W, H = 700, 380
    base = Image.new("RGBA", (W, H), "#0f0f14")
    draw = ImageDraw.Draw(base)

    draw.rounded_rectangle(
        [20, 20, W - 20, H - 20],
        radius=20,
        fill="#16161e"
    )

    font_name = load_font(32)
    font_label = load_font(16)
    font_value = load_font(24)
    font_small = load_font(14)

    avatar_size = 90
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(str(avatar_url)) as resp:
                if resp.status == 200:
                    av_bytes = await resp.read()
                    av_img = Image.open(io.BytesIO(av_bytes)).convert("RGBA")
                    av_img = av_img.resize((avatar_size, avatar_size), Image.Resampling.LANCZOS)
                    mask = Image.new("L", (avatar_size, avatar_size), 0)
                    ImageDraw.Draw(mask).ellipse((0, 0, avatar_size, avatar_size), fill=255)
                    av_final = ImageOps.fit(av_img, mask.size, centering=(0.5, 0.5))
                    av_final.putalpha(mask)
                    base.paste(av_final, (50, 45), av_final)
                    draw = ImageDraw.Draw(base)
    except Exception:
        draw.ellipse([50, 45, 50 + avatar_size, 45 + avatar_size], fill="#28283a")

    draw.text((160, 60), username, font=font_name, fill="#ffffff")
    draw.text((160, 100), f"RANK #{rank}", font=font_small, fill="#a0a0aa")
    draw.text((280, 100), f"LEVEL {level}", font=font_small, fill=accent_color)

    draw.line([(40, 155), (W - 40, 155)], fill="#28283a", width=1)

    stats = [
        ("WALLET", f"${balance:,}"),
        ("BANK", f"${bank:,}"),
        ("NET WORTH", f"${balance + bank:,}"),
        ("TOTAL EARNED", f"${total_earned:,}"),
        ("STREAK", f"{streak} days"),
        ("GEMS", f"{gems}"),
    ]

    start_x = 50
    start_y = 175
    col_width = 210
    row_height = 80

    for i, (label, value) in enumerate(stats):
        col = i % 3
        row = i // 3
        x = start_x + (col * col_width)
        y = start_y + (row * row_height)
        draw.text((x, y), label, font=font_label, fill="#a0a0aa")
        draw.text((x, y + 22), value, font=font_value, fill="#ffffff")

    buffer = io.BytesIO()
    base.save(buffer, "PNG")
    buffer.seek(0)
    return buffer
