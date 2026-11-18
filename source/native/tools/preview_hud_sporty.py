"""HUD Sporty — angular swept geometry, M-sport aggressive, no round arcs."""
from math import sin, cos, radians
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
HW, HH = 800, 400


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


def bloom(img, cx, cy, radius, color, alpha=45):
    layer = Image.new('RGBA', img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for i in range(max(5, radius // 2)):
        r = radius * (1 - i / max(1, radius // 2))
        a = int(alpha * (i / max(1, radius // 2)) ** 0.3 * (max(0, radius // 2 - i) / max(1, radius // 2)) ** 0.5)
        if a > 0 and r > 1:
            d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=color[:3] + (min(255, a),))
    return Image.alpha_composite(img, layer.filter(ImageFilter.GaussianBlur(max(2, radius // 4))))


def hud_bg():
    img = Image.new('RGBA', (HW, HH), (0, 0, 0, 255))
    draw = ImageDraw.Draw(img)
    for y in range(HH):
        v = int(4 + 5 * (y / HH))
        draw.line((0, y, HW, y), fill=(v, v, v + 1))
    return img


def draw_swept_bar(img, x, y, w, h, segments, filled, colors, slant=18, direction='right'):
    """Aggressive slanted segmented bar with glow — the M-sport look."""
    draw = ImageDraw.Draw(img)
    gap = 4
    seg_w = (w - (segments - 1) * gap) / segments
    sign = 1 if direction == 'right' else -1

    for s in range(segments):
        if direction == 'right':
            sx = x + s * (seg_w + gap)
            f = s / max(1, segments - 1)
        else:
            sx = x + w - (s + 1) * (seg_w + gap) + gap
            f = s / max(1, segments - 1)

        lit = s < filled

        for row in range(h):
            row_f = row / max(1, h - 1)
            offset = sign * slant * (1 - row_f)
            lx = sx + offset
            rx = lx + seg_w

            if lit:
                c = ramp(colors, f)
                bright = 1.2 - 0.35 * row_f
                fill_c = tuple(min(255, int(v * bright)) for v in c) + (235,)
            else:
                fill_c = (255, 255, 255, 8)

            draw.line((int(lx), y + row, int(rx), y + row), fill=fill_c)

    if filled > 0 and filled < segments:
        if direction == 'right':
            glow_x = x + filled * (seg_w + gap) + slant // 2
        else:
            glow_x = x + w - filled * (seg_w + gap) - slant // 2
        tip_c = ramp(colors, filled / segments)
        img = bloom(img, int(glow_x), y + h // 2, 20, tip_c, 60)

    return img


def draw_angular_tach(img, cx, cy, w, h, rpm_frac, colors, slant=20):
    """Wide angular tach — two swept wings extending from center."""
    draw = ImageDraw.Draw(img)
    half_w = w // 2
    segments = 12
    filled_left = int(rpm_frac * segments)
    filled_right = filled_left

    # left wing — fills from center outward to the left
    img = draw_swept_bar(img, cx - half_w, cy, half_w - 20, h,
                         segments, filled_left, colors, slant=slant, direction='left')

    # right wing — fills from center outward to the right
    img = draw_swept_bar(img, cx + 20, cy, half_w - 20, h,
                         segments, filled_right, colors, slant=slant, direction='right')

    return img


# ──────────────────────────────────────────────
# CONCEPT S1: Swept Wings — bars extend from center gear
# ──────────────────────────────────────────────
def hud_swept_wings(accent, rpm=5230, boost=18.4, speed=124, gear=4, redline=8000):
    hot = (min(255, accent[0] + 70), max(25, accent[1] - 25), max(15, accent[2] - 35))
    img = hud_bg()
    draw = ImageDraw.Draw(img)
    cx = HW // 2
    rpm_frac = rpm / redline

    colors = [(30, 30, 40), accent, accent, hot, (255, 50, 40)]

    # === LAYOUT: shift lights top → wings framing gear → boost → speed/rpm ===

    # The gear sits IN the gap between the two wings — they frame it
    wing_w = 260
    wing_h = 55
    wing_y = 85
    wing_gap = 80  # half-gap each side of center
    segs = 10
    filled = int(rpm_frac * segs)

    # left wing — ends at cx - wing_gap
    img = draw_swept_bar(img, cx - wing_gap - wing_w, wing_y, wing_w, wing_h,
                         segs, filled, colors, slant=16, direction='left')
    # right wing — starts at cx + wing_gap
    img = draw_swept_bar(img, cx + wing_gap, wing_y, wing_w, wing_h,
                         segs, filled, colors, slant=16, direction='right')

    # gear — centered in the wing gap, sized to fit cleanly
    gear_cy = wing_y + wing_h // 2
    img = bloom(img, cx, gear_cy, 55, accent, 14)
    draw = ImageDraw.Draw(img)
    gf = font(100)
    gear_str = str(gear)
    gbox = draw.textbbox((0, 0), gear_str, font=gf)
    gw = gbox[2] - gbox[0]
    gh = gbox[3] - gbox[1]
    draw.text((cx - gw // 2, gear_cy - gh // 2 - 8), gear_str,
              fill=(255, 255, 255, 250), font=gf)

    # shift lights — parallelogram blocks across the top, above wings
    total_lights = 8
    lit = max(0, int((rpm_frac - 0.55) / 0.45 * total_lights)) if rpm_frac > 0.55 else 0
    light_w = 65
    light_h = 18
    light_y = wing_y - 42

    start_lx = cx - (total_lights * (light_w + 6)) // 2
    for i in range(total_lights):
        lx = start_lx + i * (light_w + 6)
        lf = i / (total_lights - 1)
        c = ramp([accent, accent, hot, (255, 50, 40)], lf)

        if i < lit:
            img = bloom(img, lx + light_w // 2, light_y + light_h // 2, 22, c, 45)
            draw = ImageDraw.Draw(img)
            pts = [(lx + 6, light_y), (lx + light_w + 6, light_y),
                   (lx + light_w, light_y + light_h), (lx, light_y + light_h)]
            draw.polygon(pts, fill=c + (240,))
            draw.line((lx + 8, light_y + 1, lx + light_w + 4, light_y + 1),
                      fill=(255, 255, 255, 55), width=1)
        else:
            draw = ImageDraw.Draw(img)
            pts = [(lx + 6, light_y), (lx + light_w + 6, light_y),
                   (lx + light_w, light_y + light_h), (lx, light_y + light_h)]
            draw.polygon(pts, fill=(255, 255, 255, 8))

    # scale under wings
    draw = ImageDraw.Draw(img)
    for i in range(5):
        f = i / 4
        val = str(int(redline * f / 1000))
        is_red = f >= 0.875
        c = (255, 50, 40, 110) if is_red else (255, 255, 255, 40)
        lx = cx - wing_gap - wing_w + int(wing_w * (1 - f))
        draw.text((lx, wing_y + wing_h + 4), val, fill=c, font=font(10))
        rx = cx + wing_gap + int(wing_w * f)
        draw.text((rx, wing_y + wing_h + 4), val, fill=c, font=font(10))

    # boost bar + value — below the wings/gear cluster
    boost_y = wing_y + wing_h + 30
    boost_frac = min(1.0, boost / 30)
    boost_w = 340
    boost_segs = 12
    boost_filled = int(boost_frac * boost_segs)

    draw.text((cx - boost_w // 2, boost_y - 2), "BOOST", fill=accent[:3] + (90,), font=font(11))
    img = draw_swept_bar(img, cx - boost_w // 2 + 55, boost_y, boost_w - 55, 18,
                         boost_segs, boost_filled, [(30, 30, 40), accent, accent], slant=7, direction='right')

    draw = ImageDraw.Draw(img)
    boost_str = f"{boost:.1f}"
    boost_text_c = tuple(min(255, int(c * 0.7 + 80)) for c in accent)
    draw.text((cx + boost_w // 2 + 8, boost_y - 5), boost_str, fill=boost_text_c + (235,), font=font(26))
    draw.text((cx + boost_w // 2 + 72, boost_y + 2), "PSI", fill=boost_text_c[:3] + (110,), font=font(12))

    # speed — bottom left
    draw.text((45, HH - 110), str(speed), fill=(255, 255, 255, 245), font=font(62))
    draw.text((45, HH - 45), "MPH", fill=(255, 255, 255, 85), font=font(16))

    # RPM — bottom right
    draw.text((HW - 165, HH - 95), str(rpm), fill=(255, 255, 255, 180), font=font(28))
    draw.text((HW - 75, HH - 88), "RPM", fill=(255, 255, 255, 85), font=font(13))

    return img


# ──────────────────────────────────────────────
# CONCEPT S2: Horizontal Sweep — F1 telemetry inspired
# ──────────────────────────────────────────────
def hud_f1_sweep(accent, rpm=5230, boost=18.4, speed=124, gear=4, redline=8000):
    hot = (min(255, accent[0] + 70), max(25, accent[1] - 25), max(15, accent[2] - 35))
    img = hud_bg()
    draw = ImageDraw.Draw(img)
    cx = HW // 2
    rpm_frac = rpm / redline

    colors = [(30, 30, 40), accent, accent, hot, (255, 50, 40)]

    # full-width tach — wide, aggressive slant, tall segments
    tach_x, tach_y = 40, 140
    tach_w, tach_h = HW - 80, 65
    segs = 20
    filled = int(rpm_frac * segs)

    img = draw_swept_bar(img, tach_x, tach_y, tach_w, tach_h,
                         segs, filled, colors, slant=20, direction='right')

    # position needle — bright white angled line
    draw = ImageDraw.Draw(img)
    needle_x = tach_x + rpm_frac * tach_w
    draw.line((int(needle_x + 8), tach_y - 5,
               int(needle_x - 8), tach_y + tach_h + 5),
              fill=(255, 255, 255, 230), width=4)

    # shift marker
    shift_frac = 6500 / redline
    shift_x = tach_x + shift_frac * tach_w
    draw.line((int(shift_x + 6), tach_y - 3,
               int(shift_x - 6), tach_y + tach_h + 3),
              fill=(255, 200, 50, 150), width=2)

    # gear — huge, above the bar
    img = bloom(img, cx, 70, 55, accent, 10)
    draw = ImageDraw.Draw(img)
    gf = font(110)
    gear_str = str(gear)
    gbox = draw.textbbox((0, 0), gear_str, font=gf)
    gw = gbox[2] - gbox[0]
    draw.text((cx - gw // 2, 15), gear_str, fill=(255, 255, 255, 250), font=gf)

    # shift lights — parallelogram blocks flanking the gear
    total = 10
    lit = max(0, int((rpm_frac - 0.5) / 0.5 * total)) if rpm_frac > 0.5 else 0

    # 5 on each side of gear
    for side in [-1, 1]:
        for i in range(5):
            idx = i if side == -1 else i + 5
            lf = idx / 9
            c = ramp([accent, accent, hot, (255, 50, 40)], lf)

            block_w = 42
            block_h = 20
            gap = 6
            if side == -1:
                bx = cx - gw // 2 - 30 - (4 - i) * (block_w + gap)
            else:
                bx = cx + gw // 2 + 30 + i * (block_w + gap)
            by = 55

            if idx < lit:
                img = bloom(img, bx + block_w // 2, by + block_h // 2, 18, c, 40)
                draw = ImageDraw.Draw(img)
                slant = 5
                pts = [(bx + slant, by), (bx + block_w + slant, by),
                       (bx + block_w, by + block_h), (bx, by + block_h)]
                draw.polygon(pts, fill=c + (240,))
            else:
                slant = 5
                pts = [(bx + slant, by), (bx + block_w + slant, by),
                       (bx + block_w, by + block_h), (bx, by + block_h)]
                draw = ImageDraw.Draw(img)
                draw.polygon(pts, fill=(255, 255, 255, 8))

    # scale under tach
    draw = ImageDraw.Draw(img)
    for i in range(9):
        f = i / 8
        tx = tach_x + int(tach_w * f)
        is_red = i >= 7
        c = (255, 50, 40, 120) if is_red else (255, 255, 255, 50)
        draw.line((tx, tach_y + tach_h + 4, tx, tach_y + tach_h + 12), fill=c, width=1)
        if i % 2 == 0:
            draw.text((tx - 4, tach_y + tach_h + 15), str(i), fill=c, font=font(13))

    # boost — bottom center, angular bar
    boost_frac = min(1.0, boost / 30)
    boost_w = 260
    boost_filled = int(boost_frac * 10)
    boost_y = 260
    draw.text((cx - boost_w // 2, boost_y - 2), "BOOST", fill=accent[:3] + (90,), font=font(10))
    img = draw_swept_bar(img, cx - boost_w // 2 + 50, boost_y, boost_w - 50, 16,
                         10, boost_filled, [(30, 30, 40), accent, accent], slant=6, direction='right')
    draw = ImageDraw.Draw(img)
    boost_str = f"{boost:.1f}"
    boost_c = tuple(min(255, int(c * 0.7 + 80)) for c in accent)
    draw.text((cx + boost_w // 2 + 10, boost_y - 5), boost_str, fill=boost_c + (230,), font=font(24))
    draw.text((cx + boost_w // 2 + 65, boost_y), "PSI", fill=boost_c[:3] + (110,), font=font(12))

    # speed — bottom left
    draw.text((45, HH - 100), str(speed), fill=(255, 255, 255, 240), font=font(58))
    draw.text((45, HH - 40), "MPH", fill=(255, 255, 255, 80), font=font(14))

    # RPM digital — bottom right
    draw.text((HW - 155, HH - 85), str(rpm), fill=(255, 255, 255, 175), font=font(26))
    draw.text((HW - 70, HH - 80), "RPM", fill=(255, 255, 255, 80), font=font(12))

    return img


# ──────────────────────────────────────────────
# CONCEPT S3: Climbing Ramp — G80 M3 inspired rising bar
# ──────────────────────────────────────────────
def hud_ramp(accent, rpm=5230, boost=18.4, speed=124, gear=4, redline=8000):
    hot = (min(255, accent[0] + 70), max(25, accent[1] - 25), max(15, accent[2] - 35))
    img = hud_bg()
    draw = ImageDraw.Draw(img)
    cx = HW // 2
    rpm_frac = rpm / redline

    # climbing ramp — segments get taller from left to right
    ramp_x, ramp_y_base = 60, 250
    ramp_w = HW - 120
    segs = 24
    gap = 3
    seg_w = (ramp_w - (segs - 1) * gap) / segs
    filled = int(rpm_frac * segs)
    slant = 8

    colors = [(30, 30, 40), accent, accent, hot, (255, 50, 40)]

    for s in range(segs):
        sx = ramp_x + s * (seg_w + gap)
        f = s / max(1, segs - 1)
        # height ramps up — taller segments at higher RPM
        seg_h = int(30 + 55 * f)
        sy = ramp_y_base - seg_h
        lit = s < filled

        for row in range(seg_h):
            row_f = row / max(1, seg_h - 1)
            offset = slant * (1 - row_f)
            lx = sx + offset
            rx = lx + seg_w

            if lit:
                c = ramp(colors, f)
                bright = 1.15 - 0.3 * row_f
                fill_c = tuple(min(255, int(v * bright)) for v in c) + (235,)
            else:
                is_red = f >= 0.875
                fill_c = (255, 255, 255, 10 if not is_red else 6)

            draw.line((int(lx), sy + row, int(rx), sy + row), fill=fill_c)

    # glow at tip
    if filled > 0 and filled < segs:
        glow_x = ramp_x + filled * (seg_w + gap) + slant // 2
        seg_h = int(30 + 55 * (filled / segs))
        glow_y = ramp_y_base - seg_h // 2
        tip_c = ramp(colors, filled / segs)
        img = bloom(img, int(glow_x), glow_y, 22, tip_c, 60)
        draw = ImageDraw.Draw(img)

    # gear — large, above the ramp center
    img = bloom(img, cx, 85, 55, accent, 10)
    draw = ImageDraw.Draw(img)
    gf = font(120)
    gear_str = str(gear)
    gbox = draw.textbbox((0, 0), gear_str, font=gf)
    gw = gbox[2] - gbox[0]
    draw.text((cx - gw // 2, 25), gear_str, fill=(255, 255, 255, 250), font=gf)

    # shift lights — small angular dots above gear
    total = 6
    lit_lights = max(0, int((rpm_frac - 0.6) / 0.4 * total)) if rpm_frac > 0.6 else 0
    for i in range(total):
        lf = i / (total - 1)
        c = ramp([accent, accent, hot, (255, 50, 40)], lf)
        dx = cx - (total - 1) * 25 // 2 + i * 25
        dy = 22
        if i < lit_lights:
            img = bloom(img, dx, dy, 12, c, 50)
            draw = ImageDraw.Draw(img)
            draw.rounded_rectangle((dx - 8, dy - 5, dx + 8, dy + 5), radius=3, fill=c + (240,))
        else:
            draw = ImageDraw.Draw(img)
            draw.rounded_rectangle((dx - 8, dy - 5, dx + 8, dy + 5), radius=3, fill=(255, 255, 255, 8))

    # boost below gear
    boost_c = tuple(min(255, int(c * 0.7 + 80)) for c in accent)
    boost_str = f"{boost:.1f}"
    bf = font(28)
    bbox = draw.textbbox((0, 0), boost_str, font=bf)
    bw = bbox[2] - bbox[0]
    draw.text((cx - bw // 2 - 10, 150), boost_str, fill=boost_c + (230,), font=bf)
    draw.text((cx + bw // 2 - 4, 156), "PSI", fill=boost_c[:3] + (110,), font=font(13))

    # scale under ramp
    for i in range(9):
        f = i / 8
        tx = ramp_x + int(ramp_w * f)
        is_red = i >= 7
        c = (255, 50, 40, 110) if is_red else (255, 255, 255, 45)
        draw.text((tx - 4, ramp_y_base + 6), str(i), fill=c, font=font(12))

    # speed — bottom left
    draw.text((45, HH - 100), str(speed), fill=(255, 255, 255, 240), font=font(58))
    draw.text((45, HH - 40), "MPH", fill=(255, 255, 255, 80), font=font(14))

    # RPM — bottom right
    draw.text((HW - 155, HH - 85), str(rpm), fill=(255, 255, 255, 175), font=font(26))
    draw.text((HW - 70, HH - 80), "RPM", fill=(255, 255, 255, 80), font=font(12))

    return img


def main():
    out = ROOT / 'plugin'
    colors = [
        ('orange', (255, 140, 30)),
        ('ice', (80, 180, 255)),
        ('purple', (155, 75, 215)),
        ('red', (225, 40, 50)),
    ]
    for cname, accent in colors:
        for concept, fn in [('wings', hud_swept_wings), ('f1', hud_f1_sweep), ('ramp', hud_ramp)]:
            img = fn(accent)
            p = out / f'hud_sporty_{concept}_{cname}.png'
            img.save(p, format='PNG', optimize=True)
            print(f'{concept}_{cname}: {p}')


if __name__ == '__main__':
    main()
