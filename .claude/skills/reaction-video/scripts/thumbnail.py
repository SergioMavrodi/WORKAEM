#!/usr/bin/env python3
"""Clickbait-style YouTube thumbnail: source frame + shocked reactors + huge outlined text.

usage: thumbnail.py SOURCE.mp4 OUT.jpg --t 83.2 --text "HE DID WHAT?!" \
         --left avatars/max_shock.png --right avatars/zoe_shock.png [--top "IN THIS TOWN"] [--arrow 0.55,0.45]
"""
import argparse, os, subprocess, tempfile
from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageFilter

SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W, H = 1280, 720


def font(size, text):
    cyr = any("Ѐ" <= c <= "ӿ" for c in text)
    for p in ([] if cyr else [os.path.join(SKILL, "assets/fonts/LuckiestGuy-Regular.ttf")]) + [
            "/usr/share/fonts/opentype/inter/Inter-Black.otf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def fit_text(d, text, max_w, start):
    s = start
    while s > 30:
        f = font(s, text)
        if d.textlength(text, font=f) <= max_w:
            return f
        s -= 4
    return font(30, text)


def outlined(img, xy, text, f, fill, stroke=10, anchor="mm"):
    d = ImageDraw.Draw(img)
    sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).text((xy[0] + 6, xy[1] + 8), text, font=f, fill=(0, 0, 0, 200), anchor=anchor,
                            stroke_width=stroke, stroke_fill=(0, 0, 0, 200))
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(4)))
    d.text(xy, text, font=f, fill=fill, anchor=anchor, stroke_width=stroke, stroke_fill=(0, 0, 0, 255))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source"); ap.add_argument("out")
    ap.add_argument("--t", type=float, required=True, help="source time of the background frame")
    ap.add_argument("--text", required=True, help="big bottom text, 2-4 words; *word* = red")
    ap.add_argument("--top", default="", help="small banner on top, e.g. series name")
    ap.add_argument("--left"); ap.add_argument("--right")
    ap.add_argument("--arrow", help="x,y (0..1) where a red arrow should point")
    a = ap.parse_args()

    with tempfile.TemporaryDirectory() as td:
        fr = os.path.join(td, "f.png")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(a.t), "-i", a.source, "-frames:v", "1", fr], check=True)
        bg = Image.open(fr).convert("RGB")
    r = max(W / bg.width, H / bg.height)
    bg = bg.resize((int(bg.width * r) + 1, int(bg.height * r) + 1), Image.LANCZOS)
    bg = bg.crop(((bg.width - W) // 2, (bg.height - H) // 2, (bg.width - W) // 2 + W, (bg.height - H) // 2 + H))
    bg = ImageEnhance.Contrast(ImageEnhance.Color(bg).enhance(1.45)).enhance(1.12)
    img = bg.convert("RGBA")

    # darken bottom for text
    grad = Image.new("L", (1, H))
    for y in range(H):
        grad.putpixel((0, y), int(max(0, (y - H * 0.45) / (H * 0.55)) * 190))
    img.alpha_composite(Image.merge("RGBA", [Image.new("L", (W, H), 0)] * 3 + [grad.resize((W, H))]))

    for side, p in (("left", a.left), ("right", a.right)):
        if not p:
            continue
        av = Image.open(p).convert("RGBA")
        s = int(H * 0.78)
        av = av.resize((s, s), Image.LANCZOS)
        if side == "right":
            av = av.transpose(Image.FLIP_LEFT_RIGHT)
        img.alpha_composite(av, (-int(s * 0.12) if side == "left" else W - s + int(s * 0.12), H - s + int(s * 0.08)))

    if a.arrow:
        ax, ay = (float(v) for v in a.arrow.split(","))
        x, y = int(ax * W), int(ay * H)
        d = ImageDraw.Draw(img)
        d.line((x - 170, y + 150, x - 25, y + 25), fill=(0, 0, 0, 255), width=40)
        d.line((x - 170, y + 150, x - 25, y + 25), fill=(255, 40, 40, 255), width=26)
        d.polygon([(x, y), (x - 85, y + 10), (x - 10, y + 85)], fill=(255, 40, 40, 255), outline=(0, 0, 0, 255))

    d = ImageDraw.Draw(img)
    # words wrapped in *stars* are drawn red: "Everyone Gets *Cracked*"
    words, red_on = [], False
    for w in a.text.split():
        starts, ends = w.startswith("*"), w.endswith("*") and len(w) > 1
        words.append((w.strip("*").upper(), red_on or starts))
        red_on = (red_on or starts) and not ends
    plain = " ".join(w for w, _ in words)
    f = fit_text(d, plain, W * 0.92, 150)
    space = d.textlength(" ", font=f)
    x = W / 2 - d.textlength(plain, font=f) / 2
    for w, red in words:
        outlined(img, (x, int(H * 0.84)), w, f, (235, 20, 20, 255) if red else (255, 255, 255, 255),
                 stroke=12, anchor="lm")
        x += d.textlength(w, font=f) + space
    if a.top:
        top = a.top.upper()
        tf = fit_text(d, top, W * 0.6, 70)
        tw = d.textlength(top, font=tf)
        d.rounded_rectangle((W / 2 - tw / 2 - 30, 18, W / 2 + tw / 2 + 30, 18 + tf.size + 34), radius=18,
                            fill=(230, 30, 50, 255), outline=(0, 0, 0, 255), width=6)
        outlined(img, (W // 2, 18 + (tf.size + 34) // 2 + 4), top, tf, (255, 255, 255, 255), stroke=6)
    img.convert("RGB").save(a.out, quality=92)
    print("thumbnail:", a.out)


if __name__ == "__main__":
    main()
