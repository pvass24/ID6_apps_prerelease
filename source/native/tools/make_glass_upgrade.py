#!/usr/bin/env python3
"""Generate all glass-aesthetic assets for iDrive 6 BoostDeck, ShiftDeck, EngineCodes.

Usage:
    python3 make_glass_upgrade.py                 # generate all
    python3 make_glass_upgrade.py --app boostdeck # one app
    python3 make_glass_upgrade.py --preview       # preview mockups only
"""
import argparse
import sys
from io import BytesIO
from math import cos, radians, sin
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_DIR = ROOT / "plugin"

# ───────────────────── constants ──────────────────────
SCREEN_W, SCREEN_H = 1280, 480
BD_FIRST = 60000
BD_STEPS = 256
BD_MULTICOLOR = 8
ETHANOL_FIRST = 56100
ETHANOL_STEPS = 20
BD_BG_ID = 56300
SD_SWEEP_BASE = 56400
SD_SWEEP_ALERT = 56529
SD_SWEEP_STEPS = 128
SD_LIGHT_BASE = 55866
SD_DIGIT_BASE = 55890
SD_DIGIT_WARN = 55902
SD_TARGET_BASE = 55880
SD_MARK_BASE = 55920
SD_SHIFT_OFF = 55914
SD_SHIFT_ON = 55915
SD_SPEED_LEGEND = 55916
SD_RPM_LEGEND = 55917
SD_SCALE = 55918
SD_LOWER = 55919
SD_METRIC_LEGEND = 56660
EC_BG_ID = 56700

ARC_SIZE = 260
ARC_CX, ARC_CY = ARC_SIZE // 2, ARC_SIZE // 2
ARC_R_OUT, ARC_R_IN = 110, 95
ARC_START, ARC_SWEEP = 150, 240

SOLID_RAMPS = [
    [(60, 25, 5), (180, 70, 15), (255, 80, 26), (255, 160, 60)],
    [(15, 50, 100), (40, 120, 200), (88, 206, 255), (180, 230, 255)],
    [(15, 60, 30), (40, 150, 80), (108, 219, 147), (180, 240, 200)],
    [(50, 55, 65), (140, 150, 160), (200, 210, 220), (226, 234, 240)],
    [(50, 20, 80), (120, 60, 180), (173, 114, 255), (210, 170, 255)],
    [(80, 20, 50), (180, 50, 120), (255, 108, 186), (255, 170, 215)],
    [(10, 60, 60), (20, 170, 160), (32, 241, 230), (150, 250, 245)],
    [(80, 15, 15), (180, 30, 30), (255, 69, 69), (255, 140, 140)],
]
MULTICOLOR_ACCENTS = [
    (88, 206, 255), (93, 224, 191), (203, 172, 255), (255, 190, 112),
    (108, 219, 147), (96, 197, 255), (255, 183, 106), (111, 217, 186),
]
COLOR_NAMES = [
    "BMW Orange", "Blue", "Green", "White", "Purple", "Pink", "Cyan", "Red", "Multicolor",
]


def _hex_to_rgb(h):
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _accent_ramp(accent):
    return [
        tuple(max(5, int(c * 0.15)) for c in accent),
        tuple(max(10, int(c * 0.5)) for c in accent),
        accent,
        tuple(min(255, int(c * 1.2 + 50)) for c in accent),
    ]


# ───────────────── rendering primitives ───────────────

def ramp(colors, f):
    f = max(0.0, min(1.0, f))
    n = len(colors) - 1
    i = min(n - 1, int(f * n))
    t = f * n - i
    return tuple(int(colors[i][j] + (colors[i + 1][j] - colors[i][j]) * t) for j in range(3))


