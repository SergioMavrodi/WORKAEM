#!/usr/bin/env python3
"""Build a faceless reaction video from a source clip and a reaction script.

usage: build.py path/to/reaction.json [--preview] [--keep]

  --preview   fast low-res render (960px wide, ultrafast) to check timing
  --keep      keep the intermediate files in <project>/work/build

Pipeline
  1. TTS every reactor line with Piper (cached by text+voice).
  2. Pass 1: cut the source into play / freeze (pause + punch zoom) / hook segments,
     all normalised to the same size, fps and audio format, then concat -> base.mp4.
     Every line gets an absolute time on the OUTPUT timeline.
  3. Audio: source audio ducked under every reactor line, + voices + SFX (numpy mix).
  4. Avatar layers: per reactor, a transparent clip where the mouth opens with the
     loudness of its own voice and the avatar bounces while talking.
  5. Pass 2: base + avatar layers + pop-captions (ASS) + mix, loudness -14 LUFS.

Schema of reaction.json: see ../reference/schema.md
"""
import argparse, hashlib, json, math, os, re, shutil, subprocess, sys, wave

import numpy as np
from PIL import Image

SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONTS = os.path.join(SKILL, "assets", "fonts")
SR = 48000


def run(cmd):
    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if r.returncode:
        sys.stderr.write(" ".join(cmd) + "\n" + r.stderr[-3000:])
        raise SystemExit(f"ffmpeg failed ({cmd[0]})")
    return r.stdout


def probe(path, full=False):
    d = json.loads(run(["ffprobe", "-v", "error", "-print_format", "json",
                        "-show_format", "-show_streams", path]))
    dur, aud = float(d["format"]["duration"]), any(s["codec_type"] == "audio" for s in d["streams"])
    if not full:
        return dur, aud
    v = next(s for s in d["streams"] if s["codec_type"] == "video")
    return dur, aud, int(v["width"]) / int(v["height"])


# ---------------------------------------------------------------- audio helpers
def read_wav(path):
    with wave.open(path) as w:
        assert w.getframerate() == SR and w.getsampwidth() == 2, path
        a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
        return a.reshape(-1, w.getnchannels()).mean(axis=1) if w.getnchannels() > 1 else a


