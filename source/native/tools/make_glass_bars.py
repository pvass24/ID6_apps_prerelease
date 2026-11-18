"""Generate glass-aesthetic bar frames for BoostDeck on iDrive 6.

Drop-in replacement for make_bars.py assets. Same image IDs, same XML layout,
but with gradient ramp fills, glow tips, frosted panel backgrounds, and depth.
"""
from io import BytesIO
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[1]

BARS = (
    ('Boost', 'psi', 0, 35), ('AFR', '', 9, 19), ('Timing', 'deg', -20, 50),
    ('Intake air', r'\260F', -20, 100), ('Transmission', r'\260F', 0, 150),
    ('Rail pressure', 'psi', 0, 250), ('Oil pressure', 'psi', 0, 8), ('Coolant', r'\260F', 0, 130),
)

GLASS_THEMES = {
    'Frozen Ice': {
        'ramp': [(26, 70, 120), (50, 130, 200), (100, 190, 255), (170, 220, 255)],
        'glow': (126, 200, 255),
        'track': (25, 35, 50),
        'track_edge': (40, 55, 75),
        'panel': (15, 22, 35),
        'panel_edge': (45, 65, 95),
        'panel_highlight': (80, 120, 180),
    },
    'Ember': {
        'ramp': [(120, 50, 15), (200, 90, 25), (255, 140, 40), (255, 190, 80)],
        'glow': (255, 150, 50),
        'track': (45, 25, 15),
        'track_edge': (70, 40, 25),
        'panel': (30, 18, 12),
        'panel_edge': (80, 50, 30),
        'panel_highlight': (160, 90, 50),
    },
    'M Sport': {
        'ramp': [(30, 80, 180), (55, 140, 230), (80, 180, 255), (140, 210, 255)],
        'glow': (61, 155, 255),
        'track': (20, 30, 45),
        'track_edge': (35, 50, 70),
        'panel': (14, 20, 32),
        'panel_edge': (40, 55, 85),
        'panel_highlight': (70, 100, 160),
    },
    'Midnight': {
        'ramp': [(50, 50, 120), (80, 80, 180), (120, 120, 240), (170, 170, 255)],
        'glow': (140, 140, 255),
        'track': (20, 20, 35),
        'track_edge': (35, 35, 55),
        'panel': (12, 12, 22),
        'panel_edge': (40, 40, 70),
        'panel_highlight': (70, 70, 130),
    },
}

WARN_RAMP = [(200, 160, 30), (230, 130, 20), (255, 80, 30), (255, 40, 40)]
WARN_GLOW = (255, 60, 40)

STEPS, FIRST = 256, 55000


