from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter
import aiohttp
import io
import math

async def fetch_image(url: str) -> Image.Image:
    """Download image from URL"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(str(url)) as response:
                if response.status == 200:
                    data = await response.read()
                    return Image.open(io.BytesIO(data)).convert("RGBA")
    except:
        pass
    return None

def make_circle(image: Image.Image, size: int) -> Image.Image:
    """Crop image into circle"""
    image = image.resize((size, size), Image.LANCZOS)
    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, size, size), fill=255)
    output = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    output.paste(image, (0, 0), mask)
    return output

def get_font(size: int):
    """Get font - uses default if custom not available"""
    try:
        return ImageFont.truetype("assets/font.ttf", size)
    except:
        try:
            return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
        except:
            return ImageFont.load_default()

async def generate_rank_card(
    username: str,
    discriminator: str,
    avatar_url: str,
    level: int,
    current_xp: int,
    required_xp: int,
    rank: int,
    total_users: int,
    status: str = "online",
    accent_color: tuple = (99, 102, 241)
) -> io.BytesIO:
    """Generate a rank card image"""

    # Canvas size
    W, H = 900, 240

    # Colors
    BG_DARK = (15, 15, 20)
    BG_CARD = (22, 22, 30)
    TEXT_WHITE = (255, 255, 255)
    TEXT_GRAY = (160, 160, 170)
    BAR_BG = (40, 40, 50)
    ACCENT = accent_color

    STATUS_COLORS = {
        "online": (67, 181, 129),
        "idle": (250, 166, 26),
        "dnd": (240, 71, 71),
        "offline": (116, 127, 141),
        "streaming": (89, 54, 149)
    }
    STATUS_COLOR = STATUS_COLORS.get(status, STATUS_COLORS["offline"])

    # Create base image
    img = Image.new("RGBA", (W, H), BG_DARK)
    draw = ImageDraw.Draw(img)

    # Background card with slight rounding effect
    card = Image.new("RGBA", (W - 40, H - 40), BG_CARD)
    img.paste(card, (20, 20))

    # Accent left bar
    accent_bar = Image.new("RGBA", (4, H - 60), ACCENT)
    img.paste(accent_bar, (20, 30))

    # Avatar
    avatar_size = 130
    avatar_img = await fetch_image(avatar_url)

    if avatar_img:
        avatar_circle = make_circle(avatar_img, avatar_size)
        avatar_x, avatar_y = 45, (H - avatar_size) // 2
        img.paste(avatar_circle, (avatar_x, avatar_y), avatar_circle)

        # Status indicator circle
        status_size = 28
        status_circle = Image.new("RGBA", (status_size, status_size), (0, 0, 0, 0))
        sdraw = ImageDraw.Draw(status_circle)
        sdraw.ellipse((2, 2, status_size - 2, status_size - 2), fill=BG_DARK)
        sdraw.ellipse((5, 5, status_size - 5, status_size - 5), fill=STATUS_COLOR)
        img.paste(
            status_circle,
            (avatar_x + avatar_size - status_size + 5, avatar_y + avatar_size - status_size + 5),
            status_circle
        )
    else:
        # Fallback circle
        draw.ellipse(
            [45, (H - avatar_size) // 2, 45 + avatar_size, (H - avatar_size) // 2 + avatar_size],
            fill=(50, 50, 60)
        )

    # Fonts
    font_name = get_font(28)
    font_small = get_font(18)
    font_xp = get_font(16)
    font_level = get_font(38)
    font_rank = get_font(20)

    # Username
    text_x = 195
    draw.text((text_x, 45), username, font=font_name, fill=TEXT_WHITE)

    # XP text (top right)
    xp_text = f"{current_xp:,} / {required_xp:,} XP"
    xp_w = draw.textlength(xp_text, font=font_xp)
    draw.text((W - 50 - xp_w, 50), xp_text, font=font_xp, fill=TEXT_GRAY)

    # Progress bar
    bar_x = text_x
    bar_y = 95
    bar_w = W - text_x - 50
    bar_h = 18
    bar_radius = 9

    # Bar background
    draw.rounded_rectangle(
        [bar_x, bar_y, bar_x + bar_w, bar_y + bar_h],
        radius=bar_radius,
        fill=BAR_BG
    )

    # Bar fill
    progress = min(current_xp / required_xp, 1.0) if required_xp > 0 else 0
    fill_w = max(int(bar_w * progress), bar_radius * 2) if progress > 0 else 0

    if fill_w > 0:
        draw.rounded_rectangle(
            [bar_x, bar_y, bar_x + fill_w, bar_y + bar_h],
            radius=bar_radius,
            fill=ACCENT
        )

    # Level text
    level_text = f"LEVEL {level}"
    draw.text((text_x, 130), level_text, font=font_rank, fill=ACCENT)

    # Rank text
    rank_text = f"RANK #{rank}"
    rank_w = draw.textlength(rank_text, font=font_rank)
    draw.text((W - 50 - rank_w, 130), rank_text, font=font_rank, fill=TEXT_GRAY)

    # Progress percentage
    pct = f"{progress * 100:.1f}%"
    pct_w = draw.textlength(pct, font=font_xp)
    draw.text(
        (bar_x + fill_w - pct_w // 2, bar_y + bar_h + 5),
        pct,
        font=font_xp,
        fill=TEXT_GRAY
    )

    # Bottom stats
    stats_y = 175
    stats = [
        ("TOTAL XP", f"{current_xp + sum(5 * (l**2) + 50*l + 100 for l in range(level)):,}"),
        ("NEXT LEVEL", f"{required_xp - current_xp:,} XP away"),
    ]

    stat_x = text_x
    for label, value in stats:
        draw.text((stat_x, stats_y), label, font=font_xp, fill=TEXT_GRAY)
        draw.text((stat_x, stats_y + 20), value, font=font_xp, fill=TEXT_WHITE)
        stat_x += 230

    # Convert to bytes
    output = io.BytesIO()
    img = img.convert("RGB")
    img.save(output, format="PNG", optimize=True)
    output.seek(0)
    return output