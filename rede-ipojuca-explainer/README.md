# Rede Ipojuca — 15 s website explainer

A 15 s, 16:9, 1920×1080, 30 fps walkthrough of <https://rede.ipojuca.pe.gov.br> starring the "relaxa" cartoon boy.

The site is never redrawn or invented. Every website pixel comes from the real screenshots in
`assets/screenshots/`. The only changes are dropping the browser tab row, cursor movement, scrolling, zooms and
yellow emphasis rings. The boy is a Higgsfield image-to-video clip (Seedance 1.5 Pro), animated from
`assets/start_magenta.png` and keyed out of its magenta background.

| Time | Scene | Website |
|------|-------|---------|
| 0–3 s | Boy beside the browser, introduces the site | Homepage (`2.jpg`) |
| 3–7 s | Camera moves in on the nav bar; cursor hovers Início → … → Categorias, clicks, page scrolls | `2.jpg` → `3.jpg` → `4.jpg` |
| 7–12 s | Cursor picks **Administração Pública**; category page opens; **Solicitar Certidão Funcional → Acessar** highlighted | `4.jpg` → `6.jpg` |
| 12–15 s | Boy approves; address bar highlighted so `rede.ipojuca.pe.gov.br` is readable | `6.jpg` |

## Build

```sh
python3 music.py                      # assets/music.wav (soft synth bed + click/whoosh SFX)
python3 key.py assets/character_clip.mp4  # char_frames/*.png (rembg matte + magenta key)
python3 render.py video_noaudio.mp4   # renders 450 frames
python3 voice.py assets/voice_take.wav assets/music.wav assets/soundtrack.wav  # voice lines over the music
ffmpeg -i video_noaudio.mp4 -i assets/soundtrack.wav -c:v copy -c:a aac -b:a 192k -shortest rede_ipojuca_explainer.mp4
```

If `char_frames/` is missing, `render.py` uses a static cut-out of the boy as a placeholder.
`char_src_time()` in `render.py` retimes the 8 s clip to the four scenes; in-between frames are blended.

## Screen-recording-only tutorial

`rede_ipojuca_tutorial_narrado.mp4` is the same walkthrough without the boy: the browser fills the frame,
the camera zooms straight onto each step, and a narrator (Seed Audio "Benji", natural pitch) explains it.

```sh
NO_CHARACTER=1 python3 render.py tutorial_noaudio.mp4
python3 voice.py assets/narration_take.wav assets/music.wav assets/soundtrack_narrated.wav narrator
ffmpeg -i tutorial_noaudio.mp4 -i assets/soundtrack_narrated.wav -c:v copy -c:a aac -b:a 160k -shortest rede_ipojuca_tutorial_narrado.mp4
```
