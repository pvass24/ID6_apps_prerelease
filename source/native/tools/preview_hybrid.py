"""Hybrid concept: arc gauges + luxury dark + segmented bars + ambient-ready."""
from math import sin, cos, radians
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
W, H = 1280, 480


def get_font(size):
    for path in [
        "/System/Library/Fonts/Supplemental/DIN Condensed Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]:
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


def ramp_at(colors, f):
    f = max(0, min(1, f))
    n = len(colors) - 1
    i = min(n - 1, int(f * n))
    t = f * n - i
    return tuple(int(colors[i][j] + (colors[i+1][j] - colors[i][j]) * t) for j in range(3))


def soft_glow(img, cx, cy, radius, color, alpha=30):
    layer = Image.new('RGBA', img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for r in range(radius, 0, -3):
        a = int(alpha * ((radius - r) / radius) ** 0.5)
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=color[:3] + (min(255, a),))
    return Image.alpha_composite(img, layer.filter(ImageFilter.GaussianBlur(max(2, radius // 5))))


def glass_panel(img, x, y, w, h, r=14, opacity=0.12, base=(12, 13, 18), edge=(45, 50, 65)):
    panel = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    pd = ImageDraw.Draw(panel)
    a = int(255 * opacity)
    pd.rounded_rectangle((0, 0, w-1, h-1), radius=r, fill=base + (a,))
    # top inner glow
    for py in range(min(h // 4, 30)):
        fa = 1 - py / min(h // 4, 30)
        pd.line((r, py, w - r, py), fill=(255, 255, 255, int(10 * fa)))
    pd.rounded_rectangle((0, 0, w-1, h-1), radius=r, outline=edge + (35,), width=1)
    pd.line((r + 4, 1, w - r - 4, 1), fill=(255, 255, 255, 22), width=1)
    img.paste(panel, (x, y), panel)
    return img


def draw_segmented_bar(img, x, y, w, h, segments, filled, colors, slant=0):
    """Redline-style segmented bar with slant and color ramp."""
    draw = ImageDraw.Draw(img)
    seg_w = (w - (segments - 1) * 3) / segments

    for s in range(segments):
        sx = x + s * (seg_w + 3)
        f = s / (segments - 1)
        is_lit = s < filled

        # slanted parallelogram points
        pts = [
            (sx + slant, y),
            (sx + seg_w + slant, y),
            (sx + seg_w, y + h),
            (sx, y + h),
        ]

        if is_lit:
            c = ramp_at(colors, f)
            # vertical gradient within segment
            for row in range(h):
                row_f = row / h
                bright = 1.15 - 0.3 * row_f
                rc = tuple(min(255, int(v * bright)) for v in c)
                lx = sx + slant * (1 - row / h)
                rx = sx + seg_w + slant * (1 - row / h)
                draw.line((int(lx), y + row, int(rx), y + row), fill=rc + (225,))
        else:
            # dark segment
            for row in range(h):
                lx = sx + slant * (1 - row / h)
                rx = sx + seg_w + slant * (1 - row / h)
                is_redzone = f >= 0.85
                dark = (35, 18, 20) if is_redzone else (18, 22, 30)
                draw.line((int(lx), y + row, int(rx), y + row), fill=dark + (180,))

    # glow at fill edge
    if filled > 0:
        glow_x = x + filled * (seg_w + 3) - 3
        img = soft_glow(img, int(glow_x), y + h // 2, 15, ramp_at(colors, filled / segments), 40)

    return img


def draw_arc_gauge(img, cx, cy, r_out, r_in, fill_frac, colors, glow_color):
    start_deg, sweep = 150, 240

    # render at 2x then downscale for anti-aliasing
    scale = 2
    buf_w, buf_h = img.width * scale, img.height * scale
    buf = Image.new('RGBA', (buf_w, buf_h), (0, 0, 0, 0))
    scx, scy = cx * scale, cy * scale
    sr_out, sr_in = r_out * scale, r_in * scale

    # track — draw as thick arcs using PIL
    draw_buf = ImageDraw.Draw(buf)
    thickness = sr_out - sr_in
    mid_r = (sr_out + sr_in) // 2
    bbox_track = (scx - mid_r, scy - mid_r, scx + mid_r, scy + mid_r)
    draw_buf.arc(bbox_track, start_deg, start_deg + sweep, fill=(28, 34, 48, 70), width=thickness)

    # filled arc — draw in segments for color ramp
    fill_end = start_deg + sweep * fill_frac
    seg_count = max(1, int((fill_end - start_deg) * 2))
    for s in range(seg_count):
        a0 = start_deg + (fill_end - start_deg) * s / seg_count
        a1 = start_deg + (fill_end - start_deg) * (s + 1) / seg_count
        f = s / max(1, seg_count - 1)
        c = ramp_at(colors, f * fill_frac)
        draw_buf.arc(bbox_track, a0, a1 + 0.5, fill=c + (235,), width=thickness)

    # downscale for smooth edges
    buf_small = buf.resize((img.width, img.height), Image.LANCZOS)
    img = Image.alpha_composite(img, buf_small)

    # glow at tip
    tip_rad = radians(fill_end)
    tip_r = (r_in + r_out) / 2
    tx = int(cx + cos(tip_rad) * tip_r)
    ty = int(cy + sin(tip_rad) * tip_r)
    img = soft_glow(img, tx, ty, 18, glow_color, 60)

    # tick marks
    draw = ImageDraw.Draw(img)
    for i in range(9):
        tf = i / 8
        angle = start_deg + sweep * tf
        rad = radians(angle)
        ro = r_out + 4
        ri = r_in - (6 if i % 2 == 0 else 3)
        x1, y1 = int(cx + cos(rad) * ro), int(cy + sin(rad) * ro)
        x2, y2 = int(cx + cos(rad) * ri), int(cy + sin(rad) * ri)
        ta = 80 if i % 2 == 0 else 40
        draw.line((x1, y1, x2, y2), fill=(90, 100, 120, ta), width=2 if i % 2 == 0 else 1)

    return img


def build_ambient_theme(accent):
    """Build a full color palette from a single ambient accent color."""
    r, g, b = accent
    brightness = (r + g + b) / 3

    # derive ramp from accent
    dark = tuple(max(5, int(c * 0.2)) for c in accent)
    mid = tuple(max(10, int(c * 0.6)) for c in accent)
    full = accent
    bright = tuple(min(255, int(c * 1.3 + 40)) for c in accent)

    # warn/crit always warm
    warn_start = (min(255, r + 60), max(0, g - 20), max(0, b - 40))
    crit = (255, 50, 40)

    return {
        'accent': accent,
        'ramp': [dark, mid, full, bright],
        'hot_ramp': [dark, mid, full, warn_start, crit],
        'glow': accent,
        'dim': tuple(min(255, int(c * 0.5 + 60)) for c in accent),
        'text': (245, 248, 255),
        'label': tuple(min(255, int(c * 0.5 + 90)) for c in accent),
    }


def render_hybrid(accent_color, label='Ambient Match'):
    theme = build_ambient_theme(accent_color)
    img = Image.new('RGBA', (W, H), (0, 0, 0, 255))
    draw = ImageDraw.Draw(img)

    # near-black background with very subtle warm center
    for y in range(H):
        f = y / H
        center_v = max(0, 0.5 - abs(f - 0.38)) * 2
        base = tuple(int(3 + 6 * center_v + accent_color[i] * 0.015 * center_v) for i in range(3))
        draw.line((0, y, W, y), fill=base)

    # subtle ambient glow behind center
    img = soft_glow(img, W // 2, 175, 280, accent_color, 6)
    # secondary glow pools behind side arcs
    img = soft_glow(img, 210, 190, 140, accent_color, 4)
    img = soft_glow(img, W - 210, 190, 140, accent_color, 4)

    # === THREE ARC GAUGES ===
    arc_data = [
        {'cx': 210,    'cy': 195, 'r_out': 108, 'r_in': 96,  'label': 'AFR',     'val': '14.2', 'unit': '',    'fill': 0.52},
        {'cx': W // 2, 'cy': 180, 'r_out': 148, 'r_in': 133, 'label': 'BOOST',   'val': '18.4', 'unit': 'psi', 'fill': 0.52},
        {'cx': W - 210,'cy': 195, 'r_out': 108, 'r_in': 96,  'label': 'TIMING',  'val': '12.3', 'unit': '°',  'fill': 0.46},
    ]

    for g in arc_data:
        cx, cy = g['cx'], g['cy']
        is_hero = g['label'] == 'BOOST'
        panel_w = 290 if is_hero else 220
        panel_h = 310 if is_hero else 270

        img = glass_panel(img, cx - panel_w // 2, 28 if is_hero else 48,
                          panel_w, panel_h, r=16 if is_hero else 14)

        img = draw_arc_gauge(img, cx, cy, g['r_out'], g['r_in'], g['fill'],
                             theme['hot_ramp'] if is_hero else theme['ramp'],
                             theme['glow'])

        draw = ImageDraw.Draw(img)

        # value — large, pure white, no backing needed since arcs are pushed out
        vsize = 62 if is_hero else 42
        vf = get_font(vsize)
        bbox = draw.textbbox((0, 0), g['val'], font=vf)
        tw = bbox[2] - bbox[0]
        draw.text((cx - tw // 2, cy - vsize // 2 - 4), g['val'],
                  fill=(255, 255, 255), font=vf)

        # unit
        if g['unit']:
            uf = get_font(18 if is_hero else 14)
            ubbox = draw.textbbox((0, 0), g['unit'], font=uf)
            uw = ubbox[2] - ubbox[0]
            draw.text((cx - uw // 2, cy + vsize // 2), g['unit'],
                      fill=theme['label'], font=uf)

        # label BELOW the arc, between value and bottom of panel
        lsize = 18 if is_hero else 14
        lf = get_font(lsize)
        lbbox = draw.textbbox((0, 0), g['label'], font=lf)
        lw = lbbox[2] - lbbox[0]
        panel_top = 28 if is_hero else 48
        panel_h_val = 310 if is_hero else 270
        label_y = panel_top + panel_h_val - 30 if is_hero else panel_top + panel_h_val - 25
        label_color = tuple(min(255, int(c * 0.6 + 100)) for c in accent_color)
        draw.text((cx - lw // 2, label_y), g['label'], fill=label_color, font=lf)

    # === BOTTOM STRIP: Segmented bars + readouts ===
    strip_y = 355
    img = glass_panel(img, 35, strip_y, W - 70, 110, r=10, opacity=0.1)

    readings = [
        {'name': 'OIL',     'val': '4.2',  'unit': 'psi', 'fill': 8,  'total': 16},
        {'name': 'COOLANT', 'val': '195',  'unit': '°F',  'fill': 12, 'total': 16},
        {'name': 'TRANS',   'val': '168',  'unit': '°F',  'fill': 10, 'total': 16},
        {'name': 'INTAKE',  'val': '122',  'unit': '°F',  'fill': 13, 'total': 16, 'warn': True},
        {'name': 'RAIL',    'val': '2180', 'unit': 'psi', 'fill': 9,  'total': 16},
    ]

    col_w = (W - 100) // len(readings)
    for i, rd in enumerate(readings):
        rx = 55 + i * col_w
        draw = ImageDraw.Draw(img)

        # label
        draw.text((rx, strip_y + 10), rd['name'], fill=theme['label'], font=get_font(10))

        # value
        vf = get_font(32)
        draw.text((rx, strip_y + 22), rd['val'], fill=(255, 255, 255), font=vf)
        vbox = draw.textbbox((rx, strip_y + 22), rd['val'], font=vf)
        draw.text((vbox[2] + 4, strip_y + 34), rd['unit'],
                  fill=theme['label'], font=get_font(13))

        # segmented bar — accent ramp for normal, hot ramp only for warn
        bar_colors = theme['hot_ramp'] if rd.get('warn') else theme['ramp']
        img = draw_segmented_bar(img, rx, strip_y + 70, col_w - 30, 20,
                                 rd['total'], rd['fill'], bar_colors, slant=8)

        # divider
        if i < len(readings) - 1:
            draw = ImageDraw.Draw(img)
            div_x = rx + col_w - 15
            draw.line((div_x, strip_y + 12, div_x, strip_y + 95),
                      fill=(255, 255, 255, 8), width=1)

    # === TITLE ===
    draw = ImageDraw.Draw(img)
    draw.text((30, 6), "BoostDeck", fill=theme['dim'], font=get_font(18))
    draw.text((W - 85, 8), "2:49 pm", fill=(60, 65, 75), font=get_font(14))

    # thin accent line under title
    draw.line((30, 26, W - 30, 26), fill=accent_color + (20,), width=1)

    # ambient accent strip at very bottom (simulating the car's ambient light)
    for x in range(40, W - 40):
        f = (x - 40) / (W - 80)
        center = abs(f - 0.5) * 2
        a = int(18 * (1 - center ** 2))
        draw.line((x, H - 3, x, H), fill=accent_color + (a,))

    return img


def main():
    out_dir = ROOT / 'plugin'

    # generate for multiple ambient colors
    ambients = {
        'ambient_orange':  (255, 140, 30),    # warm amber (like the photo)
        'ambient_ice':     (80, 180, 255),     # cool blue
        'ambient_white':   (200, 210, 230),    # ice white
        'ambient_red':     (230, 40, 50),      # M red
        'ambient_purple':  (160, 80, 220),     # purple
        'ambient_cyan':    (40, 220, 210),     # teal/cyan
        'ambient_green':   (50, 200, 100),     # emerald
    }

    for name, color in ambients.items():
        img = render_hybrid(color, name)
        path = out_dir / f'hybrid_{name}.png'
        img.save(path, format='PNG', optimize=True)
        print(f'{name}: {path}')


if __name__ == '__main__':
    main()
