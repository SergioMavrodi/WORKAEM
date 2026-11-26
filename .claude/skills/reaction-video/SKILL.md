---
name: reaction-video
description: Make a viral faceless REACTION video (YouTube long-form 16:9 or Shorts 9:16) to someone's clip or compilation, e.g. "In This Town" Roblox story compilations. Claude watches the source through frame sheets + a Whisper transcript, writes the reactor commentary (pause-and-react freezes with punch zooms, voice-over quips, a cold-open hook), voices it with local Piper TTS, animates cartoon reactor avatars that lip-flap to their own voice, burns in pop captions, adds SFX, masters to -14 LUFS, and makes a clickbait thumbnail + title/description. It can also learn a specific reactor's delivery (catchphrases, pacing, energy) from a reference reaction video and write in that style. Use when the user asks for a reaction video, "react to this video", a reaction in the style of some channel/streamer, or a commentary/react compilation. Runs locally on Linux or macOS with ffmpeg; no API keys.
---

# reaction-video

Source clip in, finished reaction MP4 out. Everything is local and free: ffmpeg, Piper (TTS),
faster-whisper (transcript), Pillow. The creative part (what to say, when to pause) is yours.

Scripts live in `scripts/` next to this file. Below, `$S` = this skill's directory.

## 0. Setup (once per machine)

```bash
bash $S/scripts/setup.sh        # add "ru" for Russian voices
```
Needs ffmpeg. Voices go to `~/.cache/reaction-video/voices` (en_US-ryan-high, en_US-amy-medium,
en_US-joe-medium; ru_RU-dmitri/irina with `ru`).

## 1. Project folder

One folder per reaction, at the repo root:
```
reactions/<slug>/
  input/source.mp4        the video being reacted to
  style_ref/ref.mp4       optional: a reaction video whose delivery to copy
  avatars/                reactor PNGs  (<id>_idle.png, <id>_talk.png, <id>_shock.png)
  reaction.json           the script (you write it)
  work/                   sheets, transcript, cache (git-ignored)
  out/                    reaction.mp4, thumb.jpg, post.md
```

**Getting the source.** Ask the user for the file. Downloading from YouTube often fails from cloud
machines ("Sign in to confirm you're not a bot"). If that happens, do not try to get around it:
ask the user to upload the MP4 (or run `yt-dlp -f "bv*[height<=1080]+ba/b" -o input/source.mp4 URL`
on their own computer). Remind them once: a reaction has to add real commentary (transformative),
and they should credit the original creator; reuploading with little commentary gets copyright strikes.

## 2. Style: learn the reactor's delivery (when the user names a reference)

When the user says "copy how X reacts / his delivery / speech style":
1. Get the reference reaction video into `style_ref/ref.mp4` (same download rules as above).
2. `python3 $S/scripts/inspect_source.py style_ref/ref.mp4 work/style --every 5 --whisper small`
3. `python3 $S/scripts/style_stats.py work/style/transcript.json`
4. Read `work/style/transcript.txt` in full and several contact sheets. The transcript mixes the reactor's
   voice with the original video's. Separate them by content, then fill
   `$S/reference/styles/_template.md` → save as `$S/reference/styles/<reactor>.md`.
   Copy the *delivery* (rhythm, energy, how bits are built, recurring phrases, how often he pauses),
   never long verbatim passages, and do not imitate his real voice. Piper voices are generic anyway.
5. If there is no reference, use `reference/styles/duo-hype.md` (two reactors) or
   `reference/styles/solo-streamer.md` (one reactor).

## 3. Watch the source

```bash
python3 $S/scripts/inspect_source.py input/source.mp4 work --every 3 --whisper small --lang en
```
Read **every** `work/sheets/sheet_*.jpg` (each tile has its source timestamp) and all of
`work/transcript.txt`. Write a beat list before you write any jokes: for each story in the
compilation, give the setup, the twist and the most absurd moment, with timestamps.

## 4. Reactors

- Default: `python3 $S/scripts/make_avatars.py avatars --preset duo`, which gives max (left) and zoe (right).
  Other looks: `--id leo --hairstyle bowl --acc cap --hair "#3a2a20" --hoodie "#e63946"`.
- If the user has their own PNGs (a PNGtuber or a channel mascot), use those. Name them `<id>_idle/_talk/_shock.png`.
- Solo streamer style: one reactor, `"size": 0.5`, `"side": "right"`.

## 5. Write reaction.json

Schema: `reference/schema.md`. Craft rules: `reference/viral-format.md` (read it every time).
Key points:
- **Hook first** (`hook`): 2-4 s of the craziest moment + a title, before the video starts.
- **React every 15-40 s.** Mix `pause` beats (freeze + zoom + 1-3 lines, back-and-forth between reactors)
  with short `over` quips (≤ 6 words) laid over quieter moments, never over important dialogue.
- **Put the pause right after the twist frame**, not before it. Aim `focus` at the face or object that's funny.
- Lines are short and spoken: 3-14 words, contractions, slang that fits the style profile. Use `tts` for
  spelling fixes ("bruh" → "bruhh", "Roblox" stays).
- `face: "shock"` + `sfx: "boom"` for jaw-drop moments. Use them rarely, or they stop working.
- `cuts` for dead air, slow intros, repeated outros of the original.
- Total pause time ≈ 20-35% of the output length.

## 6. Build, check, iterate

```bash
python3 $S/scripts/build.py reactions/<slug>/reaction.json --preview   # half-res, fast
python3 $S/scripts/build.py reactions/<slug>/reaction.json             # final 1080p
```
After the preview, extract frames at a few line times (`out/reaction_preview_lines.txt` lists them),
for example `ffmpeg -ss 12.5 -i out/reaction_preview.mp4 -frames:v 1 f.jpg`, then look at them. Check that
captions are readable, the avatars don't cover the important part of the frame (otherwise set `video_scale: 0.86`),
and the zoom focus is right. The build prints warnings for overlapping lines. Fix those.

## 7. Package

```bash
python3 $S/scripts/thumbnail.py input/source.mp4 out/thumb.jpg --t <best frame> \
  --text "She Likes *HIM?!*" --top "In This Town" --right avatars/max_shock.png --arrow 0.5,0.4
```
Write `out/post.md` with 3 title options (pattern: `<SERIES> Roblox Compilation But <escalation>... | REACTION`),
a description that credits the original creator by channel name, chapters from `out/reaction_lines.txt`,
and 10-15 tags. Send the user the MP4, the thumbnail and post.md.
