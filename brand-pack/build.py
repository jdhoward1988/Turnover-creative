#!/usr/bin/env python3
"""The Turnover Creative - brand pack generator.

Builds four self-contained HTML documents (one per canvas size) that import
into Adobe Express as editable pages:

  express/01-feed-posts-4x5.html     1080 x 1350   (9 pages, 3 per mode)
  express/02-stories-9x16.html       1080 x 1920   (6 pages, 2 per mode)
  express/03-posters-11x17.html      3300 x 5100   (3 pages, 1 per mode, 300 dpi)
  express/04-brand-guide.html        1920 x 1080   (4 pages)

Run:  python3 brand-pack/build.py
"""
import base64
import io
import os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "express")
os.makedirs(OUT, exist_ok=True)

# --------------------------------------------------------------------------
# Brand tokens
# --------------------------------------------------------------------------
PJ = dict(  # A - Platform Journal (from the A style scape)
    newsprint="#F2EFE8", ink="#111111", chalk="#C9C6BF", red="#B5281F")
WU = dict(  # B - Warm-Up Room
    black="#0E0E0E", paper="#EDEDE8", pink="#FF48B0", blue="#0047BB")
CH = dict(  # C - Club Heritage
    green="#1F3A2E", cream="#EDE6D6", gold="#C9A46A", oxblood="#6B1E1E")

SERIF = "'instrument-serif', serif"
SANS = "'ibm-plex-sans', sans-serif"
MONO = "'ibm-plex-mono', monospace"
COND = "'archivo-condensed', sans-serif"
GRAD = "'graduate', serif"

HANDLE = "@theturnovercreative"
HANDLE_UP = "@THETURNOVERCREATIVE"
TAGLINE = "OLYMPIC-STYLE WEIGHTLIFTING · PACIFIC NORTHWEST"
DOT = "·"

FONT_LINK = '<link rel="stylesheet" href="https://use.typekit.net/arh6aed.css">'

# --------------------------------------------------------------------------
# Photo placeholders (real <img> so Express offers "Replace image")
# --------------------------------------------------------------------------
_MONO_TTF = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
_cache = {}


def placeholder(w, h, bg, fg, label):
    """Flat placeholder PNG with a crosshair and a label, as a data URI."""
    key = (w, h, bg, fg, label)
    if key in _cache:
        return _cache[key]
    # Render small; Express keeps the frame size when the image is replaced.
    # Small on purpose: keeps documents light; Express keeps the frame size
    # when you replace the image.
    s = max(w, h) / 480.0
    pw, ph = max(1, int(w / s)), max(1, int(h / s))
    fsize = max(9, int(min(pw, ph) / 22))
    im = Image.new("P", (pw, ph), bg)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, pw - 1, ph - 1], outline=fg, width=1)
    cx, cy = pw // 2, (ph // 2 if ph < pw * 1.3 else int(ph * 0.22))
    d.line([cx - 12, cy, cx + 12, cy], fill=fg, width=1)
    d.line([cx, cy - 12, cx, cy + 12], fill=fg, width=1)
    font = ImageFont.truetype(_MONO_TTF, fsize)
    for i, line in enumerate(label.split("\n")):
        tw = d.textlength(line, font=font)
        d.text((cx - tw / 2, cy + 20 + i * fsize * 1.5), line, fill=fg,
               font=font)
    buf = io.BytesIO()
    im.save(buf, "PNG", optimize=True)
    uri = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    _cache[key] = uri
    return uri


# --------------------------------------------------------------------------
# Tiny layout helpers. Every element is absolutely positioned inside .slide.
# `k` scales all geometry so the poster can be designed at 1100 x 1700.
# --------------------------------------------------------------------------
class Page:
    def __init__(self, w, h, bg, name, k=1.0):
        self.w, self.h, self.bg, self.name, self.k = w, h, bg, name, k
        self.parts = []

    def px(self, v):
        return f"{round(v * self.k, 2)}px"

    def box(self, x, y, w, h, fill=None, border=None, radius=None, extra=""):
        st = [f"left:{self.px(x)}", f"top:{self.px(y)}",
              f"width:{self.px(w)}", f"height:{self.px(h)}"]
        if fill:
            st.append(f"background-color:{fill}")
        if border:
            bw, bc = border
            st.append(f"border:{self.px(bw)} solid {bc}")
        if radius is not None:
            st.append(f"border-radius:{radius}")
        if extra:
            st.append(extra)
        self.parts.append(f'<div class="el" style="{";".join(st)}"></div>')

    def rule(self, x, y, w, color, t=2):
        self.box(x, y, w, t, fill=color)

    def text(self, x, y, w, html, font, size, color, lh=1.1, ls=0,
             weight=400, italic=False, upper=False, align="left", h=None):
        st = [f"left:{self.px(x)}", f"top:{self.px(y)}", f"width:{self.px(w)}",
              f"font-family:{font}", f"font-size:{self.px(size)}",
              f"line-height:{lh}", f"color:{color}", f"font-weight:{weight}",
              f"text-align:{align}"]
        if h is not None:
            st.append(f"height:{self.px(h)}")
        if ls:
            st.append(f"letter-spacing:{ls}em")
        if italic:
            st.append("font-style:italic")
        if upper:
            st.append("text-transform:uppercase")
        self.parts.append(f'<p class="el" style="{";".join(st)}">{html}</p>')

    def photo(self, x, y, w, h, bg, fg, label):
        uri = placeholder(int(w * self.k), int(h * self.k), bg, fg, label)
        self.parts.append(
            f'<img class="el" alt="Photo placeholder: {label.replace(chr(10), " ")}" '
            f'src="{uri}" style="left:{self.px(x)};top:{self.px(y)};'
            f'width:{self.px(w)};height:{self.px(h)};object-fit:cover">')

    def avatar(self, x, y, d, ring, letter_color):
        """The T avatar: a filled circle with an Instrument Serif T."""
        self.box(x, y, d, d, fill=ring, radius="50%")
        self.text(x, y + d * 0.13, d, "T", SERIF, d * 0.66, letter_color,
                  lh=1.0, align="center")

    def html(self):
        return (f'<div class="slide" data-name="{self.name}" '
                f'data-canvas-width="{self.w}" data-canvas-height="{self.h}" '
                f'style="width:{self.w}px;height:{self.h}px;'
                f'background-color:{self.bg}">\n  '
                + "\n  ".join(self.parts) + "\n</div>")


