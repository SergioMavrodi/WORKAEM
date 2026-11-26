# reaction.json

Paths are relative to the folder that holds reaction.json.

```jsonc
{
  "source": "input/source.mp4",
  "output": "out/reaction.mp4",
  "size": [1920, 1080],            // [1080, 1920] for Shorts (source gets a blurred fill)
  "fps": 30,
  "video_scale": 1.0,              // <1 shrinks the source to the top so avatars don't cover it
  "duck": 0.22,                    // source volume under reactor lines
  "source_volume": 1.0,
  "default_zoom": 1.2,
  "line_gap": 0.12, "pause_lead": 0.3, "pause_tail": 0.25,   // seconds
  "caption_font": "Luckiest Guy",  // auto: Luckiest Guy, or Inter Black for Cyrillic
  "caption_size": null,            // px, default 8.5% of height
  "sfx_dir": "sfx",                // optional: your own <name>.wav files override/extend built-ins
  "sfx_volume": 0.6,
  "voices_dir": "~/.cache/reaction-video/voices",

  "reactors": {
    "max": {
      "name": "Max",
      "voice": "en_US-ryan-high",  // Piper voice name (or a path to .onnx)
      "length_scale": 0.9,         // <1 = faster speech (0.85-0.95 sounds hyped)
      "volume": 1.0,
      "avatar": "avatars/max",     // uses avatars/max_idle.png, _talk.png, _shock.png
      "side": "left",              // left | right
      "size": 0.36,                // avatar height as a fraction of the frame height
      "color": "#2fb8ff",          // caption outline colour for this reactor
      "mirror": true               // flip the avatar when it is on the right
    }
  },

  "hook": { "from": 95.0, "to": 98.5, "title": "THIS GETS CRAZY..." },   // optional cold open
  "cuts": [[0, 3.5], [212, 240]],  // source ranges to drop

  "events": [
    // pause: freeze the frame at t, punch-zoom, play the line(s). Events with the same t
    // form one pause and play in order, so you can write a back-and-forth.
    { "t": 41.2, "speaker": "max", "text": "Wait wait wait. He did WHAT?",
      "mode": "pause", "zoom": 1.35, "focus": [0.45, 0.35], "face": "shock", "sfx": "boom" },
    { "t": 41.2, "speaker": "zoe", "text": "Bro has negative aura." },

    // over: the video keeps playing, the source is ducked under the line
    { "t": 55.0, "speaker": "zoe", "text": "nah he's cooked", "mode": "over" },

    // optional per line: "tts" (spoken text if it differs from the caption), "caption",
    // "voice", "length_scale"
    { "t": 70.0, "speaker": "max", "text": "Bruh.", "tts": "Bruuuh.", "mode": "pause", "zoom": 1.0 }
  ]
}
```

Built-in SFX: `boom`, `ding`, `whoosh`, `pop`, `riser` (synthesised). Drop `<name>.wav` files into
`sfx_dir` for more (vine boom, record scratch, laugh track), with sounds you have the rights to.

`face`: `talk` (default, the mouth moves with the voice) or `shock`.
`focus`: zoom centre, [x, y] in 0..1 of the frame.