def _font(size):
    for p in [
        "/System/Library/Fonts/Supplemental/DIN Condensed Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf",
    ]:
        try:
            return ImageFont.truetype(p, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


def _glow(img, cx, cy, radius, color, alpha=30):
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    steps = max(4, radius // 2)
    for i in range(steps):
        r = radius * (1 - i / steps)
        a = int(alpha * (i / steps) ** 0.4 * ((steps - i) / steps) ** 0.6)
        if a > 0 and r > 0:
            d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=color[:3] + (a,))
    return Image.alpha_composite(img, layer.filter(ImageFilter.GaussianBlur(max(2, radius // 4))))


def _glass_panel(w, h, base=(12, 14, 20), edge=(50, 60, 80), r=14, opacity=0.30):
    panel = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(panel)
    for y in range(h):
        yf = y / h
        fade = 1.0 - 0.25 * yf
        a = int(255 * opacity * fade)
        c = tuple(int(v * fade) for v in base)
        d.line((0, y, w, y), fill=c + (a,))
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, w - 1, h - 1), radius=r, fill=255)
    panel.putalpha(mask)
    d = ImageDraw.Draw(panel)
    d.rounded_rectangle((0, 0, w - 1, h - 1), radius=r, outline=edge + (40,), width=1)
    d.line((r + 4, 1, w - r - 4, 1), fill=(255, 255, 255, 28), width=1)
    d.line((r + 8, 2, w - r - 8, 2), fill=(255, 255, 255, 12), width=1)
    d.line((r + 12, h - 2, w - r - 12, h - 2), fill=(255, 255, 255, 6), width=1)
    return panel


# ─────────────────── arc rendering ────────────────────

def _render_arc_fill(size, r_out, r_in, fill_frac, colors, start=ARC_START, sweep=ARC_SWEEP):
    """Render one arc fill frame at 3x then downscale. Returns RGBA image."""
    S = 3
    cx, cy = size // 2, size // 2
    buf = Image.new("RGBA", (size * S, size * S), (0, 0, 0, 0))

    if fill_frac <= 0:
        # empty: draw faint track
        bd = ImageDraw.Draw(buf)
        scx, scy = cx * S, cy * S
        t = (r_out - r_in) * S
        mr = ((r_out + r_in) // 2) * S
        bb = (scx - mr, scy - mr, scx + mr, scy + mr)
        bd.arc(bb, start, start + sweep, fill=(255, 255, 255, 12), width=t)
        return buf.resize((size, size), Image.LANCZOS)

    bd = ImageDraw.Draw(buf)
    scx, scy = cx * S, cy * S
    t = (r_out - r_in) * S
    mr = ((r_out + r_in) // 2) * S
    bb = (scx - mr, scy - mr, scx + mr, scy + mr)

    # faint track behind everything
    bd.arc(bb, start, start + sweep, fill=(255, 255, 255, 12), width=t)

    fill_end = start + sweep * fill_frac
    seg_count = max(3, int(fill_frac * 120))

    # main fill
    for s in range(seg_count):
        a0 = start + (fill_end - start) * s / seg_count
        a1 = start + (fill_end - start) * (s + 1) / seg_count + 0.3
        f = (s / max(1, seg_count - 1)) * fill_frac
        c = ramp(colors, f)
        bd.arc(bb, a0, a1, fill=c + (245,), width=t)

    # bloom
    bloom = Image.new("RGBA", (size * S, size * S), (0, 0, 0, 0))
    bld = ImageDraw.Draw(bloom)
    bt = t + S * 14
    for s in range(max(2, seg_count // 4)):
        a0 = start + (fill_end - start) * s / max(1, seg_count // 4)
        a1 = start + (fill_end - start) * (s + 1) / max(1, seg_count // 4) + 0.5
        f = (s / max(1, seg_count // 4 - 1)) * fill_frac
        c = ramp(colors, f)
        bld.arc(bb, a0, a1, fill=c + (45,), width=bt)
    bloom = bloom.filter(ImageFilter.GaussianBlur(S * 5))
    buf = Image.alpha_composite(buf, bloom)

    img = buf.resize((size, size), Image.LANCZOS)

    # glow dot at tip
    tip_rad = radians(fill_end)
    tip_r = (r_in + r_out) / 2
    tx = int(cx + cos(tip_rad) * tip_r)
    ty = int(cy + sin(tip_rad) * tip_r)
    tip_c = ramp(colors, fill_frac)
    img = _glow(img, tx, ty, 18, tip_c, 60)

    return img


# ──────────────── BoostDeck background ────────────────

# Layout positions matching the XML
BD_TOP_GAUGES = [
    {"name": "AFR", "cx": 140, "cy": 165, "size": ARC_SIZE},
    {"name": "BOOST", "cx": SCREEN_W // 2 - 50, "cy": 145, "size": ARC_SIZE},
    {"name": "TIMING", "cx": 870, "cy": 165, "size": ARC_SIZE},
]
BD_BOT_GAUGES = [
    {"name": "INTAKE", "cx": 100},
    {"name": "TRANS", "cx": 310},
    {"name": "RAIL", "cx": 520},
    {"name": "OIL", "cx": 730},
    {"name": "COOLANT", "cx": 940},
]


def _render_boostdeck_bg():
    """1172 × 400 background with glass panels, arc tracks, labels."""
    W, H = 1172, 400
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # dark base
    for y in range(H):
        yf = y / H
        v = max(0, 0.5 - abs(yf - 0.4)) * 2
        draw.line((0, y, W, y), fill=(int(4 + 8 * v), int(6 + 10 * v), int(12 + 18 * v), 255))

    # ambient glow center
    img = _glow(img, W // 2 - 50, 145, 250, (60, 80, 120), 8)

    # top three glass panels + arc tracks
    for g in BD_TOP_GAUGES:
        x0 = g["cx"] - g["size"] // 2 - 15
        y0 = 10
        pw = g["size"] + 30
        ph = 270
        panel = _glass_panel(pw, ph, r=16, opacity=0.22)
        img.paste(panel, (x0, y0), panel)

        # dim arc track baked into background
        S = 2
        buf = Image.new("RGBA", (ARC_SIZE * S, ARC_SIZE * S), (0, 0, 0, 0))
        bd = ImageDraw.Draw(buf)
        t = (ARC_R_OUT - ARC_R_IN) * S
        mr = ((ARC_R_OUT + ARC_R_IN) // 2) * S
        scx, scy = ARC_SIZE * S // 2, ARC_SIZE * S // 2
        bb = (scx - mr, scy - mr, scx + mr, scy + mr)
        bd.arc(bb, ARC_START, ARC_START + ARC_SWEEP, fill=(35, 45, 60, 40), width=t)
        # tick marks
        for i in range(9):
            tf = i / 8
            angle = ARC_START + ARC_SWEEP * tf
            rad = radians(angle)
            major = i % 2 == 0
            ro = (ARC_R_OUT + 4) * S
            ri = (ARC_R_IN - (6 if major else 3)) * S
            x1 = int(scx + cos(rad) * ro)
            y1 = int(scy + sin(rad) * ro)
            x2 = int(scx + cos(rad) * ri)
            y2 = int(scy + sin(rad) * ri)
            bd.line((x1, y1, x2, y2), fill=(80, 95, 120, 60 if major else 30), width=S * (2 if major else 1))
        track_img = buf.resize((ARC_SIZE, ARC_SIZE), Image.LANCZOS)
        img.paste(track_img, (g["cx"] - ARC_SIZE // 2, g["cy"] - ARC_SIZE // 2), track_img)

        # label below arc
        draw = ImageDraw.Draw(img)
        lf = _font(16)
        lb = draw.textbbox((0, 0), g["name"], font=lf)
        lw = lb[2] - lb[0]
        draw.text((g["cx"] - lw // 2, g["cy"] + ARC_R_OUT + 15), g["name"],
                  fill=(100, 120, 150), font=lf)

    # bottom strip glass panel
    strip_y = 290
    strip = _glass_panel(W - 30, 100, r=10, opacity=0.18)
    img.paste(strip, (15, strip_y), strip)

    # bottom gauge arc tracks + labels
    for g in BD_BOT_GAUGES:
        compact = 130
        r_out, r_in = 52, 44
        S2 = 2
        buf = Image.new("RGBA", (compact * S2, compact * S2), (0, 0, 0, 0))
        bd = ImageDraw.Draw(buf)
        t2 = (r_out - r_in) * S2
        mr2 = ((r_out + r_in) // 2) * S2
        scx2, scy2 = compact * S2 // 2, compact * S2 // 2
        bb2 = (scx2 - mr2, scy2 - mr2, scx2 + mr2, scy2 + mr2)
        bd.arc(bb2, ARC_START, ARC_START + ARC_SWEEP, fill=(30, 40, 55, 35), width=t2)
        track2 = buf.resize((compact, compact), Image.LANCZOS)
        ix = g["cx"] - compact // 2
        iy = strip_y - 5
        img.paste(track2, (ix, iy), track2)

        draw = ImageDraw.Draw(img)
        sf = _font(11)
        sb = draw.textbbox((0, 0), g["name"], font=sf)
        sw = sb[2] - sb[0]
        draw.text((g["cx"] - sw // 2, strip_y + 82), g["name"],
                  fill=(80, 100, 130), font=sf)

    return img


# ─────────────── ethanol vertical bar ─────────────────

def _render_ethanol(step, total, color_ramp):
    """40 × 250 vertical glass bar fill."""
    W, H = 40, 250
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    r = 4
    # track
    d.rounded_rectangle((2, 2, W - 3, H - 3), radius=r, fill=(20, 28, 40, 120))
    d.rounded_rectangle((2, 2, W - 3, H - 3), radius=r, outline=(40, 55, 75, 40))
    if step <= 0:
        return img
    f = step / total
    fill_h = max(r * 2, int((H - 6) * f))
    fill_top = H - 3 - fill_h
    c = ramp(color_ramp, f)
    d.rounded_rectangle((3, fill_top, W - 4, H - 4), radius=r,
                        fill=c + (200,))
    # glow at top of fill
    glow_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow_layer)
    gd.ellipse((W // 2 - 10, fill_top - 6, W // 2 + 10, fill_top + 6), fill=c + (60,))
    glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(4))
    img = Image.alpha_composite(img, glow_layer)
    return img


# ────────────── ShiftDeck swept segments ──────────────

def _render_swept_tach(step, total, w, h, colors, slant=16, alert=False):
    """1104 × 90 glass segmented tach bar at the given fill step."""
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    segments = 20
    gap = 4
    seg_w = (w - (segments - 1) * gap) / segments
    filled = step * segments / total if total > 0 else 0

    for s in range(segments):
        sx = s * (seg_w + gap)
        f = s / max(1, segments - 1)
        lit = s < filled
        for row in range(h):
            row_f = row / max(1, h - 1)
            lx = sx + slant * (1 - row_f)
            rx = lx + seg_w
            if lit:
                c = ramp(colors, f)
                bright = 1.15 - 0.3 * row_f
                fc = tuple(min(255, int(v * bright)) for v in c) + (230,)
            else:
                is_red = f >= 0.875
                fc = (35, 16, 20, 150) if is_red else (14, 18, 28, 140)
            draw.line((int(lx), row, int(rx), row), fill=fc)

    if 0 < filled < segments:
        gx = int(filled * (seg_w + gap) + slant // 2)
        tip_c = ramp(colors, filled / segments)
        img = _glow(img, gx, h // 2, 20, tip_c, 50)
    return img


def _render_shift_lights(state, w=1104, h=60, total=12):
    """One of 14 shift-light states (0 = none lit, 13 = all red flash)."""
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    block_w = (w - 20) // total - 5
    block_h = h - 20

    green = (40, 210, 110)
    yellow = (230, 200, 40)
    red = (240, 55, 40)

    for i in range(total):
        bx = 10 + i * ((w - 20) // total)
        by = 10
        lf = i / (total - 1)
        if lf < 0.42:
            c = green
        elif lf < 0.75:
            c = yellow
        else:
            c = red

        if state == 13:
            c = red
            lit = True
        else:
            lit = i < state

        slant = 5
        if lit:
            img = _glow(img, bx + block_w // 2, by + block_h // 2, 22, c, 40)
            draw = ImageDraw.Draw(img)
            pts = [(bx + slant, by), (bx + block_w + slant, by),
                   (bx + block_w, by + block_h), (bx, by + block_h)]
            draw.polygon(pts, fill=c + (235,))
            draw.line((bx + slant + 3, by + 1, bx + block_w + slant - 3, by + 1),
                      fill=(255, 255, 255, 55), width=1)
        else:
            is_red = lf >= 0.85
            dark = (30, 14, 18, 130) if is_red else (14, 18, 28, 120)
            pts = [(bx + slant, by), (bx + block_w + slant, by),
                   (bx + block_w, by + block_h), (bx, by + block_h)]
            draw.polygon(pts, fill=dark)
    return img


def _render_digit(char, color, w=58, h=92):
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    f = _font(86)
    d.text((w // 2, 4), char, fill=color, font=f, anchor="mt")
    return img


def _render_target_card(rpm, w=164, h=135):
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    panel = _glass_panel(w, h, r=10, opacity=0.2, edge=(50, 70, 100))
    img = Image.alpha_composite(img, panel)
    d = ImageDraw.Draw(img)
    d.text((w - 8, 8), "SHIFT AT", fill=(100, 120, 150), font=_font(20), anchor="rt")
    d.text((w - 8, 35), str(rpm), fill=(80, 180, 255), font=_font(58), anchor="rt")
    d.text((w - 8, 95), "RPM", fill=(80, 100, 130), font=_font(18), anchor="rt")
    return img


def _render_mark(rpm, redline=8000, w=1104, h=9):
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    x = int(w * rpm / redline)
    d.line((x, 1, x, h - 2), fill=(255, 200, 50, 180), width=3)
    return img


def _render_scale(w=1104, h=49):
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for i in range(17):
        x = 4 + int(i * (w - 28) / 16)
        is_red = i >= 14
        c = (240, 55, 40, 200) if is_red else (160, 170, 190, 140) if i % 2 == 0 else (100, 110, 130, 80)
        tick_h = 14 if i % 2 == 0 else 8
        d.line((x, 2, x, 2 + tick_h), fill=c, width=2 if i % 2 == 0 else 1)
        if i % 2 == 0:
            d.text((max(8, x), 20), str(i // 2), fill=c, font=_font(20))
    return img


def _render_speed_legend(metric=False, w=200, h=160):
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.text((4, 4), "SPEED", fill=(100, 120, 150), font=_font(22))
    d.text((4, 120), "km/h" if metric else "MPH", fill=(80, 100, 130), font=_font(18))
    d.line((4, 155, 140, 155), fill=(50, 65, 85, 100), width=2)
    return img


def _render_rpm_legend(w=68, h=33):
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(img).text((2, 3), "RPM", fill=(100, 120, 150), font=_font(22))
    return img


def _render_lower_line(w=1104, h=10):
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.line([(0, 6), (180, 6), (220, 2), (884, 2), (924, 6), (w, 6)],
           fill=(50, 65, 85, 100), width=2)
    return img


def _render_shift_indicator(on, w=290, h=42):
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    if on:
        d = ImageDraw.Draw(img)
        d.rounded_rectangle((2, 2, w - 3, h - 3), radius=8, fill=(60, 16, 24, 200),
                            outline=(240, 55, 40, 200), width=2)
        d.text((w // 2, h // 2), "S H I F T", fill=(240, 55, 40),
               font=_font(28), anchor="mm")
    return img


# ────────────────── EngineCodes BG ────────────────────

def _render_enginecodes_bg(w=1120, h=352):
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    for y in range(h):
        yf = y / h
        v = max(0, 0.5 - abs(yf - 0.4)) * 2
        draw.line((0, y, w, y), fill=(int(4 + 6 * v), int(6 + 8 * v), int(12 + 14 * v), 255))

    # left panel with ring area
    panel_l = _glass_panel(290, h - 20, r=14, opacity=0.22)
    img.paste(panel_l, (10, 10), panel_l)

    # ring track
    S = 2
    ring_size = 220
    buf = Image.new("RGBA", (ring_size * S, ring_size * S), (0, 0, 0, 0))
    bd = ImageDraw.Draw(buf)
    ro, ri = 90, 76
    t2 = (ro - ri) * S
    mr2 = ((ro + ri) // 2) * S
    sc2 = ring_size * S // 2
    bb2 = (sc2 - mr2, sc2 - mr2, sc2 + mr2, sc2 + mr2)
    bd.arc(bb2, 150, 390, fill=(35, 45, 60, 40), width=t2)
    track = buf.resize((ring_size, ring_size), Image.LANCZOS)
    img.paste(track, (45, 30), track)

    # 4 code card frames on the right
    card_x = 320
    card_w = w - card_x - 20
    card_h = 72
    for i in range(4):
        cy = 15 + i * (card_h + 10)
        card = _glass_panel(card_w, card_h, r=10, opacity=0.16, edge=(40, 50, 65))
        img.paste(card, (card_x, cy), card)
        # severity stripe placeholder
        draw = ImageDraw.Draw(img)
        draw.line((card_x + 2, cy + 10, card_x + 2, cy + card_h - 10),
                  fill=(60, 70, 90, 100), width=4)

    return img


# ──────────────── XML generation ──────────────────────

def _add_props(comp, x, y, w, h, image=False):
    props = ET.SubElement(comp, "properties")
    for pid, val in [(20, x), (21, y), (9, w), (10, h)]:
        ET.SubElement(props, "property", id=str(pid), value=str(val))
    if image:
        ET.SubElement(props, "property", id="2", value="false")
        ET.SubElement(props, "property", id="3", value="true")


def _gen_boostdeck_xml():
    root = ET.Element("pluginApps")
    root.set("xmlns:xsi", "")
    app = ET.SubElement(root, "pluginApp", applicationType="VehicleInformation",
                        applicationWeight="210", text="BoostDeck")
    entry = ET.SubElement(app, "entryButton", id="1", action="10")
    ET.SubElement(ET.SubElement(entry, "properties"), "property", id="23", value="2")

    actions = ET.SubElement(app, "actions")
    ET.SubElement(actions, "hmiAction", id="10", target="100")
    ET.SubElement(actions, "hmiAction", id="31", target="104")
    for aid in list(range(40, 49)) + [49, 59]:
        ET.SubElement(actions, "raAction", id=str(aid))

    models = ET.SubElement(app, "models")
    for i in range(8):
        ET.SubElement(models, "raDataModel", id=str(50 + i), modelType="Richtext")
        ET.SubElement(models, "imageIdModel", id=str(60 + i), imageId=str(BD_FIRST))
    ET.SubElement(models, "raDataModel", id="110", modelType="Richtext")
    ET.SubElement(models, "raDataModel", id="58", modelType="Richtext")
    ET.SubElement(models, "imageIdModel", id="68", imageId=str(ETHANOL_FIRST))
    ET.SubElement(models, "imageIdModel", id="69", imageId=str(BD_BG_ID))

    states = ET.SubElement(app, "hmiStates")
    main_state = ET.SubElement(states, "hmiState", id="100", text="BoostDeck")
    opts = ET.SubElement(main_state, "optionComponents")
    ET.SubElement(opts, "button", id="33", action="31", text="Gauge color")
    ET.SubElement(opts, "button", id="410", action="49", text="Units: Imperial")
    ET.SubElement(opts, "button", id="411", action="59", text="Units: Metric")

    comps = ET.SubElement(main_state, "components")

    # background first (drawn behind everything)
    bg = ET.SubElement(comps, "image", id="209", model="69")
    _add_props(bg, 24, 13, 1172, 400, image=True)

    # top 3 arc gauge images (models 60-62) + labels (50-52)
    top_layout = [
        (60, 50, 200, 150, 10, 40, ARC_SIZE, ARC_SIZE, 10, 270, ARC_SIZE, 50),
        (61, 51, 201, 151, 350, 20, ARC_SIZE, ARC_SIZE, 350, 250, ARC_SIZE, 50),
        (62, 52, 202, 152, 750, 40, ARC_SIZE, ARC_SIZE, 750, 270, ARC_SIZE, 50),
    ]
    for img_model, lbl_model, img_id, lbl_id, ix, iy, iw, ih, lx, ly, lw, lh in top_layout:
        im = ET.SubElement(comps, "image", id=str(img_id), model=str(img_model))
        _add_props(im, ix, iy, iw, ih, image=True)
        lb = ET.SubElement(comps, "label", id=str(lbl_id), model=str(lbl_model))
        _add_props(lb, lx, ly, lw, lh)

    # bottom 5 compact ring gauges (models 63-67) + labels (53-57)
    compact = 130
    bot_positions = [(80, 290), (290, 290), (500, 290), (710, 290), (920, 290)]
    for i, (bx, by) in enumerate(bot_positions):
        im = ET.SubElement(comps, "image", id=str(203 + i), model=str(63 + i))
        _add_props(im, bx, by, compact, compact, image=True)
        lb = ET.SubElement(comps, "label", id=str(153 + i), model=str(53 + i))
        _add_props(lb, bx - 5, by + compact - 20, compact + 10, 40)

    # ethanol
    eth_img = ET.SubElement(comps, "image", id="208", model="68")
    _add_props(eth_img, 1106, 71, 40, 250, image=True)
    eth_lbl = ET.SubElement(comps, "label", id="158", model="58")
    _add_props(eth_lbl, 1080, 335, 112, 63)

    # color picker state (unchanged)
    color_state = ET.SubElement(states, "hmiState", id="104", parentId="100", text="Gauge color")
    cc = ET.SubElement(color_state, "components")
    ET.SubElement(cc, "label", id="389", model="110")
    for idx, name in enumerate(COLOR_NAMES):
        ET.SubElement(cc, "button", id=str(390 + idx), action=str(40 + idx), text=name)

    ET.indent(root, space="  ")
    return root


def _gen_enginecodes_xml():
    root = ET.Element("pluginApps")
    app = ET.SubElement(root, "pluginApp", applicationType="VehicleInformation",
                        applicationWeight="209", text="Engine Fault Codes")
    entry = ET.SubElement(app, "entryButton", id="1", action="10")
    ET.SubElement(ET.SubElement(entry, "properties"), "property", id="23", value="2")

    actions = ET.SubElement(app, "actions")
    ET.SubElement(actions, "hmiAction", id="10", target="101")
    ET.SubElement(actions, "hmiAction", id="25", target="102")
    ET.SubElement(actions, "raAction", id="23")
    ET.SubElement(actions, "raAction", id="27")
    ET.SubElement(actions, "raAction", id="29")

    models = ET.SubElement(app, "models")
    for mid in [80, 81, 82, 83, 84, 89, 90]:
        ET.SubElement(models, "raDataModel", id=str(mid), modelType="Richtext")
    ET.SubElement(models, "imageIdModel", id="95", imageId=str(EC_BG_ID))
    for mid in [91, 92, 93, 94]:
        ET.SubElement(models, "raDataModel", id=str(mid), modelType="Richtext")

    states = ET.SubElement(app, "hmiStates")
    main = ET.SubElement(states, "hmiState", id="101", text="Engine Fault Codes")
    opts = ET.SubElement(main, "optionComponents")
    ET.SubElement(opts, "button", id="312", action="29", text="Next page")
    ET.SubElement(opts, "button", id="313", action="25", text="Clear engine codes...")

    comps = ET.SubElement(main, "components")
    bg = ET.SubElement(comps, "image", id="328", model="95")
    _add_props(bg, 36, 9, 1120, 352, image=True)

    # header in left panel area
    hdr = ET.SubElement(comps, "label", id="320", model="80")
    _add_props(hdr, 44, 30, 260, 50)

    # code hex labels (right side, 4 rows)
    card_x, card_w = 340, 220
    for i in range(4):
        cy = 25 + i * 82
        lb = ET.SubElement(comps, "label", id=str(321 + i), model=str(81 + i))
        _add_props(lb, card_x, cy, card_w, 55)

    # description labels
    desc_x = card_x + card_w + 10
    desc_w = 1120 - desc_x - 20
    for i in range(4):
        cy = 25 + i * 82
        lb = ET.SubElement(comps, "label", id=str(330 + i), model=str(91 + i))
        _add_props(lb, desc_x, cy, desc_w, 58)

    # read button
    btn = ET.SubElement(comps, "button", id="310", action="23", text="Read engine codes")
    _add_props(btn, 49, 320, 260, 40)

    # clear confirmation
    clear = ET.SubElement(states, "hmiState", id="102", parentId="101", text="Clear engine codes?")
    cc = ET.SubElement(clear, "components")
    ET.SubElement(cc, "button", id="340", action="27", text="Confirm clear engine codes")
    ET.SubElement(cc, "label", id="350", model="89")
    ET.SubElement(cc, "label", id="360", model="90")
    ET.SubElement(cc, "label", id="370", model="80")

    ET.indent(root, space="  ")
    return root


# ──────────────────── ZIP assembly ────────────────────

def _img_bytes(img):
    buf = BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _add_png(archive, img_id, img):
    archive.writestr(ZipInfo(f"{img_id}.png"), _img_bytes(img), ZIP_DEFLATED)


# ─────────────────── main generators ──────────────────

def generate_boostdeck(out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    print("=== BoostDeck ===")

    # XML
    xml_root = _gen_boostdeck_xml()
    xml_path = out_dir / "BoostDeck.xml"
    ET.ElementTree(xml_root).write(xml_path, encoding="utf-8", xml_declaration=True)
    print(f"  XML: {xml_path}")

    # header
    header_path = ROOT / "src" / "dial_scales.h"
    scales = [f'    {{{lo}, {hi}, "{name}", "{unit}"}}'
              for name, unit, lo, hi in [
                  ("Boost", "psi", 0, 35), ("AFR", "", 9, 19), ("Timing", "deg", -20, 50),
                  ("Intake air", r"\260F", -20, 100), ("Transmission", r"\260F", 0, 150),
                  ("Rail pressure", "psi", 0, 250), ("Oil pressure", "psi", 0, 8),
                  ("Coolant", r"\260F", 0, 130),
              ]]
    colors_str = ", ".join(f'"{n}"' for n in COLOR_NAMES)
    header_path.write_text(
        "// Generated by tools/make_glass_upgrade.py.\n"
        f"static const unsigned kDialSteps = {BD_STEPS};\n"
        f"static const unsigned kBarFirst = {BD_FIRST};\n"
        f"static const unsigned kMulticolor = {BD_MULTICOLOR};\n"
        f"static const char *const kColorNames[] = {{{colors_str}}};\n"
        "static const struct DialScale { double minimum, maximum; const char *name, *unit; } kDialScales[] = {\n"
        + ",\n".join(scales) + "\n};\n"
    )
    print(f"  Header: {header_path}")

    # images ZIP
    zip_path = out_dir / "BoostDeck_ALL_Images.zip"
    with ZipFile(zip_path, "w", ZIP_DEFLATED) as z:
        # shared empty (step 0)
        empty = _render_arc_fill(ARC_SIZE, ARC_R_OUT, ARC_R_IN, 0, SOLID_RAMPS[0])
        _add_png(z, BD_FIRST, empty)
        count = 1

        # solid colors (palettes 0-7)
        for ci, color_ramp in enumerate(SOLID_RAMPS):
            for step in range(1, BD_STEPS + 1):
                frac = step / BD_STEPS
                img = _render_arc_fill(ARC_SIZE, ARC_R_OUT, ARC_R_IN, frac, color_ramp)
                _add_png(z, BD_FIRST + ci * BD_STEPS + step, img)
                count += 1
            print(f"  Color {ci} ({COLOR_NAMES[ci]}): {BD_STEPS} frames", flush=True)

        # multicolor per-gauge (palettes 8-15)
        for gi, accent in enumerate(MULTICOLOR_ACCENTS):
            mc_ramp = _accent_ramp(accent)
            for step in range(1, BD_STEPS + 1):
                frac = step / BD_STEPS
                img = _render_arc_fill(ARC_SIZE, ARC_R_OUT, ARC_R_IN, frac, mc_ramp)
                _add_png(z, BD_FIRST + (BD_MULTICOLOR + gi) * BD_STEPS + step, img)
                count += 1
            print(f"  Multicolor gauge {gi}: {BD_STEPS} frames", flush=True)

        # ethanol fills
        for ci in range(9):
            color_ramp = SOLID_RAMPS[ci] if ci < 8 else _accent_ramp(MULTICOLOR_ACCENTS[0])
            for step in range(ETHANOL_STEPS + 1):
                if ci > 0 and step == 0:
                    continue
                img = _render_ethanol(step, ETHANOL_STEPS, color_ramp)
                _add_png(z, ETHANOL_FIRST + ci * ETHANOL_STEPS + step, img)
                count += 1
        print(f"  Ethanol: done")

        # background
        bg = _render_boostdeck_bg()
        _add_png(z, BD_BG_ID, bg)
        count += 1

        print(f"  ZIP: {zip_path} ({count} images)")


def generate_shiftdeck(out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    print("=== ShiftDeck ===")

    # tach ramp: blue → accent → warm → red
    normal_ramp = [(15, 40, 90), (30, 100, 180), (60, 160, 240), (200, 140, 50), (255, 50, 40)]
    alert_ramp = [(80, 15, 15), (180, 30, 30), (240, 50, 40), (255, 60, 40), (255, 80, 60)]
    targets = [5800, 6000, 6250, 6500, 6700]

    zip_path = out_dir / "ShiftDeck_ALL_Images.zip"
    with ZipFile(zip_path, "w", ZIP_DEFLATED) as z:
        # smooth sweep bars
        for step in range(SD_SWEEP_STEPS + 1):
            img = _render_swept_tach(step, SD_SWEEP_STEPS, 1104, 90, normal_ramp)
            _add_png(z, SD_SWEEP_BASE + step, img)
        print(f"  Normal tach: {SD_SWEEP_STEPS + 1} frames")

        for step in range(SD_SWEEP_STEPS + 1):
            img = _render_swept_tach(step, SD_SWEEP_STEPS, 1104, 90, alert_ramp, alert=True)
            _add_png(z, SD_SWEEP_ALERT + step, img)
        print(f"  Alert tach: {SD_SWEEP_STEPS + 1} frames")

        # shift lights (14 states)
        for state in range(14):
            img = _render_shift_lights(state)
            _add_png(z, SD_LIGHT_BASE + state, img)
        print("  Shift lights: 14 states")

        # target cards + marks
        for i, rpm in enumerate(targets):
            _add_png(z, SD_TARGET_BASE + i, _render_target_card(rpm))
            _add_png(z, SD_MARK_BASE + i, _render_mark(rpm))
        print("  Targets + marks: 10")

        # digits (white + red)
        WHITE = (240, 244, 251)
        RED = (255, 69, 72)
        chars = "0123456789- "
        for ci, ch in enumerate(chars):
            _add_png(z, SD_DIGIT_BASE + ci, _render_digit(ch, WHITE))
            _add_png(z, SD_DIGIT_WARN + ci, _render_digit(ch, RED))
        print("  Digits: 24")

        # shift indicators
        _add_png(z, SD_SHIFT_OFF, _render_shift_indicator(False))
        _add_png(z, SD_SHIFT_ON, _render_shift_indicator(True))

        # statics
        _add_png(z, SD_SPEED_LEGEND, _render_speed_legend(metric=False))
        _add_png(z, SD_RPM_LEGEND, _render_rpm_legend())
        _add_png(z, SD_SCALE, _render_scale())
        _add_png(z, SD_LOWER, _render_lower_line())
        _add_png(z, SD_METRIC_LEGEND, _render_speed_legend(metric=True))
        print("  Statics: 7")

    print(f"  ZIP: {zip_path}")


def generate_enginecodes(out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    print("=== EngineCodes ===")

    # XML
    xml_root = _gen_enginecodes_xml()
    xml_path = out_dir / "EngineCodes.xml"
    ET.ElementTree(xml_root).write(xml_path, encoding="utf-8", xml_declaration=True)
    print(f"  XML: {xml_path}")

    # ZIP (just one background)
    zip_path = out_dir / "EngineCodes_ALL_Images.zip"
    with ZipFile(zip_path, "w", ZIP_DEFLATED) as z:
        bg = _render_enginecodes_bg()
        _add_png(z, EC_BG_ID, bg)
    print(f"  ZIP: {zip_path} (1 image)")


# ──────────────────── main ────────────────────────────

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app", choices=["boostdeck", "shiftdeck", "enginecodes", "all"],
                        default="all")
    parser.add_argument("--preview", action="store_true",
                        help="Generate preview mockups only (no ZIPs)")
    args = parser.parse_args()

    PLUGIN_DIR.mkdir(exist_ok=True)

    if args.preview:
        print("Preview mode — generating mockup images only")
        # TODO: generate preview mockups using the asset renderers
        return

    apps = [args.app] if args.app != "all" else ["boostdeck", "shiftdeck", "enginecodes"]

    for app in apps:
        if app == "boostdeck":
            generate_boostdeck(PLUGIN_DIR)
        elif app == "shiftdeck":
            generate_shiftdeck(PLUGIN_DIR)
        elif app == "enginecodes":
            generate_enginecodes(PLUGIN_DIR)

    print("\n=== All assets generated ===")
    print(f"Output: {PLUGIN_DIR}/")


if __name__ == "__main__":
    main()
