"""Place the boy's voice lines over his mouth movements and mix them with the music.

usage: python3 voice.py assets/voice_take.wav assets/music.wav assets/soundtrack.wav
       python3 voice.py assets/narration_take.wav assets/music.wav assets/soundtrack_narrated.wav narrator

The take is one Higgsfield Seed Audio generation ("Benji", pitch +4) with all lines. Each line is cut
from the take, raised another 4 semitones so he sounds younger, and dropped where his mouth moves.
"""
import os
import subprocess
import sys
import wave

import numpy as np

SR = 48000
DUR = 15.0

# (take_start, take_end, place_at) in seconds; take times come from silencedetect on the take
LINES = [
    (0.36, 1.40, 1.25),   # "Rede Ipojuca?"
    (1.84, 2.26, 2.38),   # "Hum…"
    (2.61, 3.16, 2.82),   # "deixa eu ver."
    (3.38, 4.82, 3.85),   # "Olha só: tá tudo no menu!"
    (5.60, 6.83, 6.30),   # "Clica em Categorias…"
    (7.46, 8.62, 9.45),   # "e clica em Acessar!"
]
PITCH = 2 ** (4 / 12)

# Screen-recording-only version: a narrator teaches each step (Benji at his natural pitch).
# Take times are pause boundaries in the take, matched to the sentences by syllable count.
NARRATOR_LINES = [
    (0.38, 2.95, 0.35),   # "Conheça a Rede Ipojuca, seu espaço de cidadania digital."
    (3.14, 4.33, 4.25),   # "No menu do topo, clique em Categorias." (ends just before the click at 5.6 s)
    (4.39, 7.98, 7.15),   # "Escolha a área, como Administração Pública, e clique em Acessar no serviço que você precisa."
    (8.15, 10.15, 12.35), # "Rede Ipojuca: os serviços da prefeitura num só lugar."
]


def read_wav(path):
    with wave.open(path) as w:
        assert w.getframerate() == SR, path
        x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
        return x.reshape(-1, w.getnchannels())


def main():
    take, music, out = sys.argv[1:4]
    narrator = len(sys.argv) > 4 and sys.argv[4] == 'narrator'
    lines = NARRATOR_LINES if narrator else LINES
    shifted = take + '.shifted.wav'
    af = 'anull' if narrator else f'rubberband=pitch={PITCH:.4f}'
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-i', take, '-af', af,
                    '-ar', str(SR), '-ac', '2', shifted], check=True)
    v = read_wav(shifted)
    os.remove(shifted)
    m = read_wav(music)
    n = int(DUR * SR)
    voice = np.zeros((n, 2), np.float32)
    for a, b, at in lines:
        seg = v[int(a * SR):int(b * SR)].copy()
        fade = int(0.012 * SR)
        ramp = np.linspace(0, 1, fade)[:, None]
        seg[:fade] *= ramp
        seg[-fade:] *= ramp[::-1]
        s = int(at * SR)
        voice[s:s + len(seg)] += seg[:n - s]
    voice *= 0.9 / max(1e-6, np.abs(voice).max())
    # duck the music under the voice
    env = np.convolve(np.abs(voice).mean(1), np.ones(int(0.08 * SR)) / int(0.08 * SR), mode='same')
    duck = 1 - 0.55 * np.clip(env / 0.05, 0, 1)
    mix = m[:n] * duck[:, None] * 0.8 + voice
    mix *= 0.95 / max(1e-6, np.abs(mix).max())
    with wave.open(out, 'wb') as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((mix * 32767).astype(np.int16).tobytes())
    print('wrote', out)


if __name__ == '__main__':
    main()
