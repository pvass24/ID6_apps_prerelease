"""Polished hybrid BoostDeck — premium glass aesthetic for iDrive 6."""
from math import sin, cos, radians, pi
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
W, H = 1280, 480


def font(size):
    for p in [
        "/System/Library/Fonts/Supplemental/DIN Condensed Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]:
        try:
            return ImageFont.truetype(p, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


def ramp(colors, f):
    f = max(0.0, min(1.0, f))
    n = len(colors) - 1
    i = min(n - 1, int(f * n))
    t = f * n - i
    return tuple(int(colors[i][j] + (colors[i+1][j] - colors[i][j]) * t) for j in range(3))


def glow(img, cx, cy, radius, color, alpha=30):
    layer = Image.new('RGBA', img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    steps = max(4, radius // 2)
    for i in range(steps):
        r = radius * (1 - i / steps)
        a = int(alpha * (i / steps) ** 0.4 * ((steps - i) / steps) ** 0.6)
        if a > 0 and r > 0:
            d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=color[:3] + (a,))
    blur_r = max(2, radius // 4)
    return Image.alpha_composite(img, layer.filter(ImageFilter.GaussianBlur(blur_r)))


def glass_panel(w, h, base_color=(12, 14, 20), edge_color=(50, 60, 80), r=14, opacity=0.30):
    panel = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(panel)

    # base fill with vertical gradient
    for y in range(h):
        yf = y / h
        fade = 1.0 - 0.25 * yf
        a = int(255 * opacity * fade)
        c = tuple(int(v * fade) for v in base_color)
        d.line((0, y, w, y), fill=c + (a,))

    # mask to rounded rect
    mask = Image.new('L', (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, w-1, h-1), radius=r, fill=255)
    panel.putalpha(mask)

    # edge
    d = ImageDraw.Draw(panel)
    d.rounded_rectangle((0, 0, w-1, h-1), radius=r, outline=edge_color + (40,), width=1)

    # top highlight — two lines, outer brighter
    d.line((r + 4, 1, w - r - 4, 1), fill=(255, 255, 255, 28), width=1)
    d.line((r + 8, 2, w - r - 8, 2), fill=(255, 255, 255, 12), width=1)

    # bottom edge catch
    d.line((r + 12, h - 2, w - r - 12, h - 2), fill=(255, 255, 255, 6), width=1)

    return panel


def draw_smooth_arc(img, cx, cy, r_out, r_in, fill_frac, colors, glow_color,
                    start_deg=150, sweep=240, track_color=(28, 35, 50)):
    """Anti-aliased arc gauge rendered at 3x then downscaled."""
    scale = 3
    buf_w, buf_h = img.width * scale, img.height * scale
    buf = Image.new('RGBA', (buf_w, buf_h), (0, 0, 0, 0))
    bd = ImageDraw.Draw(buf)

    scx, scy = cx * scale, cy * scale
    sr_out, sr_in = r_out * scale, r_in * scale
    thickness = sr_out - sr_in
    mid_r = (sr_out + sr_in) // 2
    bbox = (scx - mid_r, scy - mid_r, scx + mid_r, scy + mid_r)

    # track
    bd.arc(bbox, start_deg, start_deg + sweep, fill=track_color + (65,), width=thickness)

    # filled arc in fine color segments
    if fill_frac > 0.002:
        fill_end = start_deg + sweep * fill_frac
        seg_count = max(2, int(fill_frac * 200))
        for s in range(seg_count):
            a0 = start_deg + (fill_end - start_deg) * s / seg_count
            a1 = start_deg + (fill_end - start_deg) * (s + 1) / seg_count + 0.3
            f = (s / max(1, seg_count - 1)) * fill_frac
            c = ramp(colors, f)
            bd.arc(bbox, a0, a1, fill=c + (245,), width=thickness)

        # outer bloom — draw a wider, softer copy of the filled arc on a separate layer
        bloom_buf = Image.new('RGBA', (buf_w, buf_h), (0, 0, 0, 0))
        bloom_d = ImageDraw.Draw(bloom_buf)
        bloom_thickness = thickness + scale * 12
        bloom_mid = (sr_out + sr_in) // 2
        bloom_bbox = (scx - bloom_mid, scy - bloom_mid, scx + bloom_mid, scy + bloom_mid)
        for s in range(max(2, seg_count // 3)):
            a0 = start_deg + (fill_end - start_deg) * s / max(1, seg_count // 3)
            a1 = start_deg + (fill_end - start_deg) * (s + 1) / max(1, seg_count // 3) + 0.5
            f = (s / max(1, seg_count // 3 - 1)) * fill_frac
            c = ramp(colors, f)
            bloom_d.arc(bloom_bbox, a0, a1, fill=c + (50,), width=bloom_thickness)
        bloom_buf = bloom_buf.filter(ImageFilter.GaussianBlur(radius=scale * 6))
        buf = Image.alpha_composite(buf, bloom_buf)

    buf_small = buf.resize((img.width, img.height), Image.LANCZOS)
    img = Image.alpha_composite(img, buf_small)

    # glow at tip
    if fill_frac > 0.01:
        fill_end = start_deg + sweep * fill_frac
        tip_rad = radians(fill_end)
        tip_r = (r_in + r_out) / 2
        tx = int(cx + cos(tip_rad) * tip_r)
        ty = int(cy + sin(tip_rad) * tip_r)
        tip_color = ramp(colors, fill_frac)
        img = glow(img, tx, ty, 22, tip_color, 65)

    # tick marks
    draw = ImageDraw.Draw(img)
    for i in range(9):
        tf = i / 8
        angle = start_deg + sweep * tf
        rad = radians(angle)
        is_major = i % 2 == 0
        ro = r_out + 5
        ri = r_in - (7 if is_major else 3)
        x1 = int(cx + cos(rad) * ro)
        y1 = int(cy + sin(rad) * ro)
        x2 = int(cx + cos(rad) * ri)
        y2 = int(cy + sin(rad) * ri)
        tick_color = (100, 115, 140, 80) if is_major else (70, 80, 100, 40)
        draw.line((x1, y1, x2, y2), fill=tick_color, width=2 if is_major else 1)

    return img


def draw_segmented_bar(img, x, y, w, h, total_segs, filled, colors, slant=6):
    draw = ImageDraw.Draw(img)
    gap = 2
    seg_w = (w - (total_segs - 1) * gap) / total_segs

    for s in range(total_segs):
        sx = x + s * (seg_w + gap)
        f = s / max(1, total_segs - 1)
        lit = s < filled

        for row in range(h):
            row_f = row / max(1, h - 1)
            lx = sx + slant * (1 - row_f)
            rx = lx + seg_w

            if lit:
                c = ramp(colors, f)
                bright = 1.1 - 0.25 * row_f
                fill_c = tuple(min(255, int(v * bright)) for v in c) + (215,)
            else:
                is_red = f >= 0.85
                base = (30, 16, 18) if is_red else (16, 20, 28)
                fill_c = base + (140,)

            draw.line((int(lx), y + row, int(rx), y + row), fill=fill_c)

    if filled > 0 and filled < total_segs:
        glow_x = x + filled * (seg_w + gap)
        tip_c = ramp(colors, filled / total_segs)
        img = glow(img, int(glow_x), y + h // 2, 14, tip_c, 45)

    return img


def ambient_palette(accent):
    r, g, b = accent
    dark = tuple(max(5, int(c * 0.15)) for c in accent)
    mid = tuple(max(10, int(c * 0.5)) for c in accent)
    bright = tuple(min(255, int(c * 1.2 + 50)) for c in accent)
    return {
        'ramp': [dark, mid, accent, bright],
        'hot': [dark, mid, accent, (min(255, r + 80), max(0, g - 30), max(0, b - 50)), (255, 50, 40)],
        'glow': accent,
        'label': tuple(min(255, int(c * 0.55 + 105)) for c in accent),
        'dim': tuple(min(255, int(c * 0.4 + 70)) for c in accent),
    }


def render(accent, name=''):
    pal = ambient_palette(accent)
    img = Image.new('RGBA', (W, H), (0, 0, 0, 255))
    draw = ImageDraw.Draw(img)

    # background: near-black with subtle radial warmth from center
    for y in range(H):
        yf = y / H
        v = max(0, 0.5 - abs(yf - 0.38)) * 2
        base = tuple(max(2, int(3 + 8 * v + accent[i] * 0.012 * v)) for i in range(3))
        draw.line((0, y, W, y), fill=base)

    # ambient glow pools
    img = glow(img, W // 2, 180, 300, accent, 7)
    img = glow(img, 205, 195, 160, accent, 4)
    img = glow(img, W - 205, 195, 160, accent, 4)

    # ── ARC GAUGES ──
    arcs = [
        {'cx': 205,    'cy': 200, 'ro': 105, 'ri': 92,  'name': 'AFR',    'val': '14.2', 'unit': '',    'fill': 0.52, 'hero': False},
        {'cx': W // 2, 'cy': 185, 'ro': 145, 'ri': 128, 'name': 'BOOST',  'val': '18.4', 'unit': 'psi', 'fill': 0.52, 'hero': True},
        {'cx': W - 205,'cy': 200, 'ro': 105, 'ri': 92,  'name': 'TIMING', 'val': '12.3', 'unit': '°',  'fill': 0.46, 'hero': False},
    ]

    for a in arcs:
        cx, cy, hero = a['cx'], a['cy'], a['hero']
        pw = 300 if hero else 230
        ph = 320 if hero else 280
        px = cx - pw // 2
        py = 25 if hero else 42

        # glass panel
        panel = glass_panel(pw, ph,
                            base_color=(10, 12, 18),
                            edge_color=tuple(min(120, int(c * 0.3 + 30)) for c in accent),
                            r=16 if hero else 14,
                            opacity=0.28 if hero else 0.22)
        img.paste(panel, (px, py), panel)

        # arc
        colors = pal['hot'] if hero else pal['ramp']
        img = draw_smooth_arc(img, cx, cy, a['ro'], a['ri'], a['fill'], colors, pal['glow'])

        draw = ImageDraw.Draw(img)

        # value
        vs = 64 if hero else 44
        vf = font(vs)
        vbox = draw.textbbox((0, 0), a['val'], font=vf)
        vw = vbox[2] - vbox[0]
        vh = vbox[3] - vbox[1]
        draw.text((cx - vw // 2, cy - vh // 2 - 6), a['val'], fill=(255, 255, 255), font=vf)

        # unit below value
        if a['unit']:
            uf = font(18 if hero else 14)
            ubox = draw.textbbox((0, 0), a['unit'], font=uf)
            uw = ubox[2] - ubox[0]
            draw.text((cx - uw // 2, cy + vh // 2 + 2), a['unit'], fill=pal['dim'], font=uf)

        # label at bottom of panel
        lf = font(18 if hero else 15)
        lbox = draw.textbbox((0, 0), a['name'], font=lf)
        lw = lbox[2] - lbox[0]
        draw.text((cx - lw // 2, py + ph - 28), a['name'], fill=pal['label'], font=lf)

    # ── BOTTOM STRIP ──
    strip_y = 360
    strip_h = 105
    strip_panel = glass_panel(W - 70, strip_h,
                              base_color=(10, 12, 18),
                              edge_color=tuple(min(100, int(c * 0.25 + 25)) for c in accent),
                              r=10, opacity=0.2)
    img.paste(strip_panel, (35, strip_y), strip_panel)

    readings = [
        {'name': 'OIL',     'val': '4.2',  'unit': 'psi', 'segs': 16, 'filled': 8,  'warn': False},
        {'name': 'COOLANT', 'val': '195',  'unit': '°F',  'segs': 16, 'filled': 12, 'warn': False},
        {'name': 'TRANS',   'val': '168',  'unit': '°F',  'segs': 16, 'filled': 10, 'warn': False},
        {'name': 'INTAKE',  'val': '122',  'unit': '°F',  'segs': 16, 'filled': 14, 'warn': True},
        {'name': 'RAIL',    'val': '2180', 'unit': 'psi', 'segs': 16, 'filled': 9,  'warn': False},
    ]

    col_w = (W - 110) // len(readings)
    for i, rd in enumerate(readings):
        rx = 60 + i * col_w
        draw = ImageDraw.Draw(img)

        # label
        draw.text((rx, strip_y + 10), rd['name'], fill=pal['label'], font=font(12))

        # value
        vf = font(34)
        draw.text((rx, strip_y + 24), rd['val'], fill=(255, 255, 255), font=vf)
        vbox = draw.textbbox((rx, strip_y + 24), rd['val'], font=vf)
        draw.text((vbox[2] + 4, strip_y + 38), rd['unit'], fill=pal['dim'], font=font(14))

        # segmented bar
        colors = pal['hot'] if rd['warn'] else pal['ramp']
        img = draw_segmented_bar(img, rx, strip_y + 72, col_w - 30, 18,
                                 rd['segs'], rd['filled'], colors, slant=6)

        # divider
        if i < len(readings) - 1:
            draw = ImageDraw.Draw(img)
            dx = rx + col_w - 14
            draw.line((dx, strip_y + 12, dx, strip_y + strip_h - 12),
                      fill=(255, 255, 255, 10), width=1)

    # ── TITLE BAR ──
    draw = ImageDraw.Draw(img)
    draw.text((30, 5), "BoostDeck", fill=pal['label'], font=font(18))
    draw.text((W - 82, 7), "2:49 pm", fill=(55, 62, 75), font=font(14))
    draw.line((30, 24, W - 30, 24), fill=accent + (15,), width=1)

    # ── AMBIENT STRIP at bottom edge ──
    for x in range(35, W - 35):
        f = (x - 35) / (W - 70)
        center = 1 - (2 * abs(f - 0.5)) ** 1.5
        a = int(22 * center)
        if a > 0:
            draw.line((x, H - 2, x, H), fill=accent + (a,))

    return img


def main():
    out = ROOT / 'plugin'
    ambients = {
        'polished_orange':  (255, 140, 30),
        'polished_ice':     (80, 180, 255),
        'polished_white':   (195, 205, 225),
        'polished_red':     (225, 40, 50),
        'polished_purple':  (155, 75, 215),
        'polished_cyan':    (40, 215, 205),
    }
    for name, color in ambients.items():
        img = render(color, name)
        p = out / f'{name}.png'
        img.save(p, format='PNG', optimize=True)
        print(f'{name}: {p}')


if __name__ == '__main__':
    main()