def write_wav(path, mono_or_stereo):
    a = np.clip(mono_or_stereo, -1, 1)
    if a.ndim == 1:
        a = np.stack([a, a], axis=1)
    with wave.open(path, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((a * 32767).astype(np.int16).tobytes())


def to48k(src, dst, extra=None):
    cmd = ["ffmpeg", "-v", "error", "-y", "-i", src]
    if extra:
        cmd += ["-af", extra]
    run(cmd + ["-ar", str(SR), "-ac", "1", "-sample_fmt", "s16", dst])


SFX = {  # synthesised so the skill ships without third-party audio
    "boom": ("aevalsrc='0.95*sin(2*PI*(45+70*exp(-9*t))*t)*exp(-2.6*t)':s=48000:d=1.4", "lowpass=f=300,volume=2.2"),
    "ding": ("aevalsrc='0.5*sin(2*PI*1568*t)*exp(-4*t)+0.3*sin(2*PI*2349*t)*exp(-5*t)':s=48000:d=1.2", None),
    "whoosh": ("anoisesrc=d=0.7:c=pink:r=48000:a=0.9", "bandpass=f=1400:w=1800,afade=t=in:d=0.35,afade=t=out:st=0.35:d=0.35"),
    "pop": ("aevalsrc='0.7*sin(2*PI*(900-600*t*8)*t)*exp(-30*t)':s=48000:d=0.25", None),
    "riser": ("aevalsrc='0.4*sin(2*PI*(200+900*t*t)*t)*min(1,t)':s=48000:d=1.5", "afade=t=out:st=1.3:d=0.2"),
}


def sfx_path(name, cache, user_dir):
    for d in (user_dir, os.path.join(SKILL, "assets", "sfx")):
        if d:
            for ext in (".wav", ".mp3", ".ogg"):
                p = os.path.join(d, name + ext)
                if os.path.exists(p):
                    out = os.path.join(cache, f"sfx_user_{name}.wav")
                    if not os.path.exists(out):
                        to48k(p, out)
                    return out
    if name not in SFX:
        raise SystemExit(f"unknown sfx '{name}' (built-in: {', '.join(SFX)}; or drop {name}.wav in sfx_dir)")
    out = os.path.join(cache, f"sfx_{name}.wav")
    if not os.path.exists(out):
        src, af = SFX[name]
        cmd = ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", src]
        if af:
            cmd += ["-af", af]
        run(cmd + ["-ar", str(SR), "-ac", "1", "-sample_fmt", "s16", out])
    return out


# ---------------------------------------------------------------- TTS
class TTS:
    def __init__(self, voices_dir, cache):
        self.dir, self.cache, self.loaded = voices_dir, cache, {}

    def say(self, text, voice, length_scale=1.0, volume=1.0):
        key = hashlib.sha1(f"{voice}|{length_scale}|{text}".encode()).hexdigest()[:16]
        out = os.path.join(self.cache, f"tts_{key}.wav")
        if os.path.exists(out):
            return out
        from piper import PiperVoice, SynthesisConfig
        if voice not in self.loaded:
            model = voice if voice.endswith(".onnx") else os.path.join(self.dir, voice + ".onnx")
            if not os.path.exists(model):
                raise SystemExit(f"voice model not found: {model} (run scripts/setup.sh)")
            self.loaded[voice] = PiperVoice.load(model)
        raw = out + ".raw.wav"
        with wave.open(raw, "wb") as w:
            self.loaded[voice].synthesize_wav(text, w, syn_config=SynthesisConfig(length_scale=length_scale, volume=volume))
        # trim leading/trailing silence so lines snap together, light compression for presence
        to48k(raw, out, "silenceremove=start_periods=1:start_threshold=-45dB,areverse,"
                        "silenceremove=start_periods=1:start_threshold=-45dB,areverse,"
                        "acompressor=threshold=-18dB:ratio=3:attack=5:release=80,volume=1.4")
        os.remove(raw)
        return out


# ---------------------------------------------------------------- video segments
def frame_filter(W, H, box, fps, inp="[0:v]", out="[v]", extra="", src_aspect=None):
    """source -> WxH. If the source already fills the frame: plain scale. Otherwise a blurred
    fill background (blurred at 1/4 res for speed) + the source fitted, scaled by `box`."""
    fpsf = f",fps={fps}" if fps else ""
    if box >= 0.999 and src_aspect and abs(src_aspect - W / H) < 0.02:
        return f"{inp}scale={W}:{H},setsar=1{fpsf}{extra},format=yuv420p{out}"
    bw, bh = int(W * box) // 2 * 2, int(H * box) // 2 * 2
    y = 0 if box < 1 else "(H-h)/2"
    return (f"{inp}split[a][b];"
            f"[a]scale={W // 4}:{H // 4}:force_original_aspect_ratio=increase,crop={W // 4}:{H // 4},"
            f"boxblur=8:2,eq=brightness=-0.12,scale={W}:{H}[bg];"
            f"[b]scale={bw}:{bh}:force_original_aspect_ratio=decrease[fg];"
            f"[bg][fg]overlay=(W-w)/2:{y},setsar=1{fpsf}{extra},format=yuv420p{out}")


def enc(preview):
    return ["-c:v", "libx264", "-preset", "ultrafast" if preview else "veryfast", "-crf", "20",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-ar", str(SR), "-ac", "2"]


def seg_play(src, a, b, out, W, H, box, fps, has_audio, preview, aspect):
    cmd = ["ffmpeg", "-v", "error", "-y", "-ss", f"{a:.3f}", "-t", f"{b - a:.3f}", "-i", src]
    if not has_audio:
        cmd += ["-f", "lavfi", "-t", f"{b - a:.3f}", "-i", f"anullsrc=r={SR}:cl=stereo"]
    cmd += ["-filter_complex", frame_filter(W, H, box, fps, src_aspect=aspect),
            "-map", "[v]", "-map", "0:a" if has_audio else "1:a",
            "-t", f"{b - a:.3f}"] + enc(preview) + [out]
    run(cmd)


def seg_freeze(src, t, dur, out, W, H, box, fps, zoom, focus, preview, aspect):
    """Pause: grab one frame, compose it ONCE, then punch-zoom into `focus` and hold."""
    png, comp = out + ".png", out + ".comp.png"
    run(["ffmpeg", "-v", "error", "-y", "-ss", f"{max(0, t):.3f}", "-i", src, "-frames:v", "1", "-update", "1", png])
    run(["ffmpeg", "-v", "error", "-y", "-i", png, "-filter_complex",
         frame_filter(W, H, box, None, extra=",vignette=PI/5", src_aspect=aspect).replace(",format=yuv420p", ""),
         "-map", "[v]", "-frames:v", "1", "-update", "1", comp])
    n = max(1, int(0.22 * fps))   # punch-in over ~0.22s, then hold
    fx, fy = focus
    frames = max(1, int(round(dur * fps)))
    if zoom and zoom > 1.001:
        vf = (f"scale={W * 2}:{H * 2},zoompan=z='if(lte(on,{n}),1+{zoom - 1}*on/{n},{zoom})':"
              f"x='(iw-iw/zoom)*{fx}':y='(ih-ih/zoom)*{fy}':d={frames}:s={W}x{H}:fps={fps},format=yuv420p")
        cmd = ["ffmpeg", "-v", "error", "-y", "-i", comp]
    else:
        vf = f"fps={fps},format=yuv420p"
        cmd = ["ffmpeg", "-v", "error", "-y", "-loop", "1", "-framerate", str(fps), "-i", comp]
    cmd += ["-f", "lavfi", "-t", f"{dur:.3f}", "-i", f"anullsrc=r={SR}:cl=stereo",
            "-vf", vf, "-map", "0:v", "-map", "1:a", "-frames:v", str(frames), "-t", f"{dur:.3f}"] + enc(preview) + [out]
    run(cmd)
    os.remove(png); os.remove(comp)


# ---------------------------------------------------------------- captions
def ass_time(t):
    t = max(0, t)
    return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"


def ass_color(hexs):
    h = hexs.lstrip("#")
    return f"&H00{h[4:6]}{h[2:4]}{h[0:2]}".upper()


def chunk_words(text, max_words=3, max_chars=16):
    words, chunks, cur = text.split(), [], []
    for w in words:
        if cur and (len(cur) >= max_words or len(" ".join(cur + [w])) > max_chars):
            chunks.append(cur); cur = []
        cur.append(w)
        if re.search(r"[.!?…]$", w):
            chunks.append(cur); cur = []
    if cur:
        chunks.append(cur)
    return [" ".join(c) for c in chunks]


def build_ass(lines, titles, W, H, font, fontsize, path):
    fs = fontsize or int(H * 0.085)
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,{font},{fs},&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000,0,0,0,0,100,100,1,0,1,{max(4, fs // 11)},{max(2, fs // 22)},2,{int(W * 0.22)},{int(W * 0.22)},{int(H * 0.07)},1
Style: Title,{font},{int(fs * 1.35)},&H0000E1FF,&H00FFFFFF,&H00000000,&H96000000,0,0,0,0,100,100,2,0,1,{max(6, fs // 8)},{max(3, fs // 16)},8,60,60,{int(H * 0.06)},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    ev = []
    pop = r"{\fscx70\fscy70\t(0,90,\fscx112\fscy112)\t(90,160,\fscx100\fscy100)}"
    for ln in lines:
        chunks = chunk_words(ln["caption"].upper())
        weights = [len(c) + 3 for c in chunks]
        total, t = sum(weights), ln["start"]
        for c, wgt in zip(chunks, weights):
            d = ln["dur"] * wgt / total
            col = r"{\3c" + ass_color(ln["color"]) + "}" if ln.get("color") else ""
            ev.append(f"Dialogue: 1,{ass_time(t)},{ass_time(t + d)},Cap,,0,0,0,,{pop}{col}{c}")
            t += d
    for ti in titles:
        txt = ti["text"].upper().replace("\n", r"\N")
        ev.append(f"Dialogue: 2,{ass_time(ti['start'])},{ass_time(ti['end'])},Title,,0,0,0,,"
                  r"{\fad(120,120)\fscx60\fscy60\t(0,140,\fscx105\fscy105)\t(140,220,\fscx100\fscy100)}" + txt)
    open(path, "w", encoding="utf-8").write(head + "\n".join(ev) + "\n")


# ---------------------------------------------------------------- avatars
def avatar_layer(r, lines, total, fps, size, path, preview):
    """Transparent clip: idle / mouth-open from voice loudness / shock, bounce while talking."""
    base = r["avatar"]
    imgs = {}
    for face in ("idle", "talk", "shock"):
        p = f"{base}_{face}.png"
        if not os.path.exists(p):
            p = f"{base}_talk.png" if face == "shock" else p
        imgs[face] = Image.open(p).convert("RGBA").resize((size, size), Image.LANCZOS)
    if r.get("side", "left") == "right" and r.get("mirror", True):
        imgs = {k: v.transpose(Image.FLIP_LEFT_RIGHT) for k, v in imgs.items()}
    BOUNCE = max(6, size // 22)
    LH = size + BOUNCE
    frames = {}

    def frame(face, dy):
        k = (face, dy)
        if k not in frames:
            c = Image.new("RGBA", (size, LH), (0, 0, 0, 0))
            c.alpha_composite(imgs[face], (0, BOUNCE - dy))
            frames[k] = c.tobytes()
        return frames[k]

    n = int(math.ceil(total * fps))
    state = np.zeros(n, dtype=np.int8)      # 0 idle, 1 talk-closed, 2 talk-open, 3 shock
    talking = np.zeros(n, dtype=bool)
    for ln in lines:
        a = read_wav(ln["wav"])
        hop = SR // fps
        f0 = int(round(ln["start"] * fps))
        for i in range(0, len(a) // hop + 1):
            fi = f0 + i
            if fi >= n:
                break
            rms = float(np.sqrt(np.mean(a[i * hop:(i + 1) * hop] ** 2))) if i * hop < len(a) else 0
            talking[fi] = True
            state[fi] = 3 if ln["face"] == "shock" else (2 if rms > 0.045 else 1)
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgba",
                          "-s", f"{size}x{LH}", "-r", str(fps), "-i", "-", "-c:v", "qtrle", path],
                         stdin=subprocess.PIPE)
    names = {0: "idle", 1: "idle", 2: "talk", 3: "shock"}
    for fi in range(n):
        dy = int(round(BOUNCE * abs(math.sin(fi * 0.55)))) if talking[fi] else 0
        p.stdin.write(frame(names[int(state[fi])], dy))
    p.stdin.close()
    if p.wait():
        raise SystemExit("avatar layer encode failed")
    return LH


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("config")
    ap.add_argument("--preview", action="store_true")
    ap.add_argument("--keep", action="store_true")
    args = ap.parse_args()

    cfg_path = os.path.abspath(args.config)
    root = os.path.dirname(cfg_path)
    cfg = json.load(open(cfg_path))
    P = lambda p: p if os.path.isabs(p) else os.path.join(root, p)

    src = P(cfg["source"])
    W, H = cfg.get("size", [1920, 1080])
    fps = int(cfg.get("fps", 30))
    if args.preview:
        W, H = W // 2 // 2 * 2, H // 2 // 2 * 2
    box = float(cfg.get("video_scale", 1.0))
    duck = float(cfg.get("duck", 0.22))
    src_vol = float(cfg.get("source_volume", 1.0))
    gap, lead, tail = cfg.get("line_gap", 0.12), cfg.get("pause_lead", 0.3), cfg.get("pause_tail", 0.25)
    reactors = cfg["reactors"]
    for rid, r in reactors.items():
        r["avatar"] = P(r["avatar"])

    build = os.path.join(root, "work", "build")
    cache = os.path.join(root, "work", "cache")
    os.makedirs(build, exist_ok=True); os.makedirs(cache, exist_ok=True)
    out_path = P(cfg.get("output", "out/reaction.mp4"))
    if args.preview:
        out_path = re.sub(r"\.mp4$", "", out_path) + "_preview.mp4"
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    dur, has_audio, aspect = probe(src, full=True)
    tts = TTS(os.path.expanduser(cfg.get("voices_dir", "~/.cache/reaction-video/voices")), cache)

    # 1. TTS
    events = sorted(cfg.get("events", []), key=lambda e: e["t"])
    for e in events:
        r = reactors[e["speaker"]]
        e["wav"] = tts.say(e.get("tts", e["text"]), e.get("voice", r["voice"]),
                           e.get("length_scale", r.get("length_scale", 1.0)), r.get("volume", 1.0))
        e["dur"] = len(read_wav(e["wav"])) / SR
    print(f"tts: {len(events)} lines, {sum(e['dur'] for e in events):.1f}s of voice")

    # 2. timeline
    cuts = sorted(cfg.get("cuts", []))
    kept, cur = [], 0.0
    for a, b in cuts:
        if a > cur:
            kept.append((cur, min(a, dur)))
        cur = max(cur, b)
    if cur < dur:
        kept.append((cur, dur))
    in_cut = lambda t: any(a <= t < b for a, b in cuts)
    for e in events:
        if in_cut(e["t"]):
            print(f"WARNING: event at {e['t']} is inside a cut, dropped: {e['text']}")
    events = [e for e in events if not in_cut(e["t"])]

    pauses = {}
    for e in events:
        if e.get("mode", "pause") == "pause":
            pauses.setdefault(round(e["t"], 2), []).append(e)

    segs, placed, titles, sfx_marks = [], [], [], []
    t_out = 0.0

    def place(e, start):
        r = reactors[e["speaker"]]
        placed.append(dict(start=start, dur=e["dur"], wav=e["wav"], speaker=e["speaker"],
                           caption=e.get("caption", e["text"]), color=r.get("color"),
                           face=e.get("face", "talk")))
        if e.get("sfx"):
            sfx_marks.append((start - 0.05, e["sfx"]))

    hook = cfg.get("hook")
    if hook:
        hd = hook["to"] - hook["from"]
        segs.append(("play", hook["from"], hook["to"]))
        titles.append(dict(start=0.0, end=hd, text=hook.get("title", "WAIT FOR IT...")))
        sfx_marks.append((max(0, hd - 0.35), "whoosh"))
        t_out += hd

    for a, b in kept:
        cuts_in = sorted(t for t in pauses if a <= t < b)
        pos = a
        for pt in cuts_in + [b]:
            if pt - pos > 0.04:
                for e in events:
                    if e.get("mode") == "over" and pos <= e["t"] < pt:
                        place(e, t_out + e["t"] - pos)
                segs.append(("play", pos, pt))
                t_out += pt - pos
                pos = pt
            if pt in pauses:
                grp = pauses[pt]
                fdur = lead + sum(e["dur"] for e in grp) + gap * (len(grp) - 1) + tail
                ts = t_out + lead
                for e in grp:
                    place(e, ts)
                    ts += e["dur"] + gap
                z = max((e.get("zoom", cfg.get("default_zoom", 1.2)) for e in grp), default=1.2)
                focus = next((e["focus"] for e in grp if e.get("focus")), [0.5, 0.5])
                segs.append(("freeze", min(pt, dur - 0.1), fdur, z, focus))
                t_out += fdur
    total = t_out
    print(f"timeline: {len(segs)} segments, {len(pauses)} pauses, output {total:.1f}s (source {dur:.1f}s)")

    # overlap check
    pl = sorted(placed, key=lambda x: x["start"])
    for x, y in zip(pl, pl[1:]):
        if x["start"] + x["dur"] > y["start"] + 0.05:
            print(f"WARNING: lines overlap at {y['start']:.1f}s: '{x['caption'][:30]}' / '{y['caption'][:30]}'")

    # 3. render segments + concat
    seg_files = []
    for i, s in enumerate(segs):
        f = os.path.join(build, f"seg_{i:04d}.mp4")
        if s[0] == "play":
            seg_play(src, s[1], s[2], f, W, H, box, fps, has_audio, args.preview, aspect)
        else:
            seg_freeze(src, s[1], s[2], f, W, H, box, fps, s[3], s[4], args.preview, aspect)
        seg_files.append(f)
        print(f"\rsegments {i + 1}/{len(segs)}", end="", flush=True)
    print()
    lst = os.path.join(build, "concat.txt")
    open(lst, "w").write("".join(f"file '{f}'\n" for f in seg_files))
    base = os.path.join(build, "base.mp4")
    run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", base])
    total, _ = probe(base)

    # 4. audio mix
    base_wav = os.path.join(build, "base.wav")
    run(["ffmpeg", "-v", "error", "-y", "-i", base, "-vn", "-ar", str(SR), "-ac", "2", "-sample_fmt", "s16", base_wav])
    with wave.open(base_wav) as w:
        src_a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32).reshape(-1, 2) / 32768
    N = int(total * SR)
    src_a = np.pad(src_a, ((0, max(0, N - len(src_a))), (0, 0)))[:N] * src_vol
    env = np.ones(N, dtype=np.float32)
    voice = np.zeros(N, dtype=np.float32)
    ramp = int(0.12 * SR)
    for ln in placed:
        a = read_wav(ln["wav"])
        s = int(ln["start"] * SR)
        e = min(N, s + len(a))
        if s >= N:
            continue
        voice[s:e] += a[:e - s]
        lo, hi = max(0, s - ramp), min(N, e + ramp)
        seg = np.full(hi - lo, duck, dtype=np.float32)
        r1 = s - lo
        seg[:r1] = np.linspace(1, duck, r1) if r1 else seg[:r1]
        r2 = hi - e
        seg[len(seg) - r2:] = np.linspace(duck, 1, r2) if r2 else seg[len(seg) - r2:]
        env[lo:hi] = np.minimum(env[lo:hi], seg)
    for t, name in sfx_marks:
        a = read_wav(sfx_path(name, cache, P(cfg["sfx_dir"]) if cfg.get("sfx_dir") else None))
        s = max(0, int(t * SR)); e = min(N, s + len(a))
        voice[s:e] += a[:e - s] * float(cfg.get("sfx_volume", 0.6))
    mix = src_a * env[:, None] + voice[:, None]
    peak = float(np.max(np.abs(mix))) or 1
    if peak > 0.99:
        mix /= peak / 0.98
    mix_wav = os.path.join(build, "mix.wav")
    write_wav(mix_wav, mix)

    # 5. avatar layers
    margin = int(W * 0.012)
    layers = []
    for rid, r in reactors.items():
        size = int(H * float(r.get("size", cfg.get("avatar_size", 0.36)))) // 2 * 2
        f = os.path.join(build, f"avatar_{rid}.mov")
        LH = avatar_layer(r, [l for l in placed if l["speaker"] == rid], total, fps, size, f, args.preview)
        x = margin if r.get("side", "left") == "left" else W - size - margin
        layers.append((f, x, H - LH + int(size * 0.04)))

    # 6. captions + final
    font = cfg.get("caption_font")
    if not font:
        cyr = any(re.search("[А-Яа-яЁё]", l["caption"]) for l in placed) or \
              any(re.search("[А-Яа-яЁё]", t["text"]) for t in titles)
        font = "Inter Black" if cyr else "Luckiest Guy"
    ass = os.path.join(build, "captions.ass")
    build_ass(placed, titles, W, H, font, cfg.get("caption_size"), ass)

    inputs = ["-i", base]
    fc, last = [], "[0:v]"
    for i, (f, x, y) in enumerate(layers, start=1):
        inputs += ["-i", f]
        fc.append(f"{last}[{i}:v]overlay={x}:{y}:eof_action=pass[v{i}]")
        last = f"[v{i}]"
    ai = len(layers) + 1
    inputs += ["-i", mix_wav]
    esc = lambda p: p.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
    fc.append(f"{last}subtitles='{esc(ass)}':fontsdir='{esc(FONTS)}'[vout]")
    fc.append(f"[{ai}:a]loudnorm=I=-14:TP=-1.5:LRA=11,aresample={SR}[aout]")
    run(["ffmpeg", "-v", "error", "-y"] + inputs + ["-filter_complex", ";".join(fc),
         "-map", "[vout]", "-map", "[aout]", "-t", f"{total:.3f}",
         "-c:v", "libx264", "-preset", "ultrafast" if args.preview else "medium", "-crf", "20",
         "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out_path])

    # chapters / timestamps for the description
    marks = [f"{int(l['start'] // 60)}:{int(l['start'] % 60):02d} {reactors[l['speaker']].get('name', l['speaker'])}: {l['caption']}"
             for l in placed]
    open(re.sub(r"\.mp4$", "", out_path) + "_lines.txt", "w").write("\n".join(marks) + "\n")
    if not args.keep:
        shutil.rmtree(build, ignore_errors=True)
    print(f"done: {out_path} ({total:.1f}s)")


if __name__ == "__main__":
    main()
