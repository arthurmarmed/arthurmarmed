"""Render the 15 s Rede Ipojuca explainer (1920x1080, 30 fps).

Website layer = the user's real screenshots (browser tab row removed).
Character layer = keyed RGBA frames in char_frames/ (or a static placeholder).
"""
import glob
import math
import os
import subprocess
import sys

from PIL import Image, ImageChops, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
IMG = os.path.join(HERE, 'assets', 'screenshots')
W, H, FPS, DUR = 1920, 1080, 30, 15.0
NF = int(DUR * FPS)

# ---------- source crops (coordinates in the 2000x1301 screenshots) ----------
BAR_Y0, BAR_Y1 = 48, 120          # Safari address bar row (tab row 120-158 dropped)
CONTENT_Y0 = 158                  # page starts here
CW = 1980                         # page width without the scrollbar
HDR_END = {2: 311, 3: 311, 4: 289, 5: 289, 6: 289}

shots = {i: Image.open(os.path.join(IMG, f'{i}.jpg')).convert('RGB') for i in range(2, 7)}
bar = shots[2].crop((0, BAR_Y0, 2000, BAR_Y1)).resize((CW, BAR_Y1 - BAR_Y0), Image.LANCZOS)
BAR_H = bar.height
VIEW_H = 1301 - CONTENT_Y0        # 1143
WIN_SRC_W, WIN_SRC_H = CW, BAR_H + VIEW_H


def header(i):
    return shots[i].crop((0, CONTENT_Y0, CW, HDR_END[i]))


def body(i):
    return shots[i].crop((0, HDR_END[i], CW, 1301))


def page(i):
    return shots[i].crop((0, CONTENT_Y0, CW, 1301))


# ---------- easing ----------
def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def ease(x):
    x = clamp(x)
    return x * x * (3 - 2 * x)


def ease_io(x):
    x = clamp(x)
    return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


def seg(t, t0, t1):
    return clamp((t - t0) / (t1 - t0))


def lerp(a, b, k):
    return a + (b - a) * k


def keyframes(t, keys, fn=ease_io):
    """keys: list of (time, value); value may be tuple."""
    if t <= keys[0][0]:
        return keys[0][1]
    for (t0, v0), (t1, v1) in zip(keys, keys[1:]):
        if t <= t1:
            k = fn(seg(t, t0, t1))
            if isinstance(v0, tuple):
                return tuple(lerp(a, b, k) for a, b in zip(v0, v1))
            return lerp(v0, v1, k)
    return keys[-1][1]


# ---------- page state (what the browser viewport shows) ----------
# content coordinates: x in source px, y = source_y - CONTENT_Y0
def nav(i, x):
    return (x, (277 if i in (2, 3) else 260) - CONTENT_Y0)


def page_image(t):
    """Return (RGB viewport image VIEW_H tall, current shot id)."""
    # 5.85-6.75 s: smooth scroll homepage -> Simbora -> Categorias
    s0, s1 = 5.85, 6.75
    if t < s0:
        return page(2), 2
    if t < s1:
        k = ease_io(seg(t, s0, s1))
        strip_parts = [body(2), body(3), body(4)]
        hdr = header(2) if k < 0.5 else header(4)
        vh = VIEW_H - hdr.height
        total = sum(p.height for p in strip_parts)
        strip = Image.new('RGB', (CW, total))
        y = 0
        for p in strip_parts:
            strip.paste(p, (0, y))
            y += p.height
        # end offset = start of body(4) aligned under the smaller header
        end = body(2).height + body(3).height
        off = int(lerp(0, end, k))
        view = strip.crop((0, off, CW, off + vh))
        # motion blur proportional to speed
        speed = abs(ease_io(seg(t + 1 / FPS, s0, s1)) - ease_io(seg(t - 1 / FPS, s0, s1)))
        blur = min(14, speed * end / 18)
        if blur > 1.5:  # cheap vertical motion blur: squash then stretch
            view = view.resize((CW, max(1, int(vh / blur))), Image.BOX).resize((CW, vh), Image.BILINEAR)
        out = Image.new('RGB', (CW, VIEW_H))
        out.paste(view, (0, hdr.height))
        out.paste(hdr, (0, 0))
        return out, 4
    if t < 8.75:
        return page(4), 4
    if t < 9.15:  # page navigation to the category page
        k = ease(seg(t, 8.75, 9.15))
        return Image.blend(page(4), page(6), k), 6
    return page(6), 6


