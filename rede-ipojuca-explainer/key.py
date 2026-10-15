"""Cut the character out of the generated clip.

The model rendered a magenta-to-white gradient with a floor, so a plain colour key is not enough:
alpha comes from rembg (isnet-general-use), and a magenta key on top clears the backdrop seen
through the glasses and removes magenta spill from the edges.

usage: python3 key.py char.mp4
writes char_frames/NNNN.png (RGBA) next to this script.
"""
import glob
import os
import subprocess
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'char_frames')
RAW = os.path.join(HERE, 'char_raw')


def key_frame(rgb, matte=None):
    a = rgb.astype(np.float32)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    magenta = np.minimum(r, b) - g          # high on the magenta backdrop, low/negative on the boy
    alpha = 1.0 - np.clip((magenta - 40.0) / 70.0, 0.0, 1.0)
    if matte is not None:
        alpha = np.minimum(alpha, matte.astype(np.float32) / 255.0)
    # despill: pull the shared red/blue excess back toward green on semi-transparent edges
    spill = np.clip(magenta - 10.0, 0.0, None) * 0.9
    r2 = np.clip(r - spill, 0, 255)
    b2 = np.clip(b - spill, 0, 255)
    out = np.dstack([r2, g, b2, alpha * 255.0]).astype(np.uint8)
    return out


def main():
    src = sys.argv[1]
    for d in (OUT, RAW):
        os.makedirs(d, exist_ok=True)
        for f in glob.glob(os.path.join(d, '*.png')):
            os.remove(f)
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-i', src, os.path.join(RAW, '%04d.png')], check=True)
    from rembg import new_session, remove
    session = new_session('isnet-general-use')
    for f in sorted(glob.glob(os.path.join(RAW, '*.png'))):
        im = Image.open(f).convert('RGB')
        matte = np.array(remove(im, session=session, only_mask=True))
        Image.fromarray(key_frame(np.array(im), matte), 'RGBA').save(os.path.join(OUT, os.path.basename(f)))
    print(len(glob.glob(os.path.join(OUT, '*.png'))), 'frames keyed')


if __name__ == '__main__':
    main()
