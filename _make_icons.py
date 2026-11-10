"""Generuje kolorowe ikonki PNG 32x32 z antyaliasingiem (supersampling 4x)."""
import os
import struct
import zlib

L = 32          # rozmiar wyjsciowy
SS = 4          # supersampling
W = L * SS      # rozdzielczosc robocza (128)
OUT = os.path.join("src", "pic", "icons")
os.makedirs(OUT, exist_ok=True)

DARK = (32, 41, 58, 255)        # #20293a
BLUE = (47, 108, 176, 255)      # #2f6cb0
BLUE_D = (30, 80, 140, 255)
GREEN = (45, 164, 78, 255)      # #2da44e
GREEN_D = (26, 127, 55, 255)
ORANGE = (210, 153, 34, 255)    # #d29922
RED = (207, 34, 46, 255)        # #cf222e
RED_D = (160, 20, 35, 255)
PURPLE = (130, 80, 223, 255)    # #8250df
PINK = (219, 84, 120, 255)      # #db5478
WHITE = (255, 255, 255, 255)


def new_img():
    return bytearray(W * W * 4)


def px(img, x, y, color):
    x, y = int(x), int(y)
    if 0 <= x < W and 0 <= y < W:
        i = (y * W + x) * 4
        img[i:i + 4] = bytes(color)


def disc(img, cx, cy, r, color):
    for y in range(int(cy) - r - 1, int(cy) + r + 2):
        for x in range(int(cx) - r - 1, int(cx) + r + 2):
            if (x - cx) ** 2 + (y - cy) ** 2 <= r * r:
                px(img, x, y, color)


def line(img, x0, y0, x1, y1, thick, color):
    steps = int(max(abs(x1 - x0), abs(y1 - y0))) + 1
    for i in range(steps + 1):
        t = i / steps
        disc(img, x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, thick, color)


def rect(img, x0, y0, x1, y1, color):
    for y in range(int(y0), int(y1) + 1):
        for x in range(int(x0), int(x1) + 1):
            px(img, x, y, color)


def poly(img, pts, color):
    ys = [p[1] for p in pts]
    for y in range(min(ys), max(ys) + 1):
        xs = []
        for i in range(len(pts)):
            x1, y1 = pts[i]
            x2, y2 = pts[(i + 1) % len(pts)]
            if (y1 <= y < y2) or (y2 <= y < y1):
                xs.append(x1 + (y - y1) * (x2 - x1) / (y2 - y1))
        xs.sort()
        for a, b in zip(xs[::2], xs[1::2]):
            for x in range(int(a), int(b) + 1):
                px(img, x, y, color)


# ── helpery w skali logicznej (mnoza wspolrzedne przez SS) ────────────────────
def S(v):
    return v * SS


def icon_run():
    """Play — zielony trojkat z polyskiem."""
    img = new_img()
    poly(img, [(S(9), S(6)), (S(26), S(16)), (S(9), S(26))], GREEN)
    poly(img, [(S(11), S(9)), (S(22), S(16)), (S(11), S(23))], GREEN_D)
    return img


def icon_test():
    """Kolba — fioletowy obrys, roza ciecz z fala, bąbelki."""
    img = new_img()
    line(img, S(13), S(5), S(13), S(13), SS, PURPLE)
    line(img, S(19), S(5), S(19), S(13), SS, PURPLE)
    line(img, S(13), S(5), S(19), S(5), SS, PURPLE)
    line(img, S(13), S(13), S(6), S(26), SS, PURPLE)
    line(img, S(19), S(13), S(26), S(26), SS, PURPLE)
    line(img, S(6), S(26), S(26), S(26), SS, PURPLE)
    # ciecz z fala na gorze
    poly(img, [(S(9), S(20)), (S(11), S(22)), (S(14), S(20)),
               (S(18), S(23)), (S(21), S(20)), (S(23), S(22)),
               (S(23), S(26)), (S(9), S(26))], PINK)
    disc(img, S(12), S(24), SS, WHITE)
    disc(img, S(16), S(25), SS, WHITE)
    disc(img, S(20), S(23), SS, WHITE)
    return img