def rounded_mask(size, r):
    m = Image.new('L', size, 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, size[0] - 1, size[1] - 1), r, fill=255)
    return m


def glow_rect(img, box, alpha, y_off, color=(255, 196, 0), radius=14, width=6):
    """Subtle emphasis ring drawn on the window image (window coords)."""
    if alpha <= 0.01:
        return
    x0, y0, x1, y1 = box
    y0 += y_off
    y1 += y_off
    pad = 10
    layer = Image.new('RGBA', img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle((x0 - pad, y0 - pad, x1 + pad, y1 + pad), radius + pad,
                        outline=color + (int(110 * alpha),), width=width + 14)
    layer = layer.filter(ImageFilter.GaussianBlur(10))
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle((x0 - pad, y0 - pad, x1 + pad, y1 + pad), radius + pad,
                        outline=color + (int(255 * alpha),), width=width)
    img.alpha_composite(layer)


def ripple(img, pos, k, y_off):
    if not 0 < k < 1:
        return
    x, y = pos[0], pos[1] + y_off
    r = 18 + 70 * ease(k)
    a = int(200 * (1 - k))
    layer = Image.new('RGBA', img.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).ellipse((x - r, y - r, x + r, y + r), outline=(32, 117, 193, a), width=8)
    img.alpha_composite(layer)


# ---------- timeline: highlights, cursor, clicks (content coordinates) ----------
NAV2 = {'Início': 507, 'Rolando': 710, 'Simbora': 964, 'Vídeos': 1119, 'Categorias': 1246, 'Mapa': 1420}
NAV_BOX2 = {'Categorias': (1190, 255, 1302, 299)}
CARD_ADMIN = (354, 403 - CONTENT_Y0, 609, 611 - CONTENT_Y0)
ROW_CERT = (749, 597 - CONTENT_Y0, 1711, 673 - CONTENT_Y0)
BTN_ACESSAR = (1502, 613 - CONTENT_Y0, 1641, 657 - CONTENT_Y0)
URL_PILL = (596, 66 - BAR_Y0, 1405, 102 - BAR_Y0)   # bar coords

CURSOR_KEYS = [
    (0.0, (1350, 760)), (2.2, (1350, 760)),
    (3.25, nav(2, NAV2['Início'])),
    (3.75, nav(2, NAV2['Rolando'])),
    (4.25, nav(2, NAV2['Simbora'])),
    (4.75, nav(2, NAV2['Vídeos'])),
    (5.3, nav(2, NAV2['Categorias'])),
    (5.85, nav(2, NAV2['Categorias'])),
    (6.9, (1209, 102)),
    (7.9, ((354 + 609) // 2, 520 - CONTENT_Y0)),
    (8.75, ((354 + 609) // 2, 520 - CONTENT_Y0)),
    (9.6, (900, 635 - CONTENT_Y0)),
    (10.6, (1571, 635 - CONTENT_Y0)),
    (15.0, (1571, 635 - CONTENT_Y0)),
]
CLICKS = [(5.6, nav(2, NAV2['Categorias'])), (8.45, ((354 + 609) // 2, 520 - CONTENT_Y0))]


def cursor_pos(t):
    return keyframes(t, CURSOR_KEYS)


def cursor_alpha(t):
    return ease(seg(t, 2.0, 2.4))


def highlights(t):
    """list of (box_in_content_coords or ('bar', box), alpha)."""
    out = []
    a = ease(seg(t, 5.25, 5.45)) * (1 - ease(seg(t, 5.9, 6.1)))
    out.append(((1190, 255 - CONTENT_Y0, 1302, 299 - CONTENT_Y0), a))
    a = ease(seg(t, 7.7, 8.0)) * (1 - ease(seg(t, 8.7, 8.85)))
    out.append((CARD_ADMIN, a))
    a = ease(seg(t, 9.4, 9.8)) * (1 - ease(seg(t, 10.5, 10.8)))
    out.append((ROW_CERT, a))
    a = ease(seg(t, 10.55, 10.85)) * (1 - ease(seg(t, 12.6, 12.9)))
    out.append((BTN_ACESSAR, a))
    a = ease(seg(t, 12.9, 13.4))
    out.append((('bar', URL_PILL), a))
    return out


# ---------- camera (world == 1920x1080 layout at zoom 1) ----------
WIN_W = 1360
SCALE0 = WIN_W / WIN_SRC_W
WIN_H = WIN_SRC_H * SCALE0
WIN_X, WIN_Y = 50, (H - WIN_H) / 2


def src_to_world(px, py):
    return WIN_X + px * SCALE0, WIN_Y + py * SCALE0


def world_nav_focus():
    # nav centre lands at screen x~720, left of the character
    x, y = src_to_world(989, BAR_H + 119)
    return (x + 240 / 1.32, y + 150)


CAM_KEYS = [  # (t, (cx, cy, zoom))
    (0.0, (960, 540, 1.0)),
    (3.0, (930, 540, 1.045)),
    (4.3, world_nav_focus() + (1.32,)),
    (5.6, world_nav_focus() + (1.32,)),
    (6.7, (900, 540, 1.04)),
    (8.6, (860, 560, 1.08)),
    (9.3, (880, 560, 1.06)),
    (10.8, (src_to_world(1230, 0)[0] + 200, src_to_world(0, BAR_H + 720 - CONTENT_Y0)[1], 1.28)),
    (12.0, (src_to_world(1230, 0)[0] + 200, src_to_world(0, BAR_H + 720 - CONTENT_Y0)[1], 1.28)),
    (13.3, (900, 470, 1.16)),
    (15.0, (880, 440, 1.22)),
]


def camera(t):
    return keyframes(t, CAM_KEYS)


def to_screen(wx, wy, cam):
    cx, cy, z = cam
    return (wx - cx) * z + W / 2, (wy - cy) * z + H / 2


# ---------- static layers ----------
def make_background():
    bg = Image.new('RGB', (W, H))
    top, bot = (236, 243, 251), (205, 222, 242)
    d = ImageDraw.Draw(bg)
    for y in range(H):
        k = y / (H - 1)
        d.line([(0, y), (W, y)], fill=tuple(int(lerp(a, b, k)) for a, b in zip(top, bot)))
    # soft light spot behind the character
    spot = Image.new('L', (W, H), 0)
    ImageDraw.Draw(spot).ellipse((1300, 120, 2100, 1100), fill=90)
    spot = spot.filter(ImageFilter.GaussianBlur(160))
    bg = Image.composite(Image.new('RGB', (W, H), (255, 255, 255)), bg, spot)
    return bg


BG = make_background()
RADIUS_SRC = 26
WIN_MASK = rounded_mask((WIN_SRC_W, WIN_SRC_H), RADIUS_SRC)
PAD = 120
SHADOW = Image.new('L', (WIN_SRC_W + 2 * PAD, WIN_SRC_H + 2 * PAD), 0)
ImageDraw.Draw(SHADOW).rounded_rectangle((PAD, PAD + 30, PAD + WIN_SRC_W, PAD + WIN_SRC_H + 30), RADIUS_SRC, fill=95)
SHADOW = SHADOW.filter(ImageFilter.GaussianBlur(40))


def make_cursor(scale=1.0):
    pts = [(0, 0), (0, 34), (8, 26), (14, 40), (20, 37), (14, 24), (25, 24)]
    s = 2 * scale
    img = Image.new('RGBA', (int(40 * s) + 8, int(50 * s) + 8), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    p = [(x * s + 4, y * s + 4) for x, y in pts]
    d.polygon(p, fill=(255, 255, 255, 255))
    d.line(p + [p[0]], fill=(20, 20, 20, 255), width=int(2.2 * s), joint='curve')
    img = img.resize((img.width // 2, img.height // 2), Image.LANCZOS)
    sh = Image.new('RGBA', img.size, (0, 0, 0, 0))
    sh.putalpha(img.getchannel('A').point(lambda v: v * 0.35).filter(ImageFilter.GaussianBlur(2)))
    out = Image.new('RGBA', (img.width + 6, img.height + 6), (0, 0, 0, 0))
    out.alpha_composite(sh, (3, 4))
    out.alpha_composite(img, (0, 0))
    return out


CURSOR = make_cursor(1.0)


# ---------- character ----------
CHAR_DIR = os.path.join(HERE, 'char_frames')
char_files = sorted(glob.glob(os.path.join(CHAR_DIR, '*.png')))
CHAR_FALLBACK = Image.open(os.path.join(HERE, 'assets', 'char_cut.png')).convert('RGBA')
CHAR_MAP = os.path.join(HERE, 'char_map.txt')   # optional: one source-frame index per output frame
char_map = None
if os.path.exists(CHAR_MAP) and char_files:
    char_map = [int(x) for x in open(CHAR_MAP).read().split()]

CHAR_H = 860          # on-screen height of the source character frame (720 px tall source)
CHAR_CX = 1690        # horizontal centre on screen


def character_layer(fi, t):
    if char_files:
        idx = char_map[fi] if char_map else min(fi, len(char_files) - 1)
        im = Image.open(char_files[min(idx, len(char_files) - 1)]).convert('RGBA')
        s = CHAR_H / im.height
        im = im.resize((int(im.width * s), CHAR_H), Image.LANCZOS)
        x = int(CHAR_CX - im.width / 2)
        y = H - CHAR_H + 20
    else:
        h = 780
        im = CHAR_FALLBACK.resize((int(CHAR_FALLBACK.width * h / CHAR_FALLBACK.height), h), Image.LANCZOS)
        x = int(CHAR_CX - im.width / 2)
        y = H - h + 20 + int(4 * math.sin(t * 2.2))
    # gentle entrance: slide up during the first 0.5 s
    y += int(60 * (1 - ease(seg(t, 0.0, 0.5))))
    return im, (x, y)


# ---------- frame ----------
def render(fi):
    t = fi / FPS
    view, shot = page_image(t)
    win = Image.new('RGBA', (WIN_SRC_W, WIN_SRC_H))
    win.paste(bar, (0, 0))
    win.paste(view, (0, BAR_H))
    for box, a in highlights(t):
        if isinstance(box[0], str):
            glow_rect(win, box[1], a, 0, color=(255, 196, 0), radius=18, width=5)
        else:
            glow_rect(win, box, a, BAR_H)
    for ct, pos in CLICKS:
        ripple(win, pos, seg(t, ct, ct + 0.45), BAR_H)
    win.putalpha(WIN_MASK)

    cam = camera(t)
    z = cam[2] * SCALE0
    frame = BG.copy()
    # shadow
    sx, sy = to_screen(WIN_X - PAD * SCALE0, WIN_Y - PAD * SCALE0, cam)
    sh = SHADOW.resize((int(SHADOW.width * z), int(SHADOW.height * z)), Image.BILINEAR)
    black = Image.new('RGB', sh.size, (20, 40, 70))
    frame.paste(black, (int(sx), int(sy)), sh)
    # window
    wx, wy = to_screen(WIN_X, WIN_Y, cam)
    ww, wh = int(round(WIN_SRC_W * z)), int(round(WIN_SRC_H * z))
    winr = win.resize((ww, wh), Image.LANCZOS)
    frame.paste(winr, (int(round(wx)), int(round(wy))), winr)

    # cursor (screen space)
    ca = cursor_alpha(t)
    if ca > 0:
        px, py = cursor_pos(t)
        cx, cy = to_screen(*src_to_world(px, py + BAR_H), cam)
        cur = CURSOR
        for ct, _ in CLICKS:  # press squish
            k = seg(t, ct - 0.05, ct + 0.15)
            if 0 < k < 1:
                s = 1 - 0.18 * math.sin(math.pi * k)
                cur = CURSOR.resize((int(CURSOR.width * s), int(CURSOR.height * s)), Image.LANCZOS)
        if ca < 1:
            cur = cur.copy()
            cur.putalpha(cur.getchannel('A').point(lambda v: int(v * ca)))
        frame.paste(cur, (int(cx), int(cy)), cur)

    # character (screen space) with contact shadow
    im, (x, y) = character_layer(fi, t)
    shadow = Image.new('L', (W, H), 0)
    ImageDraw.Draw(shadow).ellipse((CHAR_CX - 260, H - 40, CHAR_CX + 260, H + 60), fill=110)
    shadow = shadow.filter(ImageFilter.GaussianBlur(30))
    frame.paste(Image.new('RGB', (W, H), (40, 60, 90)), (0, 0), shadow)
    frame.paste(im, (x, y), im)

    # very short fade in
    if t < 0.25:
        frame = Image.blend(Image.new('RGB', (W, H), (236, 243, 251)), frame, ease(t / 0.25))
    return frame


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'video_noaudio.mp4')
    only = sys.argv[2:]  # optional frame indices -> PNG previews
    if only:
        for f in only:
            render(int(f)).save(os.path.join(HERE, f'preview_{int(f):03d}.png'))
        return
    p = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24',
                          '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-', '-c:v', 'libx264', '-preset', 'slow',
                          '-crf', '16', '-pix_fmt', 'yuv420p', '-r', str(FPS), out], stdin=subprocess.PIPE)
    for fi in range(NF):
        p.stdin.write(render(fi).tobytes())
        if fi % 30 == 0:
            print('frame', fi, flush=True)
    p.stdin.close()
    p.wait()


if __name__ == '__main__':
    main()
