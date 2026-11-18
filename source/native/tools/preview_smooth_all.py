"""Generate smooth 256-step animations for BoostDeck arcs and HUD Wings."""
from math import sin, cos, radians, pi
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
STEPS = 256


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


def draw_arc_frame(img, cx, cy, r_out, r_in, fill_frac, color, hot, start=150, sweep=240):
    scale = 2
    buf = Image.new('RGBA', (img.width * scale, img.height * scale), (0, 0, 0, 0))
    bd = ImageDraw.Draw(buf)
    scx, scy = cx * scale, cy * scale
    sr_out, sr_in = r_out * scale, r_in * scale
    thickness = sr_out - sr_in
    mid_r = (sr_out + sr_in) // 2
    bbox = (scx - mid_r, scy - mid_r, scx + mid_r, scy + mid_r)

    bd.arc(bbox, start, start + sweep, fill=(255, 255, 255, 18), width=thickness)

    if fill_frac > 0.003:
        fill_end = start + sweep * fill_frac
        segs = max(2, int(fill_frac * 120))
        bloom_buf = Image.new('RGBA', buf.size, (0, 0, 0, 0))
        bloom_d = ImageDraw.Draw(bloom_buf)
        for s in range(segs):
            a0 = start + (fill_end - start) * s / segs
            a1 = start + (fill_end - start) * (s + 1) / segs + 0.3
            f = (s / max(1, segs - 1)) * fill_frac
            c = ramp([(30, 30, 30), color, color, hot], f)
            bd.arc(bbox, a0, a1, fill=c + (245,), width=thickness)
            bloom_d.arc(bbox, a0, a1, fill=c + (45,), width=thickness + scale * 18)
        bloom_buf = bloom_buf.filter(ImageFilter.GaussianBlur(scale * 5))
        buf = Image.alpha_composite(buf, bloom_buf)

    small = buf.resize((img.width, img.height), Image.LANCZOS)
    img = Image.alpha_composite(img, small)

    if fill_frac > 0.01:
        tip_rad = radians(start + sweep * fill_frac)
        tip_r = (r_in + r_out) / 2
        tx = int(cx + cos(tip_rad) * tip_r)
        ty = int(cy + sin(tip_rad) * tip_r)
        tip_c = ramp([color, color, hot], fill_frac)
        img = bloom(img, tx, ty, 20, tip_c, 70)

    return img


