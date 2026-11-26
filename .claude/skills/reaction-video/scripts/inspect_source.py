#!/usr/bin/env python3
"""Let Claude "watch" a source video: contact sheets + timestamped transcript.

usage: inspect_source.py SOURCE.mp4 WORKDIR [--every 3] [--whisper small] [--lang en]

Writes
  WORKDIR/sheets/sheet_001.jpg ...   4x3 grids of frames, each stamped with its source time
  WORKDIR/transcript.json            whisper segments with word timings
  WORKDIR/transcript.txt             "[mm:ss.s - mm:ss.s] text" lines
  WORKDIR/info.json                  duration, resolution, fps
"""
import argparse, json, os, subprocess, sys


def probe(path):
    out = subprocess.check_output([
        "ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", path])
    d = json.loads(out)
    v = next(s for s in d["streams"] if s["codec_type"] == "video")
    num, den = (v.get("avg_frame_rate") or "30/1").split("/")
    return {
        "duration": float(d["format"]["duration"]),
        "width": int(v["width"]), "height": int(v["height"]),
        "fps": round(float(num) / float(den or 1), 3),
        "has_audio": any(s["codec_type"] == "audio" for s in d["streams"]),
    }


def fmt(t):
    return f"{int(t // 60):02d}:{t % 60:04.1f}"


def contact_sheets(src, work, every):
    sheets = os.path.join(work, "sheets")
    os.makedirs(sheets, exist_ok=True)
    # each tile: frame every N seconds, 480px wide, time burned in top-left
    vf = (f"fps=1/{every},scale=480:-2,"
          "drawtext=text='%{pts\\:hms}':x=8:y=8:fontsize=26:fontcolor=yellow:"
          "box=1:boxcolor=black@0.7:boxborderw=6,"
          "tile=4x3:padding=6:margin=6")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-vf", vf, "-q:v", "4",
                    os.path.join(sheets, "sheet_%03d.jpg")], check=True)
    n = len([f for f in os.listdir(sheets) if f.endswith(".jpg")])
    print(f"contact sheets: {n} (each covers {12 * every:.0f}s) -> {sheets}")


def transcribe(src, work, model_name, lang):
    from faster_whisper import WhisperModel
    import numpy as np
    # decode with ffmpeg ourselves (avoids PyAV version issues inside faster-whisper)
    pcm = subprocess.check_output(["ffmpeg", "-v", "error", "-i", src, "-vn", "-ac", "1", "-ar", "16000",
                                   "-f", "s16le", "-"])
    audio = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768
    model = WhisperModel(model_name, device="cpu", compute_type="int8")
    segs, info = model.transcribe(audio, language=lang, word_timestamps=True, vad_filter=True)
    out, lines = [], []
    for s in segs:
        out.append({"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip(),
                    "words": [{"w": w.word.strip(), "s": round(w.start, 2), "e": round(w.end, 2)}
                              for w in (s.words or [])]})
        lines.append(f"[{fmt(s.start)} - {fmt(s.end)}] {s.text.strip()}")
    json.dump({"language": info.language, "segments": out},
              open(os.path.join(work, "transcript.json"), "w"), ensure_ascii=False, indent=1)
    open(os.path.join(work, "transcript.txt"), "w").write("\n".join(lines) + "\n")
    print(f"transcript: {len(out)} segments, language={info.language} -> {work}/transcript.txt")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source")
    ap.add_argument("workdir")
    ap.add_argument("--every", type=float, default=3.0, help="seconds between sheet frames")
    ap.add_argument("--whisper", default="small", help="faster-whisper model (tiny/base/small/medium)")
    ap.add_argument("--lang", default=None, help="force language code, e.g. en")
    ap.add_argument("--no-transcript", action="store_true")
    a = ap.parse_args()
    os.makedirs(a.workdir, exist_ok=True)
    info = probe(a.source)
    json.dump(info, open(os.path.join(a.workdir, "info.json"), "w"), indent=1)
    print("source:", json.dumps(info))
    contact_sheets(a.source, a.workdir, a.every)
    if not a.no_transcript:
        if not info["has_audio"]:
            print("no audio stream, skipping transcript")
        else:
            transcribe(a.source, a.workdir, a.whisper, a.lang)


if __name__ == "__main__":
    sys.exit(main())
