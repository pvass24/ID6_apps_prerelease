"""Engine Fault Codes V3 — crisp text (2x render), no glow bleed, centered content."""
from math import cos, radians
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
W, H = 1280, 480
S = 2  # render scale


def ft(size):
    for p in ["/System/Library/Fonts/Supplemental/DIN Condensed Bold.ttf",
              "/System/Library/Fonts/Helvetica.ttc"]:
        try: return ImageFont.truetype(p, size * S)
        except (OSError, IOError): pass
    return ImageFont.load_default()


def smooth_arc(img, cx, cy, ro, ri, frac, color, start=150, sweep=240):
    sc = 3
    buf = Image.new('RGBA', (img.width * sc, img.height * sc), (0, 0, 0, 0))
    bd = ImageDraw.Draw(buf)
    t = (ro - ri) * sc
    mr = ((ro + ri) // 2) * sc
    bb = (cx*sc - mr, cy*sc - mr, cx*sc + mr, cy*sc + mr)
    bd.arc(bb, start, start + sweep, fill=(255,255,255,16), width=t)
    if frac > 0.005:
        bd.arc(bb, start, start + sweep * frac, fill=color + (235,), width=t)
    img = Image.alpha_composite(img, buf.resize(img.size, Image.LANCZOS))
    return img


def gpanel(img, x, y, w, h, edge, r=14, op=0.25):
    p = Image.new('RGBA', (w, h), (0,0,0,0))
    d = ImageDraw.Draw(p)
    a = int(255 * op)
    d.rounded_rectangle((0,0,w-1,h-1), radius=r, fill=(12,14,20,a))
    d.rounded_rectangle((0,0,w-1,h-1), radius=r, outline=edge+(30,), width=S)
    d.line((r+4,1,w-r-4,1), fill=(255,255,255,18), width=1)
    img.paste(p, (x, y), p)
    return img


def ccard(w, h, sev_color, edge, r=10):
    c = Image.new('RGBA', (w, h), (0,0,0,0))
    d = ImageDraw.Draw(c)
    d.rounded_rectangle((0,0,w-1,h-1), radius=r, fill=(12,14,20, int(255*0.18)))
    d.rounded_rectangle((0,0,w-1,h-1), radius=r, outline=edge+(25,), width=S)
    d.line((r+3,1,w-r-3,1), fill=(255,255,255,12), width=1)
    # severity stripe
    sw = 6 * S
    for y in range(r, h-r):
        d.line((S, y, S+sw, y), fill=sev_color+(220,))
    for y in range(r, h-r):
        for x in range(sw + S, sw + S + 14*S):
            ga = int(15 * (1 - (x - sw - S) / (14*S)) ** 2)
            if ga > 0: d.point((x, y), fill=sev_color+(ga,))
    return c


def centered_text(draw, text, cx, y, size, color):
    f = ft(size)
    bb = draw.textbbox((0,0), text, font=f)
    tw = bb[2] - bb[0]
    draw.text((cx - tw//2, y), text, fill=color, font=f)


def render(accent, state='results'):
    ec = tuple(min(100, int(c*0.3+25)) for c in accent)
    lc = tuple(min(255, int(c*0.55+105)) for c in accent)
    dc = tuple(min(255, int(c*0.4+70)) for c in accent)

    codes = [
        {'hex': '2C5B00', 'st': 0xAF, 'sev': 'active',  'desc': 'O2 sensor B1S2 — signal range'},
        {'hex': '2A6B05', 'st': 0x2F, 'sev': 'pending', 'desc': 'Boost pressure — deviation neg'},
        {'hex': '2A1E00', 'st': 0x27, 'sev': 'stored',  'desc': 'Throttle valve adapt — lower stop'},
        {'hex': '2A0400', 'st': 0x24, 'sev': 'stored',  'desc': 'Fuel injector cyl 3 — activation'},
    ]
    sc = {
        'active': (255, 50, 40),
        'pending': (240, 180, 40),
        'stored': (80, 90, 110),
    }

    rw, rh = W*S, H*S
    img = Image.new('RGBA', (rw, rh), (0,0,0,255))
    draw = ImageDraw.Draw(img)

    for y in range(rh):
        yf = y / rh
        v = max(0, 0.5 - abs(yf - 0.4)) * 2
        base = tuple(max(2, int(3 + 6*v + accent[i]*0.008*v)) for i in range(3))
        draw.line((0, y, rw, y), fill=base)

    # title
    draw.text((30*S, 6*S), "Engine Fault Codes", fill=lc, font=ft(18))
    draw.text(((W-82)*S, 8*S), "2:51 pm", fill=(55,62,75), font=ft(14))
    draw.line((30*S, 26*S, (W-30)*S, 26*S), fill=accent+(15,), width=S)

    if state == 'clear':
        cx, cy = rw//2, 185*S
        green = (50, 210, 110)
        img = smooth_arc(img, cx, cy, 130*S, 115*S, 1.0, green)
        draw = ImageDraw.Draw(img)

        centered_text(draw, "0", cx, cy - 32*S, 56, (255,255,255,250))
        centered_text(draw, "CODES", cx, cy + 30*S, 16, (255,255,255,140))
        centered_text(draw, "ALL CLEAR", cx, cy + 58*S, 22, (255,255,255,220))
        centered_text(draw, "Last scanned: just now", cx, cy + 105*S, 14, dc)

        bw, bh = 160*S, 35*S
        bx, by = cx - bw//2, cy + 140*S
        draw.rounded_rectangle((bx, by, bx+bw, by+bh), radius=8*S, fill=accent[:3]+(25,))
        draw.rounded_rectangle((bx, by, bx+bw, by+bh), radius=8*S, outline=accent[:3]+(55,), width=S)
        centered_text(draw, "Read again", cx, by + 8*S, 16, accent+(200,))

    elif state == 'empty':
        cx, cy = rw//2, 190*S
        img = smooth_arc(img, cx, cy, 120*S, 108*S, 0, accent)
        draw = ImageDraw.Draw(img)
        centered_text(draw, "DME", cx, cy - 24*S, 40, accent+(180,))
        centered_text(draw, "READY", cx, cy + 22*S, 16, dc)
        centered_text(draw, "Select Read engine codes", cx, cy + 65*S, 18, (180,190,205))

    else:
        active = sum(1 for c in codes if c['sev'] == 'active')
        pending = sum(1 for c in codes if c['sev'] == 'pending')
        total = len(codes)

        # left panel
        lw = 300*S
        img = gpanel(img, 30*S, 40*S, lw, 400*S, ec, r=14*S, op=0.22)

        # health ring
        cx, cy = 30*S + lw//2, 180*S
        sweep = 240
        seg_per = sweep / max(1, total + 2)
        cursor = 150
        img = smooth_arc(img, cx, cy, 110*S, 96*S, 0, accent)
        for sev, cnt, svc in [('active', active, (255,50,40)),
                               ('pending', pending, (240,180,40)),
                               ('stored', total-active-pending, (70,80,100))]:
            if cnt > 0:
                ss = seg_per * cnt
                img = smooth_arc(img, cx, cy, 110*S, 96*S, 1.0, svc, start=cursor, sweep=ss)
                cursor += ss

        draw = ImageDraw.Draw(img)
        centered_text(draw, str(total), cx, cy - 30*S, 52, (255,255,255,250))
        centered_text(draw, "CODES", cx, cy + 28*S, 14, dc)

        # severity breakdown — left-aligned group, group centered in panel
        items = [(cnt, sn, svc) for sn, cnt, svc in [('ACTIVE', active, (255,50,40)),
                              ('PENDING', pending, (240,180,40)),
                              ('STORED', total-active-pending, (80,90,110))] if cnt > 0]
        item_h = 28*S
        block_h = len(items) * item_h
        by = 290*S + (70*S - block_h) // 2
        dot_r = 5*S
        text_offset = dot_r*2 + 10*S

        # find widest item to center the whole block
        max_w = 0
        lf = ft(14)
        for cnt, sn, svc in items:
            lb = draw.textbbox((0,0), f"{cnt} {sn}", font=lf)
            max_w = max(max_w, text_offset + lb[2] - lb[0])
        block_x = cx - max_w // 2

        for cnt, sn, svc in items:
            label = f"{cnt} {sn}"
            lb = draw.textbbox((0,0), label, font=lf)
            draw.ellipse((block_x, by + item_h//2 - dot_r, block_x + dot_r*2, by + item_h//2 + dot_r), fill=svc+(220,))
            draw.text((block_x + text_offset, by + (item_h - (lb[3]-lb[1]))//2), label, fill=svc+(220,), font=lf)
            by += item_h

        # buttons — centered side by side within the left panel
        btn_y = 385*S
        btn_h = 35*S
        bw_each = 115*S
        btn_gap = 12*S
        total_btn_w = bw_each * 2 + btn_gap
        panel_left = 30*S
        panel_cx = panel_left + lw // 2
        bx1 = panel_cx - total_btn_w // 2
        bx2 = bx1 + bw_each + btn_gap

        draw.rounded_rectangle((bx1, btn_y, bx1+bw_each, btn_y+btn_h), radius=6*S, fill=accent[:3]+(70,))
        draw.rounded_rectangle((bx1, btn_y, bx1+bw_each, btn_y+btn_h), radius=6*S, outline=accent[:3]+(120,), width=S)
        rlf = ft(16)
        rlb = draw.textbbox((0,0), "READ", font=rlf)
        rlth = rlb[3] - rlb[1]
        draw.text((bx1 + (bw_each - (rlb[2]-rlb[0]))//2, btn_y + (btn_h - rlth)//2), "READ", fill=(255,255,255,230), font=rlf)

        draw.rounded_rectangle((bx2, btn_y, bx2+bw_each, btn_y+btn_h), radius=6*S, fill=(255,50,40,50))
        draw.rounded_rectangle((bx2, btn_y, bx2+bw_each, btn_y+btn_h), radius=6*S, outline=(255,50,40,90), width=S)
        clb = draw.textbbox((0,0), "CLEAR", font=rlf)
        clth = clb[3] - clb[1]
        draw.text((bx2 + (bw_each - (clb[2]-clb[0]))//2, btn_y + (btn_h - clth)//2), "CLEAR", fill=(255,100,80,230), font=rlf)

        # code cards
        card_x = 350*S
        card_w = (W - 350 - 35) * S
        card_h = 90*S

        for i, code in enumerate(codes):
            cy_c = 42*S + i * (card_h + 6*S)
            svc = sc.get(code['sev'], (80,90,110))

            card = ccard(card_w, card_h, svc, ec, r=10*S)
            # tinted border for active/pending
            if code['sev'] in ('active', 'pending'):
                td = ImageDraw.Draw(card)
                ta = 30 if code['sev'] == 'active' else 18
                td.rounded_rectangle((0,0,card_w-1,card_h-1), radius=10*S, outline=svc+(ta,), width=2*S)
            img.paste(card, (card_x, cy_c), card)

            draw = ImageDraw.Draw(img)

            # content vertically centered
            ct = cy_c + (card_h - 62*S) // 2

            # hex code
            draw.text((card_x + 24*S, ct), code['hex'], fill=(255,255,255,245), font=ft(26))

            # description
            draw.text((card_x + 24*S, ct + 32*S), code['desc'], fill=(210,218,235), font=ft(17))

            # status
            draw.text((card_x + 24*S, ct + 55*S), f"status {code['st']:02X}", fill=dc+(130,), font=ft(11))

            # severity tag — right side, truly centered vertically and horizontally
            tag_label = code['sev'].upper()
            tlf = ft(12)
            tlb = draw.textbbox((0,0), tag_label, font=tlf)
            tlw = tlb[2] - tlb[0]
            tlh = tlb[3] - tlb[1]
            tag_pad_x = 10*S
            tag_pad_y = 5*S
            tag_w = tlw + tag_pad_x * 2
            tag_h = tlh + tag_pad_y * 2
            tag_x = card_x + card_w - tag_w - 14*S
            tag_y = cy_c + (card_h - tag_h) // 2
            ta = svc + (55 if code['sev'] == 'active' else 35,)
            draw.rounded_rectangle((tag_x, tag_y, tag_x + tag_w, tag_y + tag_h), radius=4*S, fill=ta)
            draw.text((tag_x + tag_pad_x, tag_y + tag_pad_y), tag_label, fill=svc+(240,), font=tlf)

        # page
        draw.text(((W-120)*S, (H-35)*S), "Page 1 / 1", fill=dc, font=ft(13))

    # ambient strip
    draw = ImageDraw.Draw(img)
    for x in range(35*S, (W-35)*S):
        f = (x - 35*S) / ((W-70)*S)
        center = 1 - (2*abs(f-0.5))**1.5
        a = int(18*center)
        if a > 0:
            draw.line((x, rh-2*S, x, rh), fill=accent+(a,))

    # downscale for crisp output
    return img.resize((W, H), Image.LANCZOS)


def main():
    out = ROOT / 'plugin'
    for cn, ac in [('orange',(255,140,30)),('ice',(80,180,255)),('purple',(155,75,215)),('red',(225,40,50))]:
        for st in ('results', 'clear', 'empty'):
            render(ac, st).save(out / f'codes_v3_{cn}_{st}.png', format='PNG')
    print(f'Engine Codes V3 saved to {out}')


if __name__ == '__main__':
    main()