def draw_swept_bar_frame(draw, img, x, y, w, h, segs, filled_frac, colors, slant=16, direction='right'):
    gap = 4
    seg_w = (w - (segs - 1) * gap) / segs
    filled = filled_frac * segs

    for s in range(segs):
        if direction == 'right':
            sx = x + s * (seg_w + gap)
        else:
            sx = x + w - (s + 1) * (seg_w + gap) + gap
        f = s / max(1, segs - 1)
        lit = s < filled

        for row in range(h):
            row_f = row / max(1, h - 1)
            sign = 1 if direction == 'right' else -1
            offset = sign * slant * (1 - row_f)
            lx = sx + offset
            rx = lx + seg_w

            if lit:
                c = ramp(colors, f)
                bright = 1.15 - 0.3 * row_f
                fill_c = tuple(min(255, int(v * bright)) for v in c) + (230,)
            else:
                fill_c = (255, 255, 255, 8)

            draw.line((int(lx), y + row, int(rx), y + row), fill=fill_c)

    if 0 < filled < segs:
        if direction == 'right':
            glow_x = x + filled * (seg_w + gap) + slant // 2
        else:
            glow_x = x + w - filled * (seg_w + gap) - slant // 2
        tip_c = ramp(colors, filled / segs)
        img = bloom(img, int(glow_x), y + h // 2, 18, tip_c, 55)
    return img


# ──────────────────────────────────────────────
# BOOSTDECK ARC ANIMATION
# ──────────────────────────────────────────────
def boostdeck_anim(accent, out_path):
    hot = (min(255, accent[0] + 70), max(25, accent[1] - 25), max(15, accent[2] - 35))
    W, H = 400, 300
    frames = []
    total_anim_frames = 120

    for frame_i in range(total_anim_frames):
        t = frame_i / total_anim_frames
        fill = (sin(t * 2 * pi - pi / 2) + 1) / 2

        img = Image.new('RGBA', (W, H), (5, 6, 10, 255))
        cx, cy = W // 2, 155

        img = draw_arc_frame(img, cx, cy, 120, 106, fill, accent, hot)

        draw = ImageDraw.Draw(img)
        step = round(fill * STEPS)
        psi = fill * 30
        val_str = f"{psi:.1f}"
        vf = font(44)
        vbox = draw.textbbox((0, 0), val_str, font=vf)
        vw = vbox[2] - vbox[0]
        draw.text((cx - vw // 2, cy - 24), val_str, fill=(255, 255, 255, 245), font=vf)
        draw.text((cx - 10, cy + 22), "PSI", fill=accent[:3] + (140,), font=font(14))

        draw.text((10, 8), f"BOOSTDECK  256-STEP", fill=accent[:3] + (120,), font=font(13))
        draw.text((10, 25), f"Step {step}/{STEPS}  ({fill*100:.1f}%)", fill=(160, 170, 185), font=font(11))

        rgb = Image.new('RGB', (W, H), (5, 6, 10))
        rgb.paste(img, mask=img.split()[3])
        frames.append(rgb)

    frames[0].save(out_path, save_all=True, append_images=frames[1:],
                   duration=33, loop=0, optimize=False)
    print(f'BoostDeck arc anim: {out_path}')


# ──────────────────────────────────────────────
# HUD WINGS ANIMATION
# ──────────────────────────────────────────────
def hud_wings_anim(accent, out_path):
    hot = (min(255, accent[0] + 70), max(25, accent[1] - 25), max(15, accent[2] - 35))
    W, H = 800, 300
    frames = []
    total_anim_frames = 120
    colors = [(30, 30, 40), accent, accent, hot, (255, 50, 40)]

    cx = W // 2
    wing_w = 260
    wing_h = 50
    wing_y = 70
    wing_gap = 75

    for frame_i in range(total_anim_frames):
        t = frame_i / total_anim_frames
        fill = (sin(t * 2 * pi - pi / 2) + 1) / 2

        img = Image.new('RGBA', (W, H), (5, 6, 10, 255))
        draw = ImageDraw.Draw(img)

        # left wing
        img = draw_swept_bar_frame(draw, img, cx - wing_gap - wing_w, wing_y, wing_w, wing_h,
                                   10, fill, colors, slant=14, direction='left')
        draw = ImageDraw.Draw(img)
        # right wing
        img = draw_swept_bar_frame(draw, img, cx + wing_gap, wing_y, wing_w, wing_h,
                                   10, fill, colors, slant=14, direction='right')

        # gear
        draw = ImageDraw.Draw(img)
        gear_cy = wing_y + wing_h // 2
        rpm = int(fill * 8000)
        gear = min(8, max(1, int(fill * 7) + 1))
        gf = font(90)
        gear_str = str(gear)
        gbox = draw.textbbox((0, 0), gear_str, font=gf)
        gw = gbox[2] - gbox[0]
        gh = gbox[3] - gbox[1]
        draw.text((cx - gw // 2, gear_cy - gh // 2 - 8), gear_str,
                  fill=(255, 255, 255, 250), font=gf)

        # shift lights
        total_lights = 8
        lit = max(0, int((fill - 0.55) / 0.45 * total_lights)) if fill > 0.55 else 0
        light_w = 60
        light_h = 16
        light_y = wing_y - 38
        start_lx = cx - (total_lights * (light_w + 5)) // 2
        for i in range(total_lights):
            lx = start_lx + i * (light_w + 5)
            lf = i / (total_lights - 1)
            c = ramp([accent, accent, hot, (255, 50, 40)], lf)
            if i < lit:
                img = bloom(img, lx + light_w // 2, light_y + light_h // 2, 18, c, 40)
                draw = ImageDraw.Draw(img)
                pts = [(lx + 5, light_y), (lx + light_w + 5, light_y),
                       (lx + light_w, light_y + light_h), (lx, light_y + light_h)]
                draw.polygon(pts, fill=c + (240,))
            else:
                draw = ImageDraw.Draw(img)
                pts = [(lx + 5, light_y), (lx + light_w + 5, light_y),
                       (lx + light_w, light_y + light_h), (lx, light_y + light_h)]
                draw.polygon(pts, fill=(255, 255, 255, 8))

        draw = ImageDraw.Draw(img)
        step = round(fill * STEPS)
        draw.text((10, 8), f"HUD WINGS  256-STEP", fill=accent[:3] + (120,), font=font(13))
        draw.text((10, 25), f"Step {step}/{STEPS}  RPM {rpm}", fill=(160, 170, 185), font=font(11))

        # speed
        spd = int(fill * 155)
        draw.text((30, H - 70), str(spd), fill=(255, 255, 255, 230), font=font(42))
        draw.text((30, H - 26), "MPH", fill=(255, 255, 255, 70), font=font(12))

        rgb = Image.new('RGB', (W, H), (5, 6, 10))
        rgb.paste(img, mask=img.split()[3])
        frames.append(rgb)

    frames[0].save(out_path, save_all=True, append_images=frames[1:],
                   duration=33, loop=0, optimize=False)
    print(f'HUD wings anim: {out_path}')


def main():
    out = ROOT / 'plugin'
    boostdeck_anim((155, 75, 215), out / 'smooth_boostdeck_256.gif')
    hud_wings_anim((155, 75, 215), out / 'smooth_hud_wings_256.gif')
    boostdeck_anim((255, 140, 30), out / 'smooth_boostdeck_256_orange.gif')
    hud_wings_anim((255, 140, 30), out / 'smooth_hud_wings_256_orange.gif')


if __name__ == '__main__':
    main()