def _bar(img, x0, x1, ytop, color, dark):
    """Slutek z zaokraglonym topem."""
    r = SS * 2
    cx = (x0 + x1) / 2 * SS
    rect(img, x0 * SS, (ytop + 2) * SS, x1 * SS, 28 * SS, color)
    disc(img, cx, (ytop + 2) * SS, r, color)
    # polysk po lewej
    rect(img, (x0 + 1) * SS, (ytop + 4) * SS, (x0 + 2) * SS, 26 * SS, dark)


def icon_report():
    """Wykres slupkowy — 3 rozne kolory, zaokraglone."""
    img = new_img()
    _bar(img, 7, 11, 20, GREEN, GREEN_D)
    _bar(img, 14, 18, 14, ORANGE, ORANGE)
    _bar(img, 21, 25, 8, BLUE, BLUE_D)
    line(img, S(5), S(27), S(27), S(27), SS, DARK)
    return img


def icon_about():
    """Litera i — niebieska, z ksztaltem kropki i pałki."""
    img = new_img()
    disc(img, S(16), S(9), 3 * SS, BLUE)
    rect(img, S(14), S(15), S(18), S(25), BLUE)
    disc(img, S(16), S(9), 2 * SS, BLUE_D)
    return img


def icon_stats():
    """Liniowy wykres trendu — niebieska linia z punktami, os."""
    img = new_img()
    pts = [(6, 22), (12, 16), (18, 20), (24, 9)]
    for i in range(len(pts) - 1):
        line(img, S(pts[i][0]), S(pts[i][1]),
             S(pts[i + 1][0]), S(pts[i + 1][1]), SS, BLUE)
    for i, (x, y) in enumerate(pts):
        color = ORANGE if i == len(pts) - 1 else BLUE
        disc(img, S(x), S(y), 2 * SS, color)
        disc(img, S(x), S(y), SS, WHITE)
    line(img, S(5), S(28), S(27), S(28), SS, DARK)
    return img


def icon_quit():
    """X — czerwone z cieniem."""
    img = new_img()
    line(img, S(9), S(9), S(23), S(23), 2 * SS, RED_D)
    line(img, S(23), S(9), S(9), S(23), 2 * SS, RED_D)
    line(img, S(9), S(9), S(23), S(23), SS, RED)
    line(img, S(23), S(9), S(9), S(23), SS, RED)
    return img


def downsample(img):
    """128x128 RGBA -> 32x32 RGBA z antyaliasingiem (box filter)."""
    out = bytearray(L * L * 4)
    for oy in range(L):
        for ox in range(L):
            sa = sr = sg = sb = 0.0
            for sy in range(SS):
                for sx in range(SS):
                    i = (((oy * SS + sy) * W) + (ox * SS + sx)) * 4
                    r, g, b, a = img[i], img[i + 1], img[i + 2], img[i + 3]
                    sa += a
                    sr += r * a
                    sg += g * a
                    sb += b * a
            j = (oy * L + ox) * 4
            if sa > 0:
                a = sa / (SS * SS)
                out[j] = int(sr / sa)
                out[j + 1] = int(sg / sa)
                out[j + 2] = int(sb / sa)
                out[j + 3] = int(a)
    return out


def write_png(path, img_hi):
    img = downsample(img_hi)

    def chunk(tag, data):
        c = tag + data
        return (struct.pack(">I", len(data)) + c +
                struct.pack(">I", zlib.crc32(c)))
    raw = b"".join(b"\x00" + bytes(img[y * L * 4:(y + 1) * L * 4])
                   for y in range(L))
    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", L, L, 8, 6, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(raw))
           + chunk(b"IEND", b""))
    with open(path, "wb") as f:
        f.write(png)


ICONS = {
    "run": icon_run,
    "test": icon_test,
    "report": icon_report,
    "stats": icon_stats,
    "about": icon_about,
    "quit": icon_quit,
}

for name, fn in ICONS.items():
    p = os.path.join(OUT, name + ".png")
    write_png(p, fn())
    print("OK", p)
