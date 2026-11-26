# In This Town: reaction #1

| | |
|---|---|
| Source to react to | "In This Town Roblox Stories Compilation (#1)" by TeamDeam (https://www.youtube.com/watch?v=CB2aoMPP2dU) |
| Format reference | "IN THIS TOWN Roblox Compilation But Things Get CRAZY... \| REACTION" by They All Laughed (https://youtu.be/wlQl8iOEcjo) |
| Delivery / speech style to copy | "In This Town Roblox TikToks Got WORSE \| YXL Salah" (https://youtu.be/9TJxC5rEq_c) |

## Needed before building
- `input/source.mp4`: the TeamDeam compilation.
- `style_ref/ref.mp4`: the YXL Salah reaction, for learning the delivery.

YouTube blocks downloads from the cloud machine (bot check), so upload both files here,
or download them on your own computer:

    yt-dlp -f "bv*[height<=1080]+ba/b" -o input/source.mp4 "https://www.youtube.com/watch?v=CB2aoMPP2dU"
    yt-dlp -f "bv*[height<=720]+ba/b"  -o style_ref/ref.mp4 "https://youtu.be/9TJxC5rEq_c"

Then ask Claude: "сделай реакцию in-this-town-1" (the reaction-video skill does the rest).
Credit TeamDeam in the description.
