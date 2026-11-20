"""Approximate Lightroom (PV2012) preset -> 3D LUT (.cube) converter.

Input/Output assumed: Rec.709 / sRGB display-referred (gamma ~2.2/2.4).
Spatial tools (grain, sharpening, NR, clarity, texture, dehaze, vignette) can't live in a LUT and are skipped.
"""
import re, sys, os, numpy as np

def parse(path):
    t = open(path, encoding="utf-8").read()
    attrs = {k: v for k, v in re.findall(r'crs:(\w+)="([^"]*)"', t)}
    def num(k, d=0.0):
        try: return float(attrs.get(k, d))
        except ValueError: return d
    curves = {}
    for tag in ["ToneCurvePV2012", "ToneCurvePV2012Red", "ToneCurvePV2012Green", "ToneCurvePV2012Blue"]:
        m = re.search(rf"<crs:{tag}>(.*?)</crs:{tag}>", t, re.S)
        if m:
            pts = [tuple(map(float, p.split(","))) for p in re.findall(r"<rdf:li>([^<]+)</rdf:li>", m.group(1))]
            curves[tag] = np.array(pts) / 255.0
    name = re.search(r"<crs:Name>.*?<rdf:li[^>]*>([^<]*)<", t, re.S).group(1)
    return name, attrs, num, curves

# ---------- helpers ----------
def srgb_to_lin(x): x = np.clip(x, 0, 1); return np.where(x <= 0.04045, x / 12.92, ((x + 0.055) / 1.055) ** 2.4)
def lin_to_srgb(x): x = np.clip(x, 0, None); return np.where(x <= 0.0031308, x * 12.92, 1.055 * np.power(x, 1 / 2.4) - 0.055)
def luma(rgb): return rgb @ np.array([0.2126, 0.7152, 0.0722])
def smooth(a, b, x): t = np.clip((x - a) / (b - a), 0, 1); return t * t * (3 - 2 * t)
def bump(x, lo, hi):
    t = np.clip((x - lo) / (hi - lo), 0, 1); return np.sin(np.pi * t) ** 2

def spline(pts):
    """Monotone cubic (Fritsch-Carlson) through curve points -> function."""
    x, y = pts[:, 0], pts[:, 1]
    if len(x) == 2: return lambda v: np.interp(v, x, y)
    h = np.diff(x); d = np.diff(y) / h
    m = np.zeros_like(y); m[0], m[-1] = d[0], d[-1]
    for i in range(1, len(x) - 1):
        if d[i - 1] * d[i] > 0:
            w1, w2 = 2 * h[i] + h[i - 1], h[i] + 2 * h[i - 1]
            m[i] = (w1 + w2) / (w1 / d[i - 1] + w2 / d[i])
    def f(v):
        i = np.clip(np.searchsorted(x, v) - 1, 0, len(h) - 1)
        t = (v - x[i]) / h[i]
        t2, t3 = t * t, t * t * t
        out = (2*t3 - 3*t2 + 1) * y[i] + (t3 - 2*t2 + t) * h[i] * m[i] + (-2*t3 + 3*t2) * y[i+1] + (t3 - t2) * h[i] * m[i+1]
        out = np.where(v < x[0], y[0], out); out = np.where(v > x[-1], y[-1], out)
        return out
    return f

def rgb_to_hsv(rgb):
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    mx, mn = rgb.max(-1), rgb.min(-1); c = mx - mn
    h = np.zeros_like(mx); nz = c > 1e-9
    rc = np.where(nz, (mx - r) / np.where(nz, c, 1), 0); gc = np.where(nz, (mx - g) / np.where(nz, c, 1), 0); bc = np.where(nz, (mx - b) / np.where(nz, c, 1), 0)
    h = np.where(r == mx, bc - gc, np.where(g == mx, 2 + rc - bc, 4 + gc - rc))
    h = np.where(nz, (h / 6) % 1, 0)
    s = np.where(mx > 1e-9, c / np.where(mx > 1e-9, mx, 1), 0)
    return np.stack([h * 360, s, mx], -1)

