"""M Performance app mockups — all 4 pages, glass aesthetic."""
from math import sin, cos, radians, pi
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
W, H = 1280, 480
S = 2


def ft(size):
    for p in ["/System/Library/Fonts/Supplemental/DIN Condensed Bold.ttf",
              "/System/Library/Fonts/Helvetica.ttc"]:
        try: return ImageFont.truetype(p, size * S)
        except (OSError, IOError): pass
    return ImageFont.load_default()


def ramp(colors, f):
    f = max(0.0, min(1.0, f))
    n = len(colors) - 1
    i = min(n - 1, int(f * n))
    t = f * n - i
    return tuple(int(colors[i][j] + (colors[i+1][j] - colors[i][j]) * t) for j in range(3))


def bloom(img, cx, cy, radius, color, alpha=35):
    layer = Image.new('RGBA', img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for i in range(max(4, radius // 3)):
        r = radius * (1 - i / max(1, radius // 3))
        a = int(alpha * (i / max(1, radius // 3)) ** 0.3 * (max(0, radius // 3 - i) / max(1, radius // 3)) ** 0.5)
        if a > 0 and r > 1:
            d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=color[:3] + (min(255, a),))
    return Image.alpha_composite(img, layer.filter(ImageFilter.GaussianBlur(max(2, radius // 4))))


def smooth_arc(img, cx, cy, ro, ri, frac, color, start=150, sweep=240):
    sc = 3
    buf = Image.new('RGBA', (img.width * sc, img.height * sc), (0, 0, 0, 0))
    bd = ImageDraw.Draw(buf)
    t = (ro - ri) * sc
    mr = ((ro + ri) // 2) * sc
    bb = (cx*sc - mr, cy*sc - mr, cx*sc + mr, cy*sc + mr)
    bd.arc(bb, start, start + sweep, fill=(255, 255, 255, 16), width=t)
    if frac > 0.005:
        bd.arc(bb, start, start + sweep * frac, fill=color + (240,), width=t)
        bloom_buf = Image.new('RGBA', buf.size, (0, 0, 0, 0))
        ImageDraw.Draw(bloom_buf).arc(bb, start, start + sweep * frac, fill=color + (45,), width=t + sc * 16)
        bloom_buf = bloom_buf.filter(ImageFilter.GaussianBlur(sc * 5))
        buf = Image.alpha_composite(buf, bloom_buf)
    img = Image.alpha_composite(img, buf.resize(img.size, Image.LANCZOS))
    if frac > 0.01:
        tip_rad = radians(start + sweep * frac)
        tip_r = (ri + ro) / 2
        img = bloom(img, int(cx + cos(tip_rad) * tip_r), int(cy + sin(tip_rad) * tip_r), 16*S, color, 55)
    return img


def gpanel(img, x, y, w, h, edge, r=14, op=0.25):
    p = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(p)
    a = int(255 * op)
    d.rounded_rectangle((0, 0, w-1, h-1), radius=r, fill=(12, 14, 20, a))
    d.rounded_rectangle((0, 0, w-1, h-1), radius=r, outline=edge + (30,), width=S)
    d.line((r+4, 1, w-r-4, 1), fill=(255, 255, 255, 18), width=1)
    img.paste(p, (x, y), p)
    return img


def bg(accent):
    img = Image.new('RGBA', (W*S, H*S), (0, 0, 0, 255))
    draw = ImageDraw.Draw(img)
    for y in range(H*S):
        yf = y / (H*S)
        v = max(0, 0.5 - abs(yf - 0.4)) * 2
        base = tuple(max(2, int(3 + 6*v + accent[i]*0.008*v)) for i in range(3))
        draw.line((0, y, W*S, y), fill=base)
    return img


def centered(draw, text, cx, y, size, color):
    f = ft(size)
    bb = draw.textbbox((0, 0), text, font=f)
    tw = bb[2] - bb[0]
    draw.text((cx - tw//2, y), text, fill=color, font=f)


def pal(accent):
    return {
        'accent': accent,
        'label': tuple(min(255, int(c*0.55+105)) for c in accent),
        'dim': tuple(min(255, int(c*0.4+70)) for c in accent),
        'green': (50, 210, 110),
        'warn': (240, 180, 40),
        'edge': tuple(min(100, int(c*0.3+25)) for c in accent),
    }


def draw_segmented_bar(img, x, y, w, h, frac, colors, segs=20, slant=8*S):
    draw = ImageDraw.Draw(img)
    gap = 3*S
    seg_w = (w - (segs-1)*gap) / segs
    filled = int(frac * segs)
    for s in range(segs):
        sx = x + s * (seg_w + gap)
        f = s / max(1, segs-1)
        for row in range(h):
            rf = row / max(1, h-1)
            offset = slant * (1 - rf)
            lx, rx = sx + offset, sx + seg_w + offset
            if s < filled:
                c = ramp(colors, f)
                bright = 1.15 - 0.3 * rf
                fill_c = tuple(min(255, int(v*bright)) for v in c) + (230,)
            else:
                fill_c = (255, 255, 255, 8)
            draw.line((int(lx), y+row, int(rx), y+row), fill=fill_c)
    if 0 < filled < segs:
        gx = x + filled * (seg_w+gap) + slant//2
        tc = ramp(colors, filled/segs)
        img = bloom(img, int(gx), y+h//2, 14*S, tc, 50)
    return img


# ──────────────────────────────────────────────
# PAGE 1: DRAG TIMER (RUNNING STATE)
# ──────────────────────────────────────────────
def page_drag(accent):
    p = pal(accent)
    img = bg(accent)
    ec = p['edge']

    # title
    draw = ImageDraw.Draw(img)
    draw.text((30*S, 6*S), "M Performance", fill=p['label'], font=ft(18))
    draw.text(((W-82)*S, 8*S), "DRAG", fill=accent+(180,), font=ft(14))
    draw.line((30*S, 26*S, (W-30)*S, 26*S), fill=accent+(15,), width=S)

    # status badge — RUNNING
    cx = W*S//2
    draw.rounded_rectangle((cx-60*S, 32*S, cx+60*S, 52*S), radius=4*S, fill=accent+(50,))
    centered(draw, "RUNNING", cx, 34*S, 14, accent+(230,))

    # big timer — center hero
    img = gpanel(img, 280*S, 60*S, 720*S, 200*S, ec, r=16*S, op=0.22)
    img = bloom(img, cx, 155*S, 120*S, accent, 8)
    draw = ImageDraw.Draw(img)
    centered(draw, "3.14", cx, 80*S, 90, (255, 255, 255, 250))
    centered(draw, "seconds", cx, 195*S, 16, p['dim'])

    # current speed — large, under timer
    centered(draw, "87", cx, 225*S, 50, accent+(240,))
    centered(draw, "MPH", cx, 280*S, 14, p['dim'])

    # speed progress bar
    img = draw_segmented_bar(img, 80*S, 310*S, (W-160)*S, 28*S, 87.0/160.0,
                             [(20, 30, 50), accent, accent, (min(255, accent[0]+60), max(30, accent[1]-20), max(20, accent[2]-30))])

    # splits — left panel
    img = gpanel(img, 30*S, 60*S, 230*S, 200*S, ec, r=12*S, op=0.2)
    draw = ImageDraw.Draw(img)
    splits = [("0-30", "1.42", True), ("0-60", "---", False), ("0-100", "---", False)]
    for i, (label, val, done) in enumerate(splits):
        sy = (80 + i * 60) * S
        draw.text((50*S, sy), label, fill=p['label'], font=ft(13))
        color = p['green'] + (230,) if done else (120, 130, 150, 150)
        draw.text((50*S, sy + 18*S), val, fill=color, font=ft(28))
        draw.text((160*S, sy + 24*S), "sec" if done else "", fill=p['dim'], font=ft(11))

    # 1/4 mile — right panel
    img = gpanel(img, (W-260)*S, 60*S, 230*S, 200*S, ec, r=12*S, op=0.2)
    draw = ImageDraw.Draw(img)
    draw.text(((W-240)*S, 80*S), "1/4 MILE", fill=p['label'], font=ft(14))
    draw.text(((W-240)*S, 105*S), "---", fill=(120, 130, 150, 150), font=ft(36))
    draw.text(((W-240)*S, 160*S), "TRAP", fill=p['label'], font=ft(12))
    draw.text(((W-240)*S, 178*S), "---", fill=(120, 130, 150, 150), font=ft(28))
    draw.text(((W-155)*S, 184*S), "MPH", fill=p['dim'], font=ft(11))

    # RPM + gear bottom info
    img = gpanel(img, 30*S, 355*S, (W-60)*S, 80*S, ec, r=8*S, op=0.12)
    draw = ImageDraw.Draw(img)
    draw.text((60*S, 370*S), "GEAR", fill=p['label'], font=ft(11))
    draw.text((60*S, 385*S), "3", fill=(255, 255, 255, 240), font=ft(30))
    draw.text((180*S, 370*S), "RPM", fill=p['label'], font=ft(11))
    draw.text((180*S, 385*S), "5,230", fill=(255, 255, 255, 200), font=ft(24))
    draw.text(((W-200)*S, 370*S), "DISTANCE", fill=p['label'], font=ft(11))
    draw.text(((W-200)*S, 385*S), "127 m", fill=(255, 255, 255, 200), font=ft(24))
    draw.text(((W-82)*S, 385*S), "EST", fill=p['dim']+(100,), font=ft(10))

    # ambient strip
    for x in range(35*S, (W-35)*S):
        f = (x - 35*S) / ((W-70)*S)
        center = 1 - (2*abs(f-0.5))**1.5
        a = int(18*center)
        if a > 0:
            draw.line((x, H*S-2*S, x, H*S), fill=accent+(a,))

    return img.resize((W, H), Image.LANCZOS)


# ──────────────────────────────────────────────
# PAGE 2: BEST TIMES
# ──────────────────────────────────────────────
def page_bests(accent):
    p = pal(accent)
    img = bg(accent)
    ec = p['edge']

    draw = ImageDraw.Draw(img)
    draw.text((30*S, 6*S), "M Performance", fill=p['label'], font=ft(18))
    draw.text(((W-110)*S, 8*S), "BEST TIMES", fill=accent+(180,), font=ft(14))
    draw.line((30*S, 26*S, (W-30)*S, 26*S), fill=accent+(15,), width=S)

    # left — all-time bests
    img = gpanel(img, 30*S, 40*S, 380*S, 390*S, ec, r=14*S, op=0.22)
    draw = ImageDraw.Draw(img)
    centered(draw, "ALL-TIME BEST", 220*S, 52*S, 16, p['label'])

    bests = [("0-60 MPH", "3.14", "sec"), ("0-100 MPH", "7.82", "sec"),
             ("1/4 MILE", "11.24", "sec"), ("TRAP SPEED", "128", "MPH")]
    for i, (label, val, unit) in enumerate(bests):
        by = (100 + i * 72) * S
        centered(draw, label, 220*S, by, 13, p['dim'])
        centered(draw, val, 190*S, by + 18*S, 38, accent+(240,))
        draw.text((260*S, by + 30*S), unit, fill=p['dim'], font=ft(13))

    # right — recent runs
    img = gpanel(img, 430*S, 40*S, (W-460)*S, 390*S, ec, r=14*S, op=0.18)
    draw = ImageDraw.Draw(img)
    draw.text((450*S, 52*S), "RECENT RUNS", fill=p['label'], font=ft(14))

    runs = [
        {"date": "Today 8:42 PM", "t060": "3.14", "qtr": "11.24", "trap": "128"},
        {"date": "Today 8:38 PM", "t060": "3.21", "qtr": "11.31", "trap": "126"},
        {"date": "Nov 16 4:15 PM", "t060": "3.18", "qtr": "11.28", "trap": "127"},
        {"date": "Nov 15 2:30 PM", "t060": "3.45", "qtr": "11.62", "trap": "124"},
    ]

    for i, run in enumerate(runs):
        ry = (90 + i * 80) * S
        # glass card row
        cw = (W - 500) * S
        card = Image.new('RGBA', (cw, 68*S), (0, 0, 0, 0))
        cd = ImageDraw.Draw(card)
        cd.rounded_rectangle((0, 0, cw-1, 68*S-1), radius=8*S, fill=(12, 14, 20, int(255*0.16)))
        cd.rounded_rectangle((0, 0, cw-1, 68*S-1), radius=8*S, outline=ec+(25,), width=S)
        img.paste(card, (450*S, ry), card)

        draw = ImageDraw.Draw(img)
        draw.text((470*S, ry + 5*S), run["date"], fill=p['dim'], font=ft(10))
        draw.text((470*S, ry + 22*S), f"0-60: {run['t060']}s", fill=(255, 255, 255, 230), font=ft(18))
        draw.text((700*S, ry + 22*S), f"1/4: {run['qtr']}s", fill=(255, 255, 255, 200), font=ft(18))
        draw.text((920*S, ry + 22*S), f"@ {run['trap']} MPH", fill=p['dim'], font=ft(14))
        if i == 0:
            draw.text(((W-100)*S, ry + 8*S), "BEST", fill=p['green']+(200,), font=ft(11))

    # ambient strip
    draw = ImageDraw.Draw(img)
    for x in range(35*S, (W-35)*S):
        f = (x - 35*S) / ((W-70)*S)
        center = 1 - (2*abs(f-0.5))**1.5
        a = int(18*center)
        if a > 0: draw.line((x, H*S-2*S, x, H*S), fill=accent+(a,))

    return img.resize((W, H), Image.LANCZOS)


# ──────────────────────────────────────────────
# PAGE 3: G-FORCE
# ──────────────────────────────────────────────
def page_gforce(accent):
    p = pal(accent)
    img = bg(accent)
    ec = p['edge']

    draw = ImageDraw.Draw(img)
    draw.text((30*S, 6*S), "M Performance", fill=p['label'], font=ft(18))
    draw.text(((W-100)*S, 8*S), "G-FORCE", fill=accent+(180,), font=ft(14))
    draw.line((30*S, 26*S, (W-30)*S, 26*S), fill=accent+(15,), width=S)

    # friction circle — left
    cx, cy = 300*S, 250*S
    img = gpanel(img, 40*S, 40*S, 520*S, 400*S, ec, r=14*S, op=0.2)

    # concentric rings
    draw = ImageDraw.Draw(img)
    for g_val in [0.5, 1.0, 1.5]:
        r = int(g_val * 120 * S)
        draw.ellipse((cx-r, cy-r, cx+r, cy+r), outline=(255, 255, 255, 20), width=S)
        draw.text((cx + r + 4*S, cy - 8*S), f"{g_val}g", fill=p['dim']+(80,), font=ft(9))

    # crosshairs
    draw.line((cx, cy - 185*S, cx, cy + 185*S), fill=(255, 255, 255, 12), width=S)
    draw.line((cx - 185*S, cy, cx + 185*S, cy), fill=(255, 255, 255, 12), width=S)

    # labels
    centered(draw, "ACCEL", cx, cy - 195*S, 10, p['dim']+(80,))
    centered(draw, "BRAKE", cx, cy + 185*S, 10, p['dim']+(80,))
    draw.text((cx - 205*S, cy - 8*S), "L", fill=p['dim']+(80,), font=ft(10))
    draw.text((cx + 192*S, cy - 8*S), "R", fill=p['dim']+(80,), font=ft(10))

    # live G dot (simulated at 0.46g forward, 0.01g right)
    dot_x = cx + int(0.01 * 120 * S)
    dot_y = cy - int(0.46 * 120 * S)
    img = bloom(img, dot_x, dot_y, 18*S, accent, 50)
    draw = ImageDraw.Draw(img)
    draw.ellipse((dot_x - 6*S, dot_y - 6*S, dot_x + 6*S, dot_y + 6*S), fill=accent+(245,))

    # trail (fading dots)
    trail = [(0.40, -0.02), (0.35, 0.01), (0.30, 0.03), (0.25, 0.02), (0.20, 0.0)]
    for i, (lg, lat) in enumerate(trail):
        tx = cx + int(lat * 120 * S)
        ty = cy - int(lg * 120 * S)
        a = int(120 * (1 - i / len(trail)))
        draw.ellipse((tx - 3*S, ty - 3*S, tx + 3*S, ty + 3*S), fill=accent[:3] + (a,))

    # readouts — right panel
    img = gpanel(img, 600*S, 40*S, 650*S, 400*S, ec, r=14*S, op=0.18)
    draw = ImageDraw.Draw(img)

    readings = [
        ("LONGITUDINAL", "0.46", "g", True),
        ("LATERAL", "0.01", "g", True),
        ("COMBINED", "0.46", "g", True),
        ("PEAK ACCEL", "0.96", "g", False),
        ("PEAK BRAKE", "1.04", "g", False),
        ("PEAK LATERAL", "0.89", "g", False),
    ]

    for i, (label, val, unit, is_live) in enumerate(readings):
        ry = (65 + i * 62) * S
        draw.text((630*S, ry), label, fill=p['label'], font=ft(11))
        color = (255, 255, 255, 240) if is_live else accent + (200,)
        draw.text((630*S, ry + 16*S), val, fill=color, font=ft(30))
        vbb = draw.textbbox((630*S, ry+16*S), val, font=ft(30))
        draw.text((vbb[2]+4*S, ry+26*S), unit, fill=p['dim'], font=ft(12))
        if not is_live:
            draw.text(((W-80)*S, ry+4*S), "PEAK", fill=accent+(100,), font=ft(9))

    # ambient strip
    draw = ImageDraw.Draw(img)
    for x in range(35*S, (W-35)*S):
        f = (x - 35*S) / ((W-70)*S)
        center = 1 - (2*abs(f-0.5))**1.5
        a = int(18*center)
        if a > 0: draw.line((x, H*S-2*S, x, H*S), fill=accent+(a,))

    return img.resize((W, H), Image.LANCZOS)


# ──────────────────────────────────────────────
# PAGE 4: BRAKE TEST
# ──────────────────────────────────────────────
def page_brake(accent):
    p = pal(accent)
    img = bg(accent)
    ec = p['edge']

    draw = ImageDraw.Draw(img)
    draw.text((30*S, 6*S), "M Performance", fill=p['label'], font=ft(18))
    draw.text(((W-100)*S, 8*S), "BRAKES", fill=accent+(180,), font=ft(14))
    draw.line((30*S, 26*S, (W-30)*S, 26*S), fill=accent+(15,), width=S)

    # center — big distance number
    cx = W*S//2
    img = gpanel(img, 200*S, 45*S, (W-400)*S, 220*S, ec, r=16*S, op=0.22)
    draw = ImageDraw.Draw(img)
    centered(draw, "60-0 MPH", cx, 58*S, 16, p['label'])
    centered(draw, "98", cx, 90*S, 80, (255, 255, 255, 250))
    centered(draw, "FEET", cx, 195*S, 18, p['dim'])

    # decel arc gauge
    img = smooth_arc(img, cx, 150*S, 140*S, 126*S, 0.85,
                     (255, 80, 50), start=180, sweep=180)

    # peak decel
    centered(draw, "PEAK", cx - 250*S, 130*S, 12, p['label'])
    centered(draw, "1.04g", cx - 250*S, 148*S, 28, accent+(230,))

    # time
    centered(draw, "TIME", cx + 250*S, 130*S, 12, p['label'])
    centered(draw, "2.41s", cx + 250*S, 148*S, 28, accent+(230,))

    draw = ImageDraw.Draw(img)

    # splits panel
    img = gpanel(img, 30*S, 290*S, (W-60)*S, 70*S, ec, r=10*S, op=0.15)
    draw = ImageDraw.Draw(img)

    splits_data = [("60-0 MPH", "98 ft", "2.41s"), ("100-0 MPH", "312 ft", "4.18s")]
    for i, (label, dist, time) in enumerate(splits_data):
        sx = (80 + i * 550) * S
        draw.text((sx, 300*S), label, fill=p['label'], font=ft(13))
        draw.text((sx, 320*S), dist, fill=(255, 255, 255, 240), font=ft(26))
        draw.text((sx + 180*S, 326*S), time, fill=p['dim'], font=ft(16))

    # best distances — bottom
    img = gpanel(img, 30*S, 380*S, (W-60)*S, 70*S, ec, r=8*S, op=0.12)
    draw = ImageDraw.Draw(img)
    draw.text((60*S, 390*S), "SESSION BEST", fill=p['label'], font=ft(12))
    draw.text((60*S, 408*S), "60-0: 95 ft  |  100-0: 308 ft  |  Peak: 1.12g", fill=accent+(180,), font=ft(16))
    draw.text(((W-160)*S, 400*S), "RESET", fill=p['dim']+(120,), font=ft(12))

    # ambient strip
    draw = ImageDraw.Draw(img)
    for x in range(35*S, (W-35)*S):
        f = (x - 35*S) / ((W-70)*S)
        center = 1 - (2*abs(f-0.5))**1.5
        a = int(18*center)
        if a > 0: draw.line((x, H*S-2*S, x, H*S), fill=accent+(a,))

    return img.resize((W, H), Image.LANCZOS)


def main():
    out = ROOT / 'plugin'
    colors = [('purple', (155, 75, 215)), ('orange', (255, 140, 30)), ('ice', (80, 180, 255))]

    for cname, accent in colors:
        for pname, fn in [('drag', page_drag), ('bests', page_bests), ('gforce', page_gforce), ('brake', page_brake)]:
            img = fn(accent)
            path = out / f'mperf_{pname}_{cname}.png'
            img.save(path, format='PNG', optimize=True)
            print(f'{pname}_{cname}: {path}')


if __name__ == '__main__':
    main()
