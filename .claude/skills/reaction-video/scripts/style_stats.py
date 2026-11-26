#!/usr/bin/env python3
"""Speech-style numbers from a reference reaction video's transcript.json (from inspect_source.py).

usage: style_stats.py WORKDIR/transcript.json [--top 40]

Prints: words per minute, utterance length, how often speech starts (reaction density),
longest silences, and the most repeated 1-3 word phrases (catchphrases / fillers).
The transcript mixes the reactor and the original video's voices; use the numbers together
with reading transcript.txt to separate them when writing the style profile.
"""
import argparse, collections, json, re

STOP = set("the a an and or to of in on it is i you he she we they that this was for with be at as".split())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("transcript")
    ap.add_argument("--top", type=int, default=40)
    a = ap.parse_args()
    segs = json.load(open(a.transcript))["segments"]
    if not segs:
        print("empty transcript"); return
    words = [w["w"] for s in segs for w in s["words"]] or " ".join(s["text"] for s in segs).split()
    span = segs[-1]["end"] - segs[0]["start"]
    talk = sum(s["end"] - s["start"] for s in segs)
    lens = sorted(len(s["text"].split()) for s in segs)
    gaps = sorted(((segs[i + 1]["start"] - segs[i]["end"], segs[i]["end"]) for i in range(len(segs) - 1)), reverse=True)
    text = " ".join(s["text"] for s in segs)
    print(f"duration covered : {span / 60:.1f} min, speech {talk / span * 100:.0f}% of the time")
    print(f"words per minute : {len(words) / (talk / 60):.0f} (while talking), {len(words) / (span / 60):.0f} overall")
    print(f"utterances       : {len(segs)} ({len(segs) / (span / 60):.1f}/min), "
          f"median {lens[len(lens) // 2]} words, p90 {lens[int(len(lens) * 0.9)]} words")
    print(f"exclamations     : {text.count('!')}, questions: {text.count('?')}, "
          f"ALL-CAPS words: {sum(1 for w in words if len(w) > 2 and w.isupper())}")
    print("longest silences : " + ", ".join(f"{g:.1f}s @ {int(t // 60)}:{int(t % 60):02d}" for g, t in gaps[:8]))
    toks = [re.sub(r"[^\w']", "", w.lower()) for w in words]
    toks = [t for t in toks if t]
    for n in (1, 2, 3):
        c = collections.Counter(tuple(toks[i:i + n]) for i in range(len(toks) - n + 1))
        items = [(" ".join(k), v) for k, v in c.most_common(a.top * 3)
                 if not (n == 1 and k[0] in STOP) and v > 1][:a.top if n > 1 else a.top // 2]
        print(f"\ntop {n}-grams: " + ", ".join(f"{k} ×{v}" for k, v in items))
    openers = collections.Counter(" ".join(s["text"].split()[:2]).lower().strip(",.!?") for s in segs)
    print("\nhow lines start : " + ", ".join(f"'{k}' ×{v}" for k, v in openers.most_common(20) if v > 1))


if __name__ == "__main__":
    main()