def hsv_to_rgb(hsv):
    h, s, v = hsv[..., 0] / 60 % 6, np.clip(hsv[..., 1], 0, 1), hsv[..., 2]
    k = lambda n: (n + h) % 6
    f = lambda n: v - v * s * np.clip(np.minimum(k(n), 4 - k(n)), 0, 1)
    return np.stack([f(5), f(3), f(1)], -1)

def hue_rgb(deg): return hsv_to_rgb(np.array([[deg, 1.0, 1.0]]))[0]

BANDS = [("Red", 0), ("Orange", 30), ("Yellow", 60), ("Green", 120), ("Aqua", 180), ("Blue", 240), ("Purple", 270), ("Magenta", 300)]
def band_weights(h):
    cs = [c for _, c in BANDS] + [360]
    w = np.zeros(h.shape + (8,))
    for i in range(8):
        a, b = cs[i], cs[i + 1]
        t = np.clip((h - a) / (b - a), 0, 1); inside = (h >= a) & (h < b)
        w[..., i] += np.where(inside, 1 - t, 0); w[..., (i + 1) % 8] += np.where(inside, t, 0)
    return w

# ---------- pipeline ----------
def build(num, attrs, curves):
    def tone1d(x):  # basic panel + parametric, per channel on gamma values
        c = num("Contrast2012") / 100
        x = x + 0.35 * c * (x - 0.5) * 4 * x * (1 - x)
        x = x + 0.22 * num("Highlights2012") / 100 * bump(x, 0.45, 1.05)
        x = x + 0.22 * num("Shadows2012") / 100 * bump(x, -0.05, 0.55)
        x = x + 0.12 * num("Whites2012") / 100 * smooth(0.55, 1.0, x)
        x = x + 0.12 * num("Blacks2012") / 100 * (1 - smooth(0.0, 0.45, x))
        s1, s2, s3 = num("ParametricShadowSplit", 25) / 100, num("ParametricMidtoneSplit", 50) / 100, num("ParametricHighlightSplit", 75) / 100
        for k, lo, hi in [("ParametricShadows", 0, s1), ("ParametricDarks", s1 * 0.5, s2), ("ParametricLights", s2, (s3 + 1) / 2), ("ParametricHighlights", s3, 1)]:
            x = x + 0.12 * num(k) / 100 * bump(x, lo - (hi - lo) * 0.5, hi + (hi - lo) * 0.5)
        return np.clip(x, 0, 1)
    xs = np.linspace(0, 1, 4096)
    t = np.maximum.accumulate(tone1d(xs))
    if "ToneCurvePV2012" in curves: t = spline(curves["ToneCurvePV2012"])(t)
    tone = lambda v: np.interp(v, xs, t)
    chan = [spline(curves[k]) if k in curves else (lambda v: v) for k in ["ToneCurvePV2012Red", "ToneCurvePV2012Green", "ToneCurvePV2012Blue"]]

    def apply(rgb):
        lin = srgb_to_lin(rgb)
        T, Ti = num("IncrementalTemperature"), num("IncrementalTint")
        lin = lin * np.array([1 + 0.004 * T, 1 - 0.003 * Ti, 1 - 0.004 * T])
        st = num("ShadowTint") / 100
        lin = lin * (1 + 0.15 * st * np.array([-0.5, 1, -0.5]) * (1 - smooth(0, 0.25, luma(lin)))[..., None])
        lin = lin * 2 ** num("Exposure2012")
        lin = lin / (1 + np.maximum(lin - 0.9, 0) * 0.6)  # soft rolloff for exposure push
        g = lin_to_srgb(lin)
        # calibration: shift hue/sat of colours near each primary
        hsv = rgb_to_hsv(np.clip(g, 0, 1)); hh = hsv[..., 0]
        wp = [np.clip(1 - np.minimum(np.abs(hh - c), 360 - np.abs(hh - c)) / 120, 0, 1) for c in (0, 120, 240)]
        hsv[..., 0] = (hh + 0.30 * sum(w * num(n + "Hue") for w, n in zip(wp, ["Red", "Green", "Blue"]))) % 360
        hsv[..., 1] = hsv[..., 1] * (1 + 0.5 * sum(w * num(n + "Saturation") for w, n in zip(wp, ["Red", "Green", "Blue"])) / 100)
        g = hsv_to_rgb(hsv)
        g = tone(np.clip(g, 0, 1))
        g = np.stack([chan[i](g[..., i]) for i in range(3)], -1)
        # HSL
        hsv = rgb_to_hsv(np.clip(g, 0, 1)); w = band_weights(hsv[..., 0])
        dh = sum(w[..., i] * num("HueAdjustment" + n) for i, (n, _) in enumerate(BANDS))
        ds = sum(w[..., i] * num("SaturationAdjustment" + n) for i, (n, _) in enumerate(BANDS)) / 100
        dl = sum(w[..., i] * num("LuminanceAdjustment" + n) for i, (n, _) in enumerate(BANDS)) / 100
        s0 = hsv[..., 1]
        hsv[..., 0] = (hsv[..., 0] + 0.30 * dh) % 360
        hsv[..., 1] = s0 * (1 + ds)
        g = hsv_to_rgb(hsv)
        g = g + (0.30 * dl * s0 * luma(np.clip(g, 0, 1)))[..., None]  # additive: lighten/darken without adding chroma
        # vibrance / saturation
        L = luma(g)[..., None]
        sat = np.clip(rgb_to_hsv(np.clip(g, 0, 1))[..., 1], 0, 1)[..., None]
        v = num("Vibrance") / 100
        vib = 1 + (v * (1 - sat) * 0.9 if v >= 0 else v * 0.8 * np.ones_like(sat))
        g = L + (g - L) * vib * (1 + num("Saturation") / 100)
        # split toning / colour grading (shadows, mids, highlights)
        L = luma(np.clip(g, 0, 1))
        bal = num("SplitToningBalance") / 100
        ws = 1 - smooth(0.0, 0.55 + 0.25 * bal, L); wh = smooth(0.45 + 0.25 * bal, 1.0, L); wm = 1 - np.abs(L - 0.5) * 2
        for hk, sk, wgt in [("SplitToningShadowHue", "SplitToningShadowSaturation", ws), ("SplitToningHighlightHue", "SplitToningHighlightSaturation", wh), ("ColorGradeMidtoneHue", "ColorGradeMidtoneSat", np.clip(wm, 0, 1))]:
            s = num(sk) / 100
            if s:
                tint = hue_rgb(num(hk)); tint = tint - luma(tint)
                g = g + 0.25 * s * wgt[..., None] * tint
        return np.clip(g, 0, 1)
    return apply

def write_cube(path, title, fn, n=33):
    r = np.linspace(0, 1, n)
    b, g, rr = np.meshgrid(r, r, r, indexing="ij")  # red varies fastest
    grid = np.stack([rr, g, b], -1).reshape(-1, 3)
    out = fn(grid)
    with open(path, "w") as f:
        f.write(f'TITLE "{title}"\n# Approximation of Lightroom preset "{title}" for Rec.709 footage\nLUT_3D_SIZE {n}\nDOMAIN_MIN 0.0 0.0 0.0\nDOMAIN_MAX 1.0 1.0 1.0\n')
        f.writelines(f"{a:.6f} {c:.6f} {d:.6f}\n" for a, c, d in out)
    return fn

if __name__ == "__main__":
    outdir = sys.argv[1]; os.makedirs(outdir, exist_ok=True)
    for p in sys.argv[2:]:
        name, attrs, num, curves = parse(p)
        fn = build(num, attrs, curves)
        safe = re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_")
        write_cube(os.path.join(outdir, f"TTC_{safe}.cube"), name, fn)
        print("wrote", safe)
