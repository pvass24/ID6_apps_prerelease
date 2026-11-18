"""Glass ShiftDeck V2 — tach-dominant racing display."""
from math import sin, cos, radians
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
    for i in range(max(4, radius // 2)):
        r = radius * (1 - i / max(1, radius // 2))
        a = int(alpha * (i / max(1, radius // 2)) ** 0.4 * (max(0, (radius // 2 - i)) / max(1, radius // 2)) ** 0.6)
        if a > 0 and r > 1:
            d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=color[:3] + (min(255, a),))
    return Image.alpha_composite(img, layer.filter(ImageFilter.GaussianBlur(max(2, radius // 4))))


def glass_panel(w, h, base=(10, 12, 18), edge=(50, 60, 80), r=14, opacity=0.28):
    panel = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(panel)
    for y in range(h):
        yf = y / h
        fade = 1.0 - 0.2 * yf
        a = int(255 * opacity * fade)
        c = tuple(int(v * fade) for v in base)
        d.line((0, y, w, y), fill=c + (a,))
    mask = Image.new('L', (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, w-1, h-1), radius=r, fill=255)
    panel.putalpha(mask)
    d = ImageDraw.Draw(panel)
    d.rounded_rectangle((0, 0, w-1, h-1), radius=r, outline=edge + (35,), width=1)
    d.line((r + 4, 1, w - r - 4, 1), fill=(255, 255, 255, 22), width=1)
    return panel


def pal(accent):
    r, g, b = accent
    # tach always ramps from cool blue → accent → red regardless of accent color
    # this ensures the danger zone ALWAYS contrasts
    tach_ramp = [(15, 40, 90), (30, 80, 160), accent, (min(255, r + 60), max(30, g - 20), max(20, b - 30)), (255, 50, 40)]
    # shift lights: dim accent → bright accent → warm → red
    light_ramp = [
        tuple(max(15, int(c * 0.4)) for c in accent),  # dim accent
        tuple(max(20, int(c * 0.6)) for c in accent),  # mid accent
        accent,                                          # full accent
        accent,                                          # full accent
        (min(255, r + 60), max(40, g - 10), max(20, b - 20)),  # warm
        (240, 55, 40),                                   # red
    ]
    return {
        'ramp': [(15, 40, 90), (30, 80, 160), accent, tuple(min(255, int(c * 1.2 + 50)) for c in accent)],
        'hot': tach_ramp,
        'light_ramp': light_ramp,
        'glow': accent,
        'label': tuple(min(255, int(c * 0.55 + 105)) for c in accent),
        'dim': tuple(min(255, int(c * 0.4 + 70)) for c in accent),
    }


def render(accent, rpm=5230, speed=124, gear=4, redline=8000, shift_at=6500):
    p = pal(accent)
    img = Image.new('RGBA', (W, H), (0, 0, 0, 255))
    draw = ImageDraw.Draw(img)

    # background
    for y in range(H):
        yf = y / H
        v = max(0, 0.5 - abs(yf - 0.5)) * 2
        base = tuple(max(2, int(3 + 5 * v + accent[i] * 0.008 * v)) for i in range(3))
        draw.line((0, y, W, y), fill=base)

    rpm_frac = rpm / redline
    edge_c = tuple(min(100, int(c * 0.3 + 25)) for c in accent)

    # ── SHIFT LIGHTS — wide blocks across the top ──
    lights_panel = glass_panel(W - 50, 60, edge=edge_c, r=8, opacity=0.15)
    img.paste(lights_panel, (25, 22), lights_panel)

    total_lights = 12
    lit = int(rpm_frac * total_lights)
    light_w = (W - 100) // total_lights - 5
    light_h = 32

    for i in range(total_lights):
        lx = 45 + i * ((W - 90) // total_lights)
        ly = 36

        lf = i / (total_lights - 1)
        c = ramp(p['light_ramp'], lf)

        if i < lit:
            # glow behind
            img = glow(img, lx + light_w // 2, ly + light_h // 2, 28, c, 35)
            draw = ImageDraw.Draw(img)
            # lit block
            draw.rounded_rectangle((lx, ly, lx + light_w, ly + light_h),
                                   radius=5, fill=c + (235,))
            # top highlight
            draw.line((lx + 4, ly + 1, lx + light_w - 4, ly + 1),
                      fill=(255, 255, 255, 70), width=1)
        else:
            draw = ImageDraw.Draw(img)
            is_red = lf >= 0.85
            dark = (32, 15, 18, 150) if is_red else (15, 18, 28, 140)
            draw.rounded_rectangle((lx, ly, lx + light_w, ly + light_h),
                                   radius=5, fill=dark)

    # ── MAIN TACH BAR — hero element, tall and wide ──
    tach_y = 220
    tach_h = 80
    tach_x = 50
    tach_w = W - 110

    tach_panel = glass_panel(tach_w + 20, tach_h + 80, edge=edge_c, r=12, opacity=0.18)
    img.paste(tach_panel, (tach_x - 10, tach_y - 10), tach_panel)

    # segmented tach
    segments = 20
    gap = 4
    slant = 16
    seg_w = (tach_w - (segments - 1) * gap) / segments
    filled = int(rpm_frac * segments)

    for s in range(segments):
        sx = tach_x + s * (seg_w + gap)
        f = s / max(1, segments - 1)
        lit = s < filled

        for row in range(tach_h):
            row_f = row / max(1, tach_h - 1)
            lx = sx + slant * (1 - row_f)
            rx = lx + seg_w

            if lit:
                c = ramp(p['hot'], f)
                bright = 1.2 - 0.35 * row_f
                fill_c = tuple(min(255, int(v * bright)) for v in c) + (235,)
            else:
                is_red = f >= 0.875
                base = (38, 16, 20) if is_red else (14, 18, 28)
                fill_c = base + (160,)

            draw = ImageDraw.Draw(img)
            draw.line((int(lx), tach_y + row, int(rx), tach_y + row), fill=fill_c)

    # glow at fill edge
    if filled > 0 and filled < segments:
        glow_x = tach_x + filled * (seg_w + gap) + slant // 2
        tip_c = ramp(p['hot'], filled / segments)
        img = glow(img, int(glow_x), tach_y + tach_h // 2, 30, tip_c, 55)

    # position needle — bright vertical line at current RPM
    needle_x = tach_x + rpm_frac * tach_w
    draw = ImageDraw.Draw(img)
    draw.line((int(needle_x + slant * 0.4), tach_y - 4,
               int(needle_x - slant * 0.1), tach_y + tach_h + 4),
              fill=(255, 255, 255, 220), width=4)

    # shift marker
    shift_frac = shift_at / redline
    shift_x = tach_x + shift_frac * tach_w
    draw.line((int(shift_x + slant * 0.4), tach_y - 6,
               int(shift_x - slant * 0.1), tach_y + tach_h + 6),
              fill=(255, 200, 50, 160), width=3)

    # scale below tach
    for i in range(9):
        tick_x = tach_x + int(tach_w * i / 8)
        val = str(i)
        is_red = i >= 7
        color = (240, 55, 40, 220) if is_red else (110, 120, 145, 180)
        tick_h = 10 if i % 2 == 0 else 6
        draw.line((tick_x, tach_y + tach_h + 8, tick_x, tach_y + tach_h + 8 + tick_h),
                  fill=color, width=2 if i % 2 == 0 else 1)
        if i % 2 == 0 or i == 7:
            tf = font(18)
            tbox = draw.textbbox((0, 0), val, font=tf)
            tw = tbox[2] - tbox[0]
            draw.text((tick_x - tw // 2, tach_y + tach_h + 22), val, fill=color, font=tf)

    # ── GEAR — massive, overlapping above the tach ──
    gear_str = str(gear) if gear > 0 else 'N'

    # glow behind gear
    img = glow(img, W // 2, 160, 80, accent, 15)
    draw = ImageDraw.Draw(img)

    gf = font(160)
    gbox = draw.textbbox((0, 0), gear_str, font=gf)
    gw = gbox[2] - gbox[0]
    gh = gbox[3] - gbox[1]
    gear_x = W // 2 - gw // 2
    gear_y = 90
    draw.text((gear_x, gear_y), gear_str, fill=accent, font=gf)

    # ── SPEED — left side ──
    speed_str = str(speed)
    draw.text((55, 100), "SPEED", fill=p['label'], font=font(15))
    draw.text((55, 120), speed_str, fill=(255, 255, 255), font=font(80))
    draw.text((55, 205), "MPH", fill=p['dim'], font=font(16))

    # ── SHIFT AT — right side ──
    draw.text((W - 255, 100), "SHIFT AT", fill=p['label'], font=font(15))
    stf = font(70)
    st_str = str(shift_at)
    stbox = draw.textbbox((0, 0), st_str, font=stf)
    stw = stbox[2] - stbox[0]
    draw.text((W - 75 - stw, 118), st_str, fill=accent, font=stf)

    # RPM readout
    draw.text((W - 160, 195), str(rpm), fill=(200, 210, 225), font=font(22))
    draw.text((W - 100, 198), "RPM", fill=p['dim'], font=font(13))

    # ── BOTTOM INFO BAR ──
    info_panel = glass_panel(W - 50, 48, edge=edge_c, r=8, opacity=0.12)
    img.paste(info_panel, (25, H - 65), info_panel)
    draw = ImageDraw.Draw(img)

    draw.text((50, H - 55), f"PEAK  {rpm + 1380}", fill=p['dim'], font=font(14))
    draw.text((250, H - 55), "LIMITER  0×", fill=p['dim'], font=font(14))

    # last shift badge
    draw.text((550, H - 55), "LAST  3 > 4  @  6480", fill=p['dim'], font=font(14))
    draw.rounded_rectangle((770, H - 58, 855, H - 38), radius=4, fill=(40, 200, 100, 180))
    draw.text((778, H - 56), "SPOT ON", fill=(255, 255, 255), font=font(13))

    # reset + next page labels
    draw.text((W - 230, H - 55), "RESET MAX", fill=(80, 90, 110), font=font(12))

    # ── TITLE ──
    draw.text((30, 4), "ShiftDeck", fill=p['label'], font=font(18))
    draw.text((W - 82, 6), "2:50 pm", fill=(55, 62, 75), font=font(14))

    # ambient strip
    for x in range(35, W - 35):
        f = (x - 35) / (W - 70)
        center = 1 - (2 * abs(f - 0.5)) ** 1.5
        a = int(20 * center)
        if a > 0:
            draw.line((x, H - 2, x, H), fill=accent + (a,))

    return img


def main():
    out = ROOT / 'plugin'
    ambients = {
        'shiftdeck_v2_orange':  (255, 140, 30),
        'shiftdeck_v2_ice':     (80, 180, 255),
        'shiftdeck_v2_red':     (225, 40, 50),
        'shiftdeck_v2_cyan':    (40, 215, 205),
        'shiftdeck_v2_purple':  (155, 75, 215),
    }
    for name, color in ambients.items():
        img = render(color)
        path = out / f'{name}.png'
        img.save(path, format='PNG', optimize=True)
        print(f'{name}: {path}')


if __name__ == '__main__':
    main()
