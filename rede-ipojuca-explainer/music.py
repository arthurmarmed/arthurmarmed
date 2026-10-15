"""Synthesize a soft 15 s background bed (pad + marimba-like plucks) plus UI click/whoosh SFX."""
import wave

import numpy as np

SR = 48000
DUR = 15.0
N = int(SR * DUR)
t = np.arange(N) / SR
rng = np.random.default_rng(7)


def note(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def env_adsr(n, a, r):
    e = np.ones(n)
    na, nr = min(n, int(a * SR)), min(n, int(r * SR))
    e[:na] = np.linspace(0, 1, na)
    e[-nr:] *= np.linspace(1, 0, nr)
    return e


mix = np.zeros((N, 2))
BPM = 100
beat = 60 / BPM
bar = 4 * beat  # 2.4 s
chords = [[48, 55, 59, 64], [45, 52, 55, 60], [41, 48, 52, 57], [43, 50, 55, 59]]  # Cmaj7 Am7 Fmaj7 G

# pad: detuned soft saws filtered by averaging, one chord per bar
for i in range(int(np.ceil(DUR / bar))):
    s0 = int(i * bar * SR)
    n = min(int(bar * SR) + int(0.6 * SR), N - s0)
    if n <= 0:
        break
    tt = np.arange(n) / SR
    sig = np.zeros(n)
    for m in chords[i % 4]:
        for det in (-0.06, 0.06):
            f = note(m + 12) * (1 + det / 100)
            sig += np.sin(2 * np.pi * f * tt) + 0.25 * np.sin(4 * np.pi * f * tt)
    sig *= env_adsr(n, 0.5, 0.7) * 0.022
    pan = 0.5
    mix[s0:s0 + n, 0] += sig * (1 - pan * 0.3)
    mix[s0:s0 + n, 1] += sig * (0.7 + pan * 0.3)

# plucks: arpeggio on 8th notes, marimba-ish (sine + fast decay + 4x partial)
arp = [0, 2, 1, 3, 2, 1, 3, 2]
step = beat / 2
k = 0
while k * step < DUR - 0.2:
    ci = int(k * step // bar) % 4
    m = chords[ci][arp[k % 8]] + 24
    s0 = int(k * step * SR)
    n = min(int(0.9 * SR), N - s0)
    tt = np.arange(n) / SR
    f = note(m)
    sig = (np.sin(2 * np.pi * f * tt) * np.exp(-tt * 6) + 0.3 * np.sin(2 * np.pi * 4 * f * tt) * np.exp(-tt * 25))
    sig *= 0.05 * (0.85 + 0.15 * rng.random())
    p = 0.35 + 0.3 * ((k % 4) / 3)
    mix[s0:s0 + n, 0] += sig * (1 - p)
    mix[s0:s0 + n, 1] += sig * p
    k += 1

# soft bass on each bar
for i in range(int(np.ceil(DUR / bar))):
    s0 = int(i * bar * SR)
    n = min(int(bar * SR), N - s0)
    tt = np.arange(n) / SR
    f = note(chords[i % 4][0] - 12)
    sig = np.sin(2 * np.pi * f * tt) * env_adsr(n, 0.02, 0.4) * np.exp(-tt * 0.6) * 0.07
    mix[s0:s0 + n] += sig[:, None]


# UI SFX: clicks + a short whoosh for the scroll
def click(at, gain=0.25):
    s0 = int(at * SR)
    n = int(0.05 * SR)
    tt = np.arange(n) / SR
    sig = (rng.standard_normal(n) * np.exp(-tt * 300) + np.sin(2 * np.pi * 2200 * tt) * np.exp(-tt * 180)) * gain
    mix[s0:s0 + n] += sig[:, None]


def whoosh(a, b, gain=0.06):
    s0, s1 = int(a * SR), int(b * SR)
    n = s1 - s0
    noise = rng.standard_normal(n)
    # crude band-pass via moving averages
    lp = np.convolve(noise, np.ones(12) / 12, mode='same')
    bp = lp - np.convolve(lp, np.ones(80) / 80, mode='same')
    e = np.sin(np.linspace(0, np.pi, n)) ** 2
    mix[s0:s1] += (bp * e * gain * 6)[:, None]


click(5.6)
click(8.45)
whoosh(5.8, 6.8)

# master: fade in/out, normalize
fade = np.ones(N)
fi, fo = int(0.3 * SR), int(0.8 * SR)
fade[:fi] = np.linspace(0, 1, fi)
fade[-fo:] = np.linspace(1, 0, fo)
mix *= fade[:, None]
mix /= np.max(np.abs(mix)) / 0.6
pcm = (mix * 32767).astype(np.int16)
with wave.open('assets/music.wav', 'wb') as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes(pcm.tobytes())
print('ok', pcm.shape)