def document(title, pages):
    w, h = pages[0].w, pages[0].h
    css = (
        "*{margin:0;padding:0;box-sizing:border-box}"
        "body{background:#d9d9d9}"
        ".slide{position:relative;overflow:hidden;margin:0 auto 40px}"
        ".el{position:absolute;margin:0}"
        "i,em{font-style:italic}"
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{title}</title>
<meta name="hz:slide-selector" content=".slide">
<meta name="hz:canvas-width" content="{w}">
<meta name="hz:canvas-height" content="{h}">
{FONT_LINK}
<style>{css}</style>
</head>
<body>
{chr(10).join(p.html() for p in pages)}
</body>
</html>
"""


# --------------------------------------------------------------------------
# Shared marks
# --------------------------------------------------------------------------
def pj_lockup(p, x, y, scale, ink, accent_line=True):
    """'The Turnover' + spaced CREATIVE + tagline, as in the style scape."""
    p.text(x, y, 900 * scale, "The Turnover", SERIF, 120 * scale, ink, lh=1.0)
    p.text(x + 4 * scale, y + 128 * scale, 600 * scale, "CREATIVE", MONO,
           20 * scale, ink, ls=0.45)
    if accent_line:
        p.text(x + 12 * scale, y + 172 * scale, 900 * scale, TAGLINE, MONO,
               15 * scale, ink, ls=0.18)


def footer(p, y, color, left=HANDLE_UP, right="PACIFIC NORTHWEST", m=72,
           size=20, rule=None):
    if rule:
        p.rule(m, y - 22, p.w / p.k - 2 * m, rule, 2)
    p.text(m, y, 600, left, MONO, size, color, ls=0.12)
    p.text(p.w / p.k - m - 600, y, 600, right, MONO, size, color, ls=0.12,
           align="right")


# ==========================================================================
# 01 FEED POSTS 4:5 (1080 x 1350)
# ==========================================================================
def feed_pages():
    W, H, M = 1080, 1350, 72
    pages = []

    # ---- A1 Platform Journal: feature photo post -------------------------
    p = Page(W, H, PJ["newsprint"], "A1 Platform Journal - Feature")
    p.text(M, 58, 600, f"THE TURNOVER CREATIVE {DOT} FEATURE", MONO, 20,
           PJ["ink"], ls=0.14)
    p.text(W - M - 400, 58, 400, "NO. 07", MONO, 20, PJ["ink"], ls=0.14,
           align="right")
    p.rule(M, 100, W - 2 * M, PJ["ink"], 2)
    p.photo(M, 128, W - 2 * M, 780, "#2a2a2a", "#bdbdbd",
            "YOUR PHOTO · BLACK & WHITE\nreplace image")
    p.text(M, 940, W - 2 * M, "Waiting is part<br>of the <i>story.</i>", SERIF,
           104, PJ["ink"], lh=0.98)
    p.text(M, 1162, 760,
           "Lifter Name, Club Name — 64 kg. Four minutes to the snatch "
           "opener, then 92 kg on the first attempt.", SANS, 24, PJ["ink"],
           lh=1.4)
    footer(p, 1280, PJ["ink"], rule=PJ["chalk"])
    pages.append(p)

    # ---- A2 Platform Journal: result card --------------------------------
    p = Page(W, H, PJ["newsprint"], "A2 Platform Journal - Result")
    p.text(M, 58, 900, f"RESULTS {DOT} MEET NAME {DOT} 14.03.27", MONO, 20,
           PJ["ink"], ls=0.14)
    p.rule(M, 100, W - 2 * M, PJ["ink"], 2)
    p.photo(W - M - 380, 140, 380, 480, "#2a2a2a", "#bdbdbd",
            "PORTRAIT\nreplace image")
    p.text(M, 140, 520, "Lifter<br><i>Name</i>", SERIF, 132, PJ["ink"], lh=0.95)
    p.text(M, 420, 520, f"CLUB NAME {DOT} 64 KG", MONO, 22, PJ["ink"], ls=0.14)
    p.text(M, 470, 500,
           "First national total. Six for six, and a 4 kg PR in the clean "
           "& jerk.", SANS, 24, PJ["ink"], lh=1.4)
    p.rule(M, 680, W - 2 * M, PJ["chalk"], 2)
    for i, (lab, val) in enumerate([("SN", "102"), ("CJ", "130")]):
        y = 712 + i * 128
        p.text(M, y, 300, lab, MONO, 92, PJ["ink"], lh=1.0)
        p.text(M + 300, y, W - 2 * M - 300, f"{val} kg", MONO, 92, PJ["ink"],
               lh=1.0, align="right")
        p.rule(M, y + 112, W - 2 * M, PJ["chalk"], 2)
    p.text(M, 980, 300, "TOT", MONO, 92, PJ["red"], lh=1.0)
    p.text(M + 300, 980, W - 2 * M - 300, "232 kg", MONO, 92, PJ["red"],
           lh=1.0, align="right")
    p.rule(M, 1092, W - 2 * M, PJ["ink"], 2)
    p.text(M, 1130, W - 2 * M,
           "Every lifter, <i>not just</i> the podium.", SERIF, 48, PJ["ink"])
    footer(p, 1280, PJ["ink"], right="FULL RESULTS IN BIO")
    pages.append(p)

    # ---- A3 Platform Journal: quote / manifesto --------------------------
    p = Page(W, H, PJ["ink"], "A3 Platform Journal - Quote")
    p.text(M, 58, 700, f"THE TURNOVER CREATIVE {DOT} FIELD NOTES", MONO, 20,
           PJ["newsprint"], ls=0.14)
    p.rule(M, 100, W - 2 * M, PJ["newsprint"], 2)
    p.text(M, 300, W - 2 * M,
           "Every lifter,<br><i>not just</i><br>the podium.", SERIF, 168,
           PJ["newsprint"], lh=0.95)
    p.text(M, 860, 640,
           "Meet coverage, features and results from Olympic-style "
           "weightlifting across the Pacific Northwest.", SANS, 28,
           PJ["newsprint"], lh=1.45)
    p.avatar(M, 1110, 110, PJ["newsprint"], PJ["ink"])
    p.text(M + 140, 1126, 700, "Follow along", SERIF, 44, PJ["newsprint"])
    p.text(M + 140, 1182, 700, HANDLE_UP, MONO, 20, PJ["chalk"], ls=0.14)
    pages.append(p)

    # ---- B1 Warm-Up Room: session hype -----------------------------------
    p = Page(W, H, WU["black"], "B1 Warm-Up Room - Hype")
    p.photo(0, 0, W, 820, "#3a3a3a", "#d0d0d0",
            "YOUR PHOTO · PHOTOCOPY B&W\nreplace image")
    p.box(M, 780, 560, 70, fill=WU["pink"])
    p.text(M + 24, 799, 540, f"WARM-UP ROOM {DOT} FRI 10.30", MONO, 28,
           WU["black"], ls=0.08, weight=500)
    p.text(M, 880, W - 2 * M, "CLOCK IS<br>RUNNING.", COND, 210, WU["paper"],
           lh=0.86, weight=900)
    footer(p, 1280, WU["paper"], right="TAG US IN YOUR SESSION")
    pages.append(p)

    # ---- B2 Warm-Up Room: weekly schedule --------------------------------
    p = Page(W, H, WU["paper"], "B2 Warm-Up Room - Schedule")
    p.box(0, 0, W, 540, fill=WU["blue"])
    p.text(M, 64, 600, f"WARM-UP ROOM {DOT} WEEK 12", MONO, 22, WU["paper"],
           ls=0.14)
    p.text(M, 150, W - 2 * M, "THIS WEEK<br>IN THE ROOM.", COND, 150,
           WU["paper"], lh=0.86, weight=900)
    rows = [("MON 18.00", "TECHNIQUE"), ("WED 18.00", "STRENGTH"),
            ("FRI 10.30", "OPEN PLATFORM"), ("SAT 09.00", "MOCK MEET")]
    for i, (t, s) in enumerate(rows):
        y = 590 + i * 130
        p.text(M, y, 360, t, MONO, 40, WU["black"], lh=1.0, weight=500)
        p.text(M + 360, y - 8, W - 2 * M - 360, s, COND, 64, WU["black"],
               lh=1.0, weight=900, align="right")
        p.rule(M, y + 84, W - 2 * M, WU["black"], 3)
    p.box(M, 1150, 420, 64, fill=WU["pink"])
    p.text(M + 22, 1167, 400, "ALL LEVELS WELCOME", MONO, 26, WU["black"],
           ls=0.08, weight=500)
    footer(p, 1280, WU["black"], right="BOOK VIA LINK IN BIO")
    pages.append(p)

    # ---- B3 Warm-Up Room: PR stamp ---------------------------------------
    p = Page(W, H, WU["pink"], "B3 Warm-Up Room - PR")
    p.text(M, 64, 700, f"WARM-UP ROOM {DOT} PR BOARD", MONO, 22, WU["black"],
           ls=0.14)
    p.text(M, 130, W - 2 * M, "NEW<br>PR.", COND, 400, WU["black"], lh=0.82,
           weight=900)
    p.box(M, 830, 440, 380, border=(8, WU["black"]))
    p.text(M + 32, 860, 380, "SNATCH", MONO, 28, WU["black"], ls=0.14,
           weight=500)
    p.text(M + 32, 910, 380, "85 kg", COND, 150, WU["black"], lh=1.0,
           weight=900)
    p.text(M + 32, 1080, 380, "+3 KG<br>LIFTER NAME", MONO, 28, WU["black"],
           lh=1.35, ls=0.08, weight=500)
    p.photo(560, 830, W - M - 560, 380, "#7a2a5c", "#ffd1ea",
            "PINK DUOTONE\nreplace image")
    footer(p, 1280, WU["black"], right="NEXT ONE FRIDAY")
    pages.append(p)

    # ---- C1 Club Heritage: milestone -------------------------------------
    p = Page(W, H, CH["green"], "C1 Club Heritage - Milestone")
    p.text(M, 70, W - 2 * M, f"CLUB NAME {DOT} EST. 2016", GRAD, 28,
           CH["gold"], ls=0.12, align="center")
    p.rule(M + 300, 126, W - 2 * M - 600, CH["gold"], 2)
    p.text(M, 170, W - 2 * M, "Ten years<br>on the platform.", SERIF, 120,
           CH["cream"], lh=0.98, italic=True, align="center")
    p.box(M + 60, 450, W - 2 * M - 120, 640, border=(4, CH["gold"]))
    p.photo(M + 76, 466, W - 2 * M - 152, 608, "#4a3a28", "#e8d6b0",
            "YOUR PHOTO · WARM 35 MM COLOUR\nreplace image")
    p.text(M, 1130, W - 2 * M,
           "A decade of Thursday nights, first meets and club records. "
           "Thank you to every lifter who walked in.", SANS, 26, CH["cream"],
           lh=1.45, align="center")
    footer(p, 1280, CH["gold"])
    pages.append(p)

    # ---- C2 Club Heritage: from the archive ------------------------------
    p = Page(W, H, CH["cream"], "C2 Club Heritage - Archive")
    p.text(M, 70, 700, "FROM THE ARCHIVE", GRAD, 30, CH["oxblood"], ls=0.12)
    p.text(W - M - 300, 74, 300, "NO. 03", MONO, 22, CH["oxblood"], ls=0.14,
           align="right")
    p.rule(M, 124, W - 2 * M, CH["oxblood"], 2)
    p.box(M, 160, W - 2 * M, 820, border=(4, CH["gold"]))
    p.photo(M + 16, 176, W - 2 * M - 32, 788, "#4a3a28", "#e8d6b0",
            "ARCHIVE PHOTO · WARM 35 MM\nreplace image")
    p.text(M, 1012, W - 2 * M, "The 2019 Club Championships.", SERIF, 76,
           CH["green"], lh=1.0, italic=True)
    p.text(M, 1110, 800,
           "Twelve lifters, one platform, and the first club record board. "
           "Know someone in this photo? Tag them.", SANS, 24, CH["green"],
           lh=1.45)
    footer(p, 1280, CH["oxblood"], right="SHARE YOUR CLUB PHOTOS")
    pages.append(p)

    # ---- C3 Club Heritage: member spotlight ------------------------------
    p = Page(W, H, CH["cream"], "C3 Club Heritage - Member")
    p.box(0, 0, W, 150, fill=CH["oxblood"])
    p.text(M, 56, W - 2 * M, "MEMBER SPOTLIGHT", GRAD, 40, CH["cream"],
           ls=0.12, align="center")
    p.box(M, 210, 460, 620, border=(4, CH["gold"]))
    p.photo(M + 14, 224, 432, 592, "#4a3a28", "#e8d6b0",
            "PORTRAIT\nreplace image")
    p.text(580, 220, W - M - 580, "Member<br>Name", SERIF, 104, CH["green"],
           lh=0.95, italic=True)
    rows = [("JOINED", "2022"), ("WEIGHT CLASS", "71 KG"),
            ("BEST TOTAL", "180 KG"), ("FAVOURITE LIFT", "CLEAN & JERK")]
    for i, (a, b) in enumerate(rows):
        y = 480 + i * 88
        p.text(580, y, 300, a, GRAD, 18, CH["oxblood"], ls=0.1)
        p.text(580, y + 30, W - M - 580, b, MONO, 28, CH["green"])
        p.rule(580, y + 74, W - M - 580, CH["gold"], 2)
    p.text(M, 920, W - 2 * M,
           "“I came for one class and stayed for the people. "
           "Thursday nights are the best part of my week.”", SERIF, 56,
           CH["green"], lh=1.1, italic=True)
    p.text(M, 1110, W - 2 * M, "New lifters welcome — club night every "
           "Thursday, 19.00.", SANS, 26, CH["green"], lh=1.4)
    footer(p, 1280, CH["oxblood"], right="CLUB NAME")
    pages.append(p)
    return pages


# ==========================================================================
# 02 STORIES + REEL COVERS 9:16 (1080 x 1920)
# Safe area: keep key text between y=250 and y=1580 (Instagram UI).
# Reel covers: key text inside the centre 1080 x 1440 (grid crop 3:4).
# ==========================================================================
def story_pages():
    W, H, M = 1080, 1920, 80
    pages = []

    # ---- A Platform Journal: meet coverage story -------------------------
    p = Page(W, H, PJ["newsprint"], "A Story - Live from the platform")
    p.photo(0, 0, W, 1080, "#2a2a2a", "#bdbdbd",
            "MEET PHOTO · NATURAL COLOUR\nreplace image")
    p.text(M, 1130, W - 2 * M, f"LIVE FROM THE PLATFORM {DOT} DAY ONE",
           MONO, 24, PJ["ink"], ls=0.14)
    p.rule(M, 1176, W - 2 * M, PJ["ink"], 2)
    p.text(M, 1210, W - 2 * M, "Meet Name<br><i>Open 2027.</i>", SERIF, 132,
           PJ["ink"], lh=0.95)
    p.text(M, 1480, W - 2 * M,
           "Session B starts 13.00. Every flight, every lifter.", SANS, 30,
           PJ["ink"], lh=1.4)
    p.text(M, 1560, W - 2 * M, f"FOLLOW {HANDLE_UP}", MONO, 24, PJ["red"],
           ls=0.14, weight=500)
    pages.append(p)

    # ---- A Platform Journal: reel cover ----------------------------------
    p = Page(W, H, PJ["ink"], "A Reel cover")
    p.photo(0, 0, W, H, "#2a2a2a", "#bdbdbd",
            "FULL-BLEED PHOTO · B&W\nreplace image")
    p.box(0, 760, W, 400, fill=PJ["newsprint"])
    p.text(M, 790, W - 2 * M, f"FEATURE {DOT} NO. 07", MONO, 22, PJ["ink"],
           ls=0.14, align="center")
    p.text(M, 840, W - 2 * M, "Every lifter,<br><i>not just</i> the podium.",
           SERIF, 112, PJ["ink"], lh=0.98, align="center")
    p.text(M, 1090, W - 2 * M, "THE TURNOVER CREATIVE", MONO, 20, PJ["ink"],
           ls=0.3, align="center")
    pages.append(p)

    # ---- B Warm-Up Room: session story -----------------------------------
    p = Page(W, H, WU["black"], "B Story - Session")
    p.box(M, 260, 520, 72, fill=WU["pink"])
    p.text(M + 24, 280, 500, f"WARM-UP ROOM {DOT} TODAY", MONO, 28,
           WU["black"], ls=0.08, weight=500)
    p.text(M, 370, W - 2 * M, "SESSION<br>STARTS<br>NOW.", COND, 240,
           WU["paper"], lh=0.84, weight=900)
    p.photo(M, 1010, W - 2 * M, 470, "#3a3a3a", "#d0d0d0",
            "PHOTOCOPY B&W\nreplace image")
    p.box(M, 1500, W - 2 * M, 80, fill=WU["blue"])
    p.text(M + 24, 1522, W - 2 * M - 48, "18.00 — OPEN PLATFORM", MONO,
           30, WU["paper"], ls=0.08, weight=500)
    p.text(M, 1620, W - 2 * M, HANDLE_UP, MONO, 22, WU["paper"], ls=0.14)
    pages.append(p)

    # ---- B Warm-Up Room: reel cover --------------------------------------
    p = Page(W, H, WU["black"], "B Reel cover")
    p.photo(0, 0, W, H, "#3a3a3a", "#d0d0d0",
            "FULL-BLEED PHOTO · PHOTOCOPY B&W\nreplace image")
    p.box(0, 740, W, 440, fill=WU["blue"])
    p.text(M, 790, W - 2 * M, "CLOCK IS<br>RUNNING.", COND, 176, WU["paper"],
           lh=0.86, weight=900, align="center")
    p.box(W / 2 - 230, 1100, 460, 56, fill=WU["pink"])
    p.text(W / 2 - 230, 1112, 460, f"WARM-UP ROOM {DOT} EP. 04", MONO, 24,
           WU["black"], ls=0.08, weight=500, align="center")
    pages.append(p)

    # ---- C Club Heritage: club night story -------------------------------
    p = Page(W, H, CH["green"], "C Story - Club night")
    p.text(M, 270, W - 2 * M, f"CLUB NAME {DOT} EST. 2016", GRAD, 30,
           CH["gold"], ls=0.12, align="center")
    p.rule(W / 2 - 120, 330, 240, CH["gold"], 2)
    p.text(M, 370, W - 2 * M, "Club night<br>is back.", SERIF, 150,
           CH["cream"], lh=0.95, italic=True, align="center")
    p.box(M + 40, 720, W - 2 * M - 80, 640, border=(4, CH["gold"]))
    p.photo(M + 56, 736, W - 2 * M - 112, 608, "#4a3a28", "#e8d6b0",
            "WARM 35 MM COLOUR\nreplace image")
    p.text(M, 1400, W - 2 * M, "THURSDAYS · 19.00", GRAD, 40,
           CH["cream"], ls=0.08, align="center")
    p.text(M, 1470, W - 2 * M,
           "All levels. Bring a friend who has never lifted.", SANS, 30,
           CH["cream"], lh=1.4, align="center")
    p.text(M, 1580, W - 2 * M, HANDLE_UP, MONO, 22, CH["gold"], ls=0.14,
           align="center")
    pages.append(p)

    # ---- C Club Heritage: reel cover -------------------------------------
    p = Page(W, H, CH["green"], "C Reel cover")
    p.photo(0, 0, W, H, "#4a3a28", "#e8d6b0",
            "FULL-BLEED PHOTO · WARM 35 MM\nreplace image")
    p.box(M, 720, W - 2 * M, 480, fill=CH["cream"], border=(4, CH["gold"]))
    p.text(M + 40, 770, W - 2 * M - 80, "FROM THE ARCHIVE", GRAD, 28,
           CH["oxblood"], ls=0.12, align="center")
    p.text(M + 40, 830, W - 2 * M - 80, "Ten years<br>on the platform.",
           SERIF, 110, CH["green"], lh=0.98, italic=True, align="center")
    p.text(M + 40, 1100, W - 2 * M - 80, "CLUB NAME", GRAD, 24, CH["oxblood"],
           ls=0.12, align="center")
    pages.append(p)
    return pages


# ==========================================================================
# 03 POSTERS 11 x 17 in (3300 x 5100 px at 300 dpi; designed at 1100 x 1700)
# ==========================================================================
def poster_pages():
    K = 3.0
    W, H, M = 1100, 1700, 72
    pages = []

    # ---- A Platform Journal: meet poster ---------------------------------
    p = Page(int(W * K), int(H * K), PJ["newsprint"],
             "A Poster - Meet", k=K)
    pj_lockup(p, M, 60, 0.62, PJ["ink"])
    p.text(W - M - 360, 70, 360, f"MEET POSTER<br>NO. 01", MONO, 14,
           PJ["ink"], ls=0.14, align="right", lh=1.5)
    p.rule(M, 200, W - 2 * M, PJ["ink"], 2)
    p.text(M, 236, W - 2 * M, "Meet Name<br><i>Open 2027.</i>", SERIF, 168,
           PJ["ink"], lh=0.93)
    p.photo(M, 580, W - 2 * M, 640, "#2a2a2a", "#bdbdbd",
            "YOUR PHOTO · BLACK & WHITE\nreplace image")
    cells = [("DATE", "Sat 14 March 2027"), ("VENUE", "Venue Name, City"),
             ("WEIGH-IN", "07.00 — 08.00"), ("ENTRY", "Closes 28 Feb")]
    for i, (a, b) in enumerate(cells):
        cx = M + (i % 2) * ((W - 2 * M) / 2)
        cy = 1260 + (i // 2) * 120
        p.rule(cx, cy, (W - 2 * M) / 2 - 24, PJ["chalk"], 2)
        p.text(cx, cy + 16, 440, a, MONO, 14, PJ["ink"], ls=0.18)
        p.text(cx, cy + 42, 460, b, SERIF, 44, PJ["ink"], lh=1.0)
    p.rule(M, 1520, W - 2 * M, PJ["ink"], 2)
    p.text(M, 1544, 700, "Every lifter, <i>not just</i> the podium.", SERIF,
           40, PJ["ink"])
    p.text(M, 1610, 700, f"REGISTER: LINK IN BIO {DOT} {HANDLE_UP}", MONO, 15,
           PJ["red"], ls=0.14, weight=500)
    p.avatar(W - M - 90, 1540, 90, PJ["ink"], PJ["newsprint"])
    pages.append(p)

    # ---- B Warm-Up Room: open platform poster ----------------------------
    p = Page(int(W * K), int(H * K), WU["black"], "B Poster - Open platform",
             k=K)
    p.box(M, 70, 520, 64, fill=WU["pink"])
    p.text(M + 22, 87, 500, f"WARM-UP ROOM {DOT} OPEN PLATFORM", MONO, 22,
           WU["black"], ls=0.08, weight=500)
    p.text(M, 170, W - 2 * M, "OPEN<br>PLATFORM.", COND, 190, WU["paper"],
           lh=0.86, weight=900)
    p.photo(M, 540, W - 2 * M, 680, "#3a3a3a", "#d0d0d0",
            "YOUR PHOTO · PHOTOCOPY B&W\nreplace image")
    p.box(M, 1250, W - 2 * M, 300, fill=WU["blue"])
    rows = [("EVERY FRIDAY", "10.30 — 13.00"),
            ("WHERE", "Gym Name, City"), ("WHO", "All levels, all ages")]
    for i, (a, b) in enumerate(rows):
        y = 1280 + i * 86
        p.text(M + 32, y + 10, 340, a, MONO, 22, WU["paper"], ls=0.12,
               weight=500)
        p.text(M + 380, y, W - 2 * M - 412, b, COND, 52, WU["paper"],
               lh=1.0, weight=900, align="right", upper=True)
    p.text(M, 1600, 700, HANDLE_UP, MONO, 20, WU["paper"], ls=0.14)
    p.text(W - M - 400, 1600, 400, "BRING A FRIEND", MONO, 20, WU["pink"],
           ls=0.14, align="right", weight=500)
    pages.append(p)

    # ---- C Club Heritage: anniversary / open day poster ------------------
    p = Page(int(W * K), int(H * K), CH["green"], "C Poster - Open day", k=K)
    p.box(40, 40, W - 80, H - 80, border=(3, CH["gold"]))
    p.text(M, 110, W - 2 * M, f"CLUB NAME {DOT} EST. 2016", GRAD, 34,
           CH["gold"], ls=0.12, align="center")
    p.rule(W / 2 - 160, 172, 320, CH["gold"], 2)
    p.text(M, 210, W - 2 * M, "Ten years<br>on the platform.", SERIF, 136,
           CH["cream"], lh=0.95, italic=True, align="center")
    p.box(M + 80, 520, W - 2 * M - 160, 640, border=(4, CH["gold"]))
    p.photo(M + 96, 536, W - 2 * M - 192, 608, "#4a3a28", "#e8d6b0",
            "YOUR PHOTO · WARM 35 MM COLOUR\nreplace image")
    p.text(M, 1210, W - 2 * M, "CLUB OPEN DAY", GRAD, 56, CH["gold"],
           ls=0.08, align="center")
    p.text(M, 1300, W - 2 * M,
           "Saturday 6 June 2027 · 10.00 — 15.00<br>"
           "Club Address, City", SERIF, 52, CH["cream"], lh=1.2,
           align="center")
    p.text(M + 120, 1460, W - 2 * M - 240,
           "Try the lifts with our coaches, see the club record board and "
           "meet ten years of members.", SANS, 24, CH["cream"], lh=1.5,
           align="center")
    p.text(M, 1580, W - 2 * M, HANDLE_UP, MONO, 18, CH["gold"], ls=0.14,
           align="center")
    pages.append(p)
    return pages


# ==========================================================================
# 04 BRAND GUIDE (1920 x 1080)
# ==========================================================================
def swatch(p, x, y, w, color, name, hexv, note, text_color, border=None):
    p.box(x, y, w, 120, fill=color, border=(2, border) if border else None)
    p.text(x, y + 136, w, f"{name} {hexv}", MONO, 16, text_color, ls=0.04)
    p.text(x, y + 162, w, note, MONO, 16, text_color, ls=0.04)


def guide_pages():
    W, H, M = 1920, 1080, 96
    pages = []

    # ---- Overview ---------------------------------------------------------
    p = Page(W, H, PJ["newsprint"], "Guide 0 - Overview")
    p.text(M, 70, 900, "BRAND PACK · 2027 · HOW TO USE IT", MONO, 18,
           PJ["ink"], ls=0.16)
    pj_lockup(p, M, 110, 0.8, PJ["ink"])
    p.rule(M, 290, W - 2 * M, PJ["ink"], 2)
    cols = [
        ("A", "Platform Journal", PJ["newsprint"], PJ["ink"], PJ["red"],
         "Results, meet coverage, features and long captions.",
         "Use it to tell the story of a lifter or a meet. Calm, editorial, "
         "plenty of space. Signal red only on totals and results."),
        ("B", "Warm-Up Room", WU["black"], WU["paper"], WU["pink"],
         "Training sessions, schedules, PRs and hype.",
         "Use it to get people into the room. Loud condensed type, one "
         "pink tag per post, blue blocks for times."),
        ("C", "Club Heritage", CH["green"], CH["cream"], CH["gold"],
         "Club history, milestones, members and archive photos.",
         "Use it to celebrate the club and its people. Serif italic, gold "
         "frames, warm 35 mm colour."),
    ]
    cw = (W - 2 * M - 2 * 48) / 3
    for i, (letter, name, bg, fg, acc, when, how) in enumerate(cols):
        x = M + i * (cw + 48)
        p.box(x, 330, cw, 140, fill=bg, border=(2, PJ["chalk"]))
        p.text(x + 28, 352, cw - 56, f"DIRECTION {letter}", MONO, 16, acc,
               ls=0.16)
        p.text(x + 28, 384, cw - 56, name, SERIF, 56, fg, lh=1.0)
        p.text(x, 500, cw, "WHEN", MONO, 15, PJ["ink"], ls=0.16)
        p.text(x, 528, cw, when, SERIF, 34, PJ["ink"], lh=1.1)
        p.text(x, 640, cw, how, SANS, 20, PJ["ink"], lh=1.5)
    p.rule(M, 800, W - 2 * M, PJ["chalk"], 2)
    rules = [
        ("ONE LOOK PER POST", "Never mix directions on one page."),
        ("OUR PHOTOS ONLY", "Your own photography. No stock, no AI images."),
        ("SAFE AREAS", "Stories: text between 250 and 1580 px from the top."),
        ("ALWAYS SIGN OFF", f"Every post ends with {HANDLE}."),
    ]
    rw = (W - 2 * M - 3 * 40) / 4
    for i, (a, b) in enumerate(rules):
        x = M + i * (rw + 40)
        p.text(x, 830, rw, a, MONO, 16, PJ["red"] if i == 0 else PJ["ink"],
               ls=0.16, weight=500)
        p.text(x, 862, rw, b, SANS, 20, PJ["ink"], lh=1.45)
    p.text(M, 1000, 900, "Every lifter, <i>not just</i> the podium.", SERIF,
           34, PJ["ink"])
    p.text(W - M - 600, 1012, 600, HANDLE_UP, MONO, 16, PJ["ink"], ls=0.16,
           align="right")
    pages.append(p)

    # ---- A Platform Journal ----------------------------------------------
    p = Page(W, H, PJ["newsprint"], "Guide A - Platform Journal")
    p.text(M, 60, 800, "DIRECTION A · STYLE SCAPE", MONO, 16, PJ["ink"],
           ls=0.16)
    p.text(M, 86, 1000, "Platform Journal", SERIF, 84, PJ["ink"], lh=1.0)
    p.text(W - M - 600, 120, 600, "Editorial print · results · features",
           MONO, 16, PJ["ink"], ls=0.08, align="right")
    p.rule(M, 190, W - 2 * M, PJ["ink"], 2)
    p.box(M, 220, 1060, 300, border=(2, PJ["chalk"]))
    pj_lockup(p, M + 160, 280, 0.9, PJ["ink"])
    p.box(M + 1100, 220, W - 2 * M - 1100, 300, fill=PJ["ink"])
    p.avatar(M + 1180, 290, 130, PJ["newsprint"], PJ["ink"])
    p.avatar(M + 1350, 335, 44, PJ["newsprint"], PJ["ink"])
    p.text(M + 1180, 450, 500, "AVATAR AT 110 PX AND 40 PX", MONO, 14,
           PJ["chalk"], ls=0.14)
    p.text(M, 560, 500, "DISPLAY · INSTRUMENT SERIF", MONO, 14, PJ["ink"],
           ls=0.14)
    p.text(M, 590, 520, "Every lifter, <i>not<br>just</i> the podium.", SERIF,
           58, PJ["ink"], lh=1.0)
    p.text(M + 600, 560, 500, "TEXT · IBM PLEX SANS", MONO, 14, PJ["ink"],
           ls=0.14)
    p.text(M + 600, 590, 520,
           "Captions lead with the person and the moment, then the numbers. "
           "Plain, specific, unhurried.", SANS, 22, PJ["ink"], lh=1.5)
    p.text(M + 1200, 560, 500, "NUMERALS · IBM PLEX MONO", MONO, 14,
           PJ["ink"], ls=0.14)
    p.text(M + 1200, 590, 500, "SN 102 kg<br>CJ 130 kg<br>TOT 232 kg", MONO,
           36, PJ["ink"], lh=1.3)
    sw = (W - 2 * M - 3 * 32) / 4
    for i, (c, n, hx, note, b) in enumerate([
            (PJ["newsprint"], "Newsprint", "#F2EFE8", "Page. Ink on it 16.4:1",
             PJ["chalk"]),
            (PJ["ink"], "Ink", "#111111", "Type, rules, dark pages", None),
            (PJ["chalk"], "Chalk", "#C9C6BF", "Rules and borders only", None),
            (PJ["red"], "Signal red", "#B5281F", "Results only", None)]):
        swatch(p, M + i * (sw + 32), 790, sw, c, n, hx, note, PJ["ink"], b)
    pages.append(p)

    # ---- B Warm-Up Room ----------------------------------------------------
    p = Page(W, H, WU["black"], "Guide B - Warm-Up Room")
    p.text(M, 60, 800, "DIRECTION B · STYLE SCAPE", MONO, 16,
           WU["paper"], ls=0.16)
    p.text(M, 86, 1200, "WARM-UP ROOM", COND, 96, WU["paper"], lh=1.0,
           weight=900)
    p.text(W - M - 600, 120, 600, "Training · sessions · PRs · hype",
           MONO, 16, WU["paper"], ls=0.08, align="right")
    p.rule(M, 200, W - 2 * M, WU["paper"], 2)
    p.text(M, 240, 500, "DISPLAY · ARCHIVO CONDENSED BLACK", MONO, 14,
           WU["pink"], ls=0.14)
    p.text(M, 270, 900, "CLOCK IS<br>RUNNING.", COND, 170, WU["paper"],
           lh=0.86, weight=900)
    p.text(M + 1000, 240, 600, "TAGS + TIMES · IBM PLEX MONO", MONO, 14,
           WU["pink"], ls=0.14)
    p.box(M + 1000, 280, 520, 64, fill=WU["pink"])
    p.text(M + 1022, 297, 500, f"WARM-UP ROOM {DOT} FRI 10.30", MONO, 26,
           WU["black"], ls=0.08, weight=500)
    p.box(M + 1000, 370, 520, 64, fill=WU["blue"])
    p.text(M + 1022, 387, 500, "18.00 — OPEN PLATFORM", MONO, 26,
           WU["paper"], ls=0.08, weight=500)
    p.text(M + 1000, 470, 620,
           "Motion: steps at 12 fps with hold keys — slam, wobble, stamp, "
           "2-frame paper flash.<br>Photos: photocopy black & white or pink "
           "duotone.<br>One pink tag per post. Headlines end with a full "
           "stop.", SANS, 20, WU["paper"], lh=1.55)
    sw = (W - 2 * M - 3 * 32) / 4
    for i, (c, n, hx, note, b) in enumerate([
            (WU["black"], "Black", "#0E0E0E", "Main background", WU["paper"]),
            (WU["paper"], "Paper", "#EDEDE8", "Headlines, light pages", None),
            (WU["pink"], "Pink", "#FF48B0", "Tags and PR pages", None),
            (WU["blue"], "Blue", "#0047BB", "Time and schedule blocks",
             None)]):
        swatch(p, M + i * (sw + 32), 720, sw, c, n, hx, note, WU["paper"], b)
    pages.append(p)

    # ---- C Club Heritage --------------------------------------------------
    p = Page(W, H, CH["green"], "Guide C - Club Heritage")
    p.text(M, 60, 800, "DIRECTION C · STYLE SCAPE", MONO, 16, CH["gold"],
           ls=0.16)
    p.text(M, 86, 1200, "Club Heritage", SERIF, 84, CH["cream"], lh=1.0,
           italic=True)
    p.text(W - M - 700, 120, 700,
           "Club history · milestones · members", MONO, 16, CH["cream"],
           ls=0.08, align="right")
    p.rule(M, 190, W - 2 * M, CH["gold"], 2)
    p.text(M, 230, 500, "DISPLAY · INSTRUMENT SERIF ITALIC", MONO, 14,
           CH["gold"], ls=0.14)
    p.text(M, 260, 800, "Ten years<br>on the platform.", SERIF, 96,
           CH["cream"], lh=0.98, italic=True)
    p.text(M + 860, 230, 500, "LABELS · GRADUATE", MONO, 14, CH["gold"],
           ls=0.14)
    p.text(M + 860, 262, 800, f"CLUB NAME {DOT} EST. 2016", GRAD, 40,
           CH["gold"], ls=0.12)
    p.text(M + 860, 340, 500, "TEXT · IBM PLEX SANS", MONO, 14,
           CH["gold"], ls=0.14)
    p.text(M + 860, 372, 860,
           "Warm and grateful. Name the people, the year and the place. "
           "Motion is slow: an eased rise and fade.<br>Photos: warm 35 mm "
           "colour inside a thin gold frame.", SANS, 22, CH["cream"], lh=1.55)
    p.box(M, 560, W - 2 * M, 2, fill=CH["gold"])
    p.text(M, 860, 600, "PHOTO RULES", GRAD, 26, CH["gold"], ls=0.12)
    p.text(M, 910, W - 2 * M,
           "Warm 35 mm colour, never black & white. \u00b7 People first: "
           "faces, hands, the club room. \u00b7 Always inside a thin gold "
           "frame. \u00b7 Name the year and the place in the caption.",
           SANS, 22, CH["cream"], lh=1.6)
    sw = (W - 2 * M - 3 * 32) / 4
    for i, (c, n, hx, note, b) in enumerate([
            (CH["green"], "Green", "#1F3A2E", "Main background", CH["gold"]),
            (CH["cream"], "Cream", "#EDE6D6", "Headlines, light pages", None),
            (CH["gold"], "Gold", "#C9A46A", "Frames, labels, rules", None),
            (CH["oxblood"], "Oxblood", "#6B1E1E", "Bands and labels on cream",
             CH["gold"])]):
        swatch(p, M + i * (sw + 32), 600, sw, c, n, hx, note, CH["cream"], b)
    pages.append(p)
    return pages


DOCS = [
    ("01-feed-posts-4x5.html", "Turnover Feed Posts", feed_pages),
    ("02-stories-9x16.html", "Turnover Stories", story_pages),
    ("03-posters-11x17.html", "Turnover Posters", poster_pages),
    ("04-brand-guide.html", "Turnover Brand Guide", guide_pages),
]

if __name__ == "__main__":
    for fname, title, fn in DOCS:
        path = os.path.join(OUT, fname)
        with open(path, "w", encoding="utf-8") as f:
            f.write(document(title, fn()))
        print(f"wrote {path} ({os.path.getsize(path) // 1024} KB)")
