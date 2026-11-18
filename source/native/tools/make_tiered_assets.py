"""Generate BoostDeck glass assets at multiple step counts for safe deployment.

Tier 1 (32 steps):  Uses original kBarFirst=55000 — works with STOCK binaries
Tier 2 (64 steps):  Uses kBarFirst=60000 — needs recompiled binary with kDialSteps=64
Tier 3 (256 steps): Uses kBarFirst=60000 — needs recompiled binary with kDialSteps=256
"""
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo
from io import BytesIO

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'plugin'


def build_zip_manual(out_path, steps, base_id, colors, multicolors):
    """Build a BoostDeck ZIP at the given step count and base ID.

    This is a standalone generator that doesn't depend on make_glass_upgrade.
    """
    from PIL import Image, ImageDraw, ImageFilter

    def ramp(cols, f):
        f = max(0.0, min(1.0, f))
        n = len(cols) - 1
        i = min(n - 1, int(f * n))
        t = f * n - i
        return tuple(int(cols[i][j] + (cols[i+1][j] - cols[i][j]) * t) for j in range(3))

    def render_arc(size, fill_frac, color_ramp):
        """Render a single arc fill frame at 3x then downscale."""
        scale = 3
        buf = Image.new('RGBA', (size * scale, size * scale), (0, 0, 0, 0))
        d = ImageDraw.Draw(buf)
        cx, cy = size * scale // 2, size * scale // 2
        ro, ri = int(size * 0.42 * scale), int(size * 0.365 * scale)
        thickness = ro - ri
        mid_r = (ro + ri) // 2
        bb = (cx - mid_r, cy - mid_r, cx + mid_r, cy + mid_r)
        start, sweep = 150, 240

        # dim track
        d.arc(bb, start, start + sweep, fill=(255, 255, 255, 16), width=thickness)

        if fill_frac > 0.003:
            end = start + sweep * fill_frac
            segs = max(2, int(fill_frac * 100))
            for s in range(segs):
                a0 = start + (end - start) * s / segs
                a1 = start + (end - start) * (s + 1) / segs + 0.3
                f = (s / max(1, segs - 1)) * fill_frac
                c = ramp(color_ramp, f)
                d.arc(bb, a0, a1, fill=c + (240,), width=thickness)

            # bloom
            bloom = Image.new('RGBA', buf.size, (0, 0, 0, 0))
            bd = ImageDraw.Draw(bloom)
            for s in range(max(2, segs // 3)):
                a0 = start + (end - start) * s / max(1, segs // 3)
                a1 = start + (end - start) * (s + 1) / max(1, segs // 3) + 0.5
                f = (s / max(1, segs // 3 - 1)) * fill_frac
                c = ramp(color_ramp, f)
                bd.arc(bb, a0, a1, fill=c + (40,), width=thickness + scale * 16)
            bloom = bloom.filter(ImageFilter.GaussianBlur(scale * 5))
            buf = Image.alpha_composite(buf, bloom)

        return buf.resize((size, size), Image.LANCZOS)

    SIZE = 260

    # Color ramps for each palette
    solid_ramps = {
        0: [(60, 25, 5), (180, 70, 15), (255, 80, 26), (255, 160, 60)],      # BMW Orange
        1: [(15, 50, 100), (40, 120, 200), (88, 206, 255), (180, 230, 255)],  # Blue
        2: [(15, 60, 30), (40, 150, 80), (108, 219, 147), (180, 240, 200)],   # Green
        3: [(50, 55, 65), (140, 150, 160), (200, 210, 220), (226, 234, 240)], # White
        4: [(50, 20, 80), (120, 60, 180), (173, 114, 255), (210, 170, 255)],  # Purple
        5: [(80, 20, 50), (180, 50, 120), (255, 108, 186), (255, 170, 215)],  # Pink
        6: [(10, 60, 60), (20, 170, 160), (32, 241, 230), (150, 250, 245)],   # Cyan
        7: [(80, 15, 15), (180, 30, 30), (255, 69, 69), (255, 140, 140)],     # Red
    }

    multi_colors = {
        8: (88, 206, 255), 9: (93, 224, 191), 10: (203, 172, 255), 11: (255, 190, 112),
        12: (108, 219, 147), 13: (96, 197, 255), 14: (255, 183, 106), 15: (111, 217, 186),
    }

    total = 1 + len(solid_ramps) * steps + len(multi_colors) * steps
    print(f'Generating {total} arc PNGs at {SIZE}x{SIZE}, {steps} steps...')

    count = 0
    with ZipFile(str(out_path), 'w', ZIP_DEFLATED) as zf:
        # step 0 — empty track (shared)
        img = render_arc(SIZE, 0.0, [(128, 128, 128)] * 4)
        buf = BytesIO()
        img.save(buf, format='PNG', optimize=True)
        zf.writestr(ZipInfo(f'{base_id}.png'), buf.getvalue(), ZIP_DEFLATED)
        count += 1

        # solid colors (palettes 0-7)
        for palette, color_ramp in solid_ramps.items():
            for step in range(1, steps + 1):
                frac = step / steps
                img = render_arc(SIZE, frac, color_ramp)
                buf = BytesIO()
                img.save(buf, format='PNG', optimize=True)
                img_id = base_id + palette * steps + step
                zf.writestr(ZipInfo(f'{img_id}.png'), buf.getvalue(), ZIP_DEFLATED)
                count += 1
                if count % 100 == 0:
                    print(f'  {count}/{total} ...', flush=True)

        # multicolor per-gauge (palettes 8-15)
        for palette, accent in multi_colors.items():
            dark = tuple(max(5, int(c * 0.15)) for c in accent)
            mid = tuple(max(10, int(c * 0.5)) for c in accent)
            bright = tuple(min(255, int(c * 1.2 + 50)) for c in accent)
            mc_ramp = [dark, mid, accent, bright]
            for step in range(1, steps + 1):
                frac = step / steps
                img = render_arc(SIZE, frac, mc_ramp)
                buf = BytesIO()
                img.save(buf, format='PNG', optimize=True)
                img_id = base_id + palette * steps + step
                zf.writestr(ZipInfo(f'{img_id}.png'), buf.getvalue(), ZIP_DEFLATED)
                count += 1
                if count % 100 == 0:
                    print(f'  {count}/{total} ...', flush=True)

        # Background (56300)
        bg = Image.new('RGBA', (1172, 400), (8, 10, 16, 255))
        buf = BytesIO()
        bg.save(buf, format='PNG', optimize=True)
        zf.writestr(ZipInfo('56300.png'), buf.getvalue(), ZIP_DEFLATED)

        # Ethanol empty (56100)
        eth = Image.new('RGBA', (40, 250), (0, 0, 0, 0))
        buf = BytesIO()
        eth.save(buf, format='PNG', optimize=True)
        zf.writestr(ZipInfo('56100.png'), buf.getvalue(), ZIP_DEFLATED)

    print(f'Done: {count} PNGs → {out_path} ({out_path.stat().st_size // 1024 // 1024} MB)')


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Generate tiered BoostDeck assets')
    parser.add_argument('--tier', choices=['1', '2', '3', 'all'], default='all')
    args = parser.parse_args()

    tiers = {
        '1': (32, 55000, 'BoostDeck_Glass_T1_32step.zip'),
        '2': (64, 60000, 'BoostDeck_Glass_T2_64step.zip'),
        '3': (256, 60000, 'BoostDeck_Glass_T3_256step.zip'),
    }

    to_build = tiers.keys() if args.tier == 'all' else [args.tier]

    for tier in to_build:
        steps, base_id, filename = tiers[tier]
        out_path = OUT / filename
        print(f'\n=== Tier {tier}: {steps} steps, base ID {base_id} ===')
        build_zip_manual(out_path, steps, base_id, {}, {})


if __name__ == '__main__':
    main()