def lerp_color(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def ramp_color(colors, f):
    f = max(0.0, min(1.0, f))
    n = len(colors) - 1
    idx = min(n - 1, int(f * n))
    local_t = f * n - idx
    return lerp_color(colors[idx], colors[idx + 1], local_t)


def draw_glass_bar(width, height, step, total_steps, theme, warn=False):
    """Generate a single glass-style progress bar frame."""
    img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    radius = height // 2

    # track background with subtle edge
    track_color = theme['track'] + (180,)
    draw.rounded_rectangle((0, 0, width - 1, height - 1), radius=radius,
                           fill=track_color)

    # track inner edge (subtle depth)
    edge_color = theme['track_edge'] + (60,)
    draw.rounded_rectangle((0, 0, width - 1, height - 1), radius=radius,
                           outline=edge_color, width=1)

    if step == 0:
        return img

    f = step / total_steps
    fill_width = max(radius * 2, int(width * f))
    colors = WARN_RAMP if warn else theme['ramp']
    glow_color = WARN_GLOW if warn else theme['glow']

    # gradient fill bar
    bar = Image.new('RGBA', (fill_width, height), (0, 0, 0, 0))
    bar_draw = ImageDraw.Draw(bar)

    # draw gradient by columns
    for x in range(fill_width):
        col_f = x / max(1, fill_width - 1)
        combined_f = col_f * f
        color = ramp_color(colors, combined_f)
        # vertical gradient: lighter at top, darker at bottom
        for y in range(height):
            vert_f = y / max(1, height - 1)
            brightness = 1.0 + 0.15 * (1.0 - vert_f) - 0.1 * vert_f
            px_color = tuple(max(0, min(255, int(c * brightness))) for c in color) + (230,)
            bar.putpixel((x, y), px_color)

    # mask to rounded rect
    mask = Image.new('L', (fill_width, height), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle((0, 0, fill_width - 1, height - 1), radius=radius, fill=255)
    bar.putalpha(mask)

    img.paste(bar, (0, 0), bar)

    # glow tip at the leading edge
    if fill_width > radius * 2:
        glow_layer = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        glow_draw = ImageDraw.Draw(glow_layer)
        glow_x = fill_width - 2
        glow_y = height // 2
        glow_r = height
        glow_rgba = glow_color + (90,)
        glow_draw.ellipse((glow_x - glow_r, glow_y - glow_r,
                           glow_x + glow_r, glow_y + glow_r), fill=glow_rgba)
        glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(radius=4))
        img = Image.alpha_composite(img, glow_layer)

        # bright dot at tip
        dot_layer = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        dot_draw = ImageDraw.Draw(dot_layer)
        dot_draw.ellipse((glow_x - 2, glow_y - 2, glow_x + 2, glow_y + 2),
                         fill=glow_color + (200,))
        img = Image.alpha_composite(img, dot_layer)

    # top highlight line for glass effect
    hl_layer = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    hl_draw = ImageDraw.Draw(hl_layer)
    if fill_width > radius * 2 + 4:
        hl_draw.line((radius + 2, 1, fill_width - radius - 2, 1),
                     fill=(255, 255, 255, 35), width=1)
    img = Image.alpha_composite(img, hl_layer)

    return img


def draw_glass_panel(width, height, theme):
    """Generate a frosted glass panel background."""
    img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    radius = 10

    # main panel fill with vertical gradient
    for y in range(height):
        f = y / max(1, height - 1)
        base = theme['panel']
        alpha = int(140 + 40 * (1.0 - f))
        brightness = 1.0 + 0.12 * (1.0 - f)
        color = tuple(max(0, min(255, int(c * brightness))) for c in base) + (alpha,)
        draw.line((radius, y, width - radius - 1, y), fill=color)

    # mask to rounded rect
    mask = Image.new('L', (width, height), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle((0, 0, width - 1, height - 1), radius=radius, fill=255)
    img.putalpha(mask)

    # edge glow
    edge_layer = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    edge_draw = ImageDraw.Draw(edge_layer)
    edge_color = theme['panel_edge'] + (80,)
    edge_draw.rounded_rectangle((0, 0, width - 1, height - 1), radius=radius,
                                outline=edge_color, width=1)
    img = Image.alpha_composite(img, edge_layer)

    # top highlight for frosted glass
    hl = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    hl_draw = ImageDraw.Draw(hl)
    hl_color = theme['panel_highlight'] + (30,)
    hl_draw.line((radius + 4, 1, width - radius - 4, 1), fill=hl_color, width=1)
    img = Image.alpha_composite(img, hl)

    return img


def build_assets(theme_name='Frozen Ice'):
    theme = GLASS_THEMES[theme_name]
    out_dir = ROOT / 'plugin'
    out_dir.mkdir(exist_ok=True)

    with ZipFile(out_dir / 'BoostDeck_ALL_Images.zip', 'w',
                 compression=ZIP_DEFLATED) as archive:
        # bar images: same ID scheme as original
        # ID 55000 = step 0 (empty track), shared across all colors
        # Then each "color" index has 32 steps
        for color_idx in range(9):
            for step in range(STEPS + 1):
                if color_idx and not step:
                    continue
                warn = (step > STEPS * 0.85)
                img = draw_glass_bar(240, 12, step, STEPS, theme, warn=warn)
                identifier = FIRST + color_idx * STEPS + step
                data = BytesIO()
                img.save(data, format='PNG', optimize=True)
                archive.writestr(ZipInfo(f'{identifier}.png'), data.getvalue(),
                                 ZIP_DEFLATED)

        # panel background images
        # 56100 = large background panel (behind all gauges)
        panel_bg = draw_glass_panel(1172, 400, theme)
        data = BytesIO()
        panel_bg.save(data, format='PNG', optimize=True)
        archive.writestr(ZipInfo('56100.png'), data.getvalue(), ZIP_DEFLATED)

        # 56300 = ethanol vertical bar background
        ethanol_bg = draw_glass_panel(40, 250, theme)
        data = BytesIO()
        ethanol_bg.save(data, format='PNG', optimize=True)
        archive.writestr(ZipInfo('56300.png'), data.getvalue(), ZIP_DEFLATED)

    print(f'Glass assets ({theme_name}) written to {out_dir}/BoostDeck_ALL_Images.zip')


def preview_all_themes(out_dir=None):
    """Generate a side-by-side preview of all themes for comparison."""
    out_dir = out_dir or ROOT / 'plugin'
    out_dir.mkdir(exist_ok=True)

    bar_w, bar_h = 240, 12
    padding = 8
    preview_steps = [0, 8, 16, 24, 32]

    for theme_name, theme in GLASS_THEMES.items():
        rows = len(preview_steps)
        img_w = bar_w + padding * 2
        img_h = rows * (bar_h + padding) + padding + 30
        preview = Image.new('RGBA', (img_w, img_h), (10, 12, 18, 255))
        draw = ImageDraw.Draw(preview)

        # title
        draw.text((padding, 4), theme_name, fill=(200, 210, 220))

        for i, step in enumerate(preview_steps):
            y = 26 + i * (bar_h + padding)
            bar = draw_glass_bar(bar_w, bar_h, step, STEPS, theme,
                                 warn=(step > STEPS * 0.85))
            preview.paste(bar, (padding, y), bar)

        fname = f'preview_glass_{theme_name.lower().replace(" ", "_")}.png'
        preview.save(out_dir / fname, format='PNG')
        print(f'Preview: {out_dir / fname}')


if __name__ == '__main__':
    import sys
    if '--preview' in sys.argv:
        preview_all_themes()
    else:
        theme = sys.argv[1] if len(sys.argv) > 1 else 'Frozen Ice'
        build_assets(theme)
