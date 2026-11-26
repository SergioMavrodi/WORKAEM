#!/usr/bin/env python3
"""Draw original cartoon reactor avatars (idle / talk / shock) as sticker PNGs.

usage:
  make_avatars.py OUTDIR --id max --hair "#2fb8ff" --hoodie "#ff4d6d" --hairstyle spiky --acc headphones
  make_avatars.py OUTDIR --preset duo      # two ready-made reactors: max + zoe

Writes OUTDIR/<id>_idle.png, <id>_talk.png, <id>_shock.png (600x600, transparent).
If the user has their own avatar art, skip this and point reaction.json at their PNGs.
"""
import argparse, os
from PIL import Image, ImageDraw, ImageFilter

S = 1200          # draw at 2x, downscale for anti-aliasing
INK = (26, 22, 46, 255)
OUT_W = 14


def hexc(h, a=255):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) + (a,)


def darker(c, k=0.7):
    return tuple(int(v * k) for v in c[:3]) + (255,)


def draw_char(hair, hoodie, skin, hairstyle, acc, face):
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    hair, hoodie, skin = hexc(hair), hexc(hoodie), hexc(skin)

    # long hair goes behind the head
    if hairstyle == "long":
        d.rounded_rectangle((250, 230, 950, 1050), radius=300, fill=hair, outline=INK, width=OUT_W)

    # body / hoodie
    d.ellipse((190, 880, 1010, 1560), fill=hoodie, outline=INK, width=OUT_W)
    d.line((600, 960, 600, 1200), fill=darker(hoodie), width=10)          # zipper
    d.line((520, 950, 500, 1100), fill=(255, 255, 255, 255), width=12)    # strings
    d.line((680, 950, 700, 1100), fill=(255, 255, 255, 255), width=12)

    # head
    d.ellipse((300, 240, 900, 870), fill=skin, outline=INK, width=OUT_W)

    # hair on top
    if hairstyle == "spiky":
        pts = [(290, 520), (300, 330), (360, 250), (330, 140), (450, 200), (500, 90),
               (580, 190), (680, 90), (720, 210), (850, 150), (830, 280), (920, 330), (910, 520),
               (840, 400), (760, 450), (700, 360), (600, 440), (520, 360), (420, 450), (360, 390)]
        d.polygon(pts, fill=hair, outline=INK)
        d.line(pts + [pts[0]], fill=INK, width=OUT_W, joint="curve")
    elif hairstyle == "long":
        d.chord((290, 220, 910, 700), 180, 360, fill=hair, outline=INK, width=OUT_W)
        d.polygon([(330, 470), (420, 330), (520, 470)], fill=hair)
        d.polygon([(560, 450), (680, 320), (740, 450)], fill=hair)
        d.polygon([(760, 460), (850, 360), (880, 500)], fill=hair)
    else:  # bowl / short
        d.chord((285, 210, 915, 690), 180, 360, fill=hair, outline=INK, width=OUT_W)
        d.rectangle((300, 440, 900, 470), fill=hair)

    # accessory
    if acc == "headphones":
        d.arc((250, 160, 950, 860), 180, 360, fill=INK, width=60)
        d.arc((250, 160, 950, 860), 180, 360, fill=darker(hoodie, 0.9), width=40)
        for x0 in (215, 855):
            d.rounded_rectangle((x0, 470, x0 + 130, 700), radius=50, fill=darker(hoodie, 0.9),
                                outline=INK, width=OUT_W)
    elif acc == "bow":
        c = hexc("#ff5fa2")
        d.polygon([(760, 250), (900, 170), (900, 340)], fill=c, outline=INK)
        d.polygon([(760, 250), (640, 160), (650, 330)], fill=c, outline=INK)
        d.ellipse((725, 215, 795, 285), fill=darker(c, 0.85), outline=INK, width=8)
    elif acc == "cap":
        c = darker(hoodie, 0.85)
        d.chord((290, 190, 910, 650), 180, 360, fill=c, outline=INK, width=OUT_W)
        d.rounded_rectangle((250, 400, 700, 460), radius=25, fill=c, outline=INK, width=OUT_W)

    # blush
    blush = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    bd = ImageDraw.Draw(blush)
    for cx in (400, 800):
        bd.ellipse((cx - 60, 640, cx + 60, 700), fill=(255, 110, 140, 110))
    im.alpha_composite(blush)

    # eyes
    big = face == "shock"
    for cx in (470, 730):
        rx, ry = (85, 105) if big else (72, 88)
        d.ellipse((cx - rx, 560 - ry, cx + rx, 560 + ry), fill=(255, 255, 255, 255), outline=INK, width=10)
        pr = 26 if big else 40
        d.ellipse((cx - pr, 570 - pr, cx + pr, 570 + pr), fill=INK)
        d.ellipse((cx - pr // 2 - 6, 570 - pr + 4, cx - pr // 2 + 14, 570 - pr + 24), fill=(255, 255, 255, 255))
        # eyebrows
        if big:   # raised, arched
            d.arc((cx - 75, 390, cx + 75, 470), 200, 340, fill=INK, width=20)
        else:     # relaxed, outer end slightly up
            outer, inner = (cx - 70, 450), (cx + 60, 462)
            if cx > 600:
                outer, inner = (cx + 70, 450), (cx - 60, 462)
            d.line(outer + inner, fill=INK, width=22)

    # mouth
    if face == "idle":
        d.arc((520, 680, 680, 790), 20, 160, fill=INK, width=16)
    elif face == "talk":
        d.rounded_rectangle((515, 690, 685, 810), radius=55, fill=(120, 20, 40, 255), outline=INK, width=12)
        d.ellipse((550, 755, 650, 815), fill=(240, 100, 120, 255))
    else:  # shock
        d.ellipse((540, 700, 660, 840), fill=(120, 20, 40, 255), outline=INK, width=12)
        # sweat drop
        d.polygon([(880, 380), (850, 450), (910, 450)], fill=(140, 210, 255, 255))
        d.ellipse((848, 425, 912, 485), fill=(140, 210, 255, 255), outline=INK, width=6)

    # sticker border: dilate alpha and put white underneath
    alpha = im.split()[3]
    border = alpha.filter(ImageFilter.MaxFilter(41))
    sticker = Image.new("RGBA", (S, S), (255, 255, 255, 0))
    sticker.putalpha(border)
    white = Image.new("RGBA", (S, S), (255, 255, 255, 255))
    base = Image.composite(white, sticker, border)
    base.alpha_composite(im)
    return base.resize((600, 600), Image.LANCZOS)


PRESETS = {
    "max": dict(hair="#2fb8ff", hoodie="#ffb703", skin="#ffd6b0", hairstyle="spiky", acc="headphones"),
    "zoe": dict(hair="#b06cff", hoodie="#3ddc97", skin="#f6c7a0", hairstyle="long", acc="bow"),
    "leo": dict(hair="#3a2a20", hoodie="#e63946", skin="#c98b62", hairstyle="bowl", acc="cap"),
}


def make(outdir, cid, spec):
    os.makedirs(outdir, exist_ok=True)
    for face in ("idle", "talk", "shock"):
        p = os.path.join(outdir, f"{cid}_{face}.png")
        draw_char(face=face, **spec).save(p)
        print("wrote", p)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("outdir")
    ap.add_argument("--preset", choices=["duo", "max", "zoe", "leo"])
    ap.add_argument("--id")
    ap.add_argument("--hair", default="#2fb8ff")
    ap.add_argument("--hoodie", default="#ffb703")
    ap.add_argument("--skin", default="#ffd6b0")
    ap.add_argument("--hairstyle", default="spiky", choices=["spiky", "long", "bowl"])
    ap.add_argument("--acc", default="none", choices=["none", "headphones", "bow", "cap"])
    a = ap.parse_args()
    if a.preset == "duo":
        make(a.outdir, "max", PRESETS["max"])
        make(a.outdir, "zoe", PRESETS["zoe"])
    elif a.preset:
        make(a.outdir, a.preset, PRESETS[a.preset])
    else:
        if not a.id:
            ap.error("--id or --preset required")
        make(a.outdir, a.id, dict(hair=a.hair, hoodie=a.hoodie, skin=a.skin, hairstyle=a.hairstyle, acc=a.acc))


if __name__ == "__main__":
    main()
