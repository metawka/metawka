import base64
import datetime
import hashlib
import json
import math
import os
import subprocess
import sys
import urllib.request
from html import escape
from pathlib import Path

ROOT = Path(__file__).parent
OUT = ROOT / "assets"
USER = "metawka"
W = 840

PALETTE = json.loads((ROOT / "data/palette.json").read_text(encoding="utf-8"))
ICONS = json.loads((ROOT / "data/icons.json").read_text(encoding="utf-8"))
METRICS = json.loads((ROOT / "data/metrics.json").read_text(encoding="utf-8"))
FONT = base64.b64encode((ROOT / "fonts/GoogleSansFlex-subset.woff2").read_bytes()).decode()
FONT_CYR = base64.b64encode((ROOT / "fonts/RobotoFlex-cyrillic.woff2").read_bytes()).decode()

SHAPES = ["cookie", "clover", "sunny", "flower"]

ICON_RULES = [
    (("zip", "archive", "7-zip", "rar"), "folder_zip"),
    (("music", "audio", "spotify", "player", "sound"), "music_note"),
    (("dictat", "speech", "voice", "whisper", "mic"), "mic"),
    (("tracker", "screen time", "activity", "monitor", "stats"), "monitoring"),
    (("discord",), "brand:discord"),
    (("game", "minecraft", "mod "), "sports_esports"),
    (("site", "website", "web ", "landing", "portfolio"), "language"),
    (("launcher", "installer"), "deployed_code"),
    (("theme", "design", "ui kit", "palette"), "palette"),
    (("terminal", "cli", "shell", "dotfiles", "hyprland"), "terminal"),
]

LANG_ICONS = {
    "Rust": "brand:rust",
    "Python": "brand:python",
    "TypeScript": "brand:typescript",
    "JavaScript": "code",
    "C#": "desktop_windows",
    "Java": "brand:openjdk",
}

STACK = [
    ("Main", [("brand:typescript", "TypeScript"), ("brand:python", "Python"), ("brand:rust", "Rust"), ("widgets", "WinUI 3")]),
    ("Also", [("brand:dotnet", "C#"), ("brand:nextdotjs", "Next.js"), ("brand:react", "React"), ("brand:electron", "Electron"), ("brand:openjdk", "Java")]),
    ("Tools", [("brand:git", "Git"), ("brand:githubactions", "GitHub Actions"), ("brand:hyprland", "Hyprland"), ("brand:discord", "Discord")]),
]

ABOUT = [
    ("person", "16 y.o. developer"),
    ("code", "Mostly frontend, a bit of backend"),
    ("palette", "Web, frontend and UI design"),
    ("desktop_windows", "Sometimes small Windows utilities, like the ones below"),
]

BUTTONS = [
    ("site", "metawka.xyz", "language", "filled"),
    ("repos", "All repositories", "book_2", "tonal"),
]


# Helpers
def text_width(s, size, weight=400):
    table = METRICS[str(min((400, 500, 600, 700), key=lambda w: abs(w - weight)))]
    return sum(table.get(c, 0.55) for c in s) * size


def wrap(s, size, width, weight=400, lines=2):
    out, cur = [], ""
    for word in s.split():
        trial = f"{cur} {word}".strip()
        if text_width(trial, size, weight) <= width:
            cur = trial
        else:
            out.append(cur)
            cur = word
    out.append(cur)
    if len(out) > lines:
        out = out[:lines]
        while text_width(out[-1] + "…", size, weight) > width:
            out[-1] = out[-1].rsplit(" ", 1)[0]
        out[-1] += "…"
    return out


def mix(a, b, t):
    pa = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    pb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(pa, pb))


def shape(kind, cx, cy, r):
    n, a, sharp = {
        "cookie": (9, 0.07, 1.0),
        "cookie12": (12, 0.05, 1.0),
        "clover": (4, 0.2, 1.0),
        "sunny": (8, 0.1, 2.2),
        "flower": (8, 0.16, 1.0),
        "pill": (2, 0.0, 1.0),
    }[kind]
    pts = []
    steps = 180
    for i in range(steps):
        t = 2 * math.pi * i / steps
        wave = math.cos(n * t)
        wave = math.copysign(abs(wave) ** (1 / sharp), wave)
        rr = r * (1 - a + a * wave)
        pts.append((cx + rr * math.cos(t - math.pi / 2), cy + rr * math.sin(t - math.pi / 2)))
    return "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in pts) + " Z"


def icon(name, x, y, size, fill):
    if name.startswith("brand:"):
        d = ICONS["brand"][name[6:]]
        s = size / 24
        return f'<path d="{d}" fill="{fill}" transform="translate({x:.1f} {y:.1f}) scale({s:.4f})"/>'
    sym = ICONS["symbol"][name]
    vx, vy, vw, vh = [float(v) for v in sym["vb"].split()]
    s = size / vw
    return f'<path d="{sym["d"]}" fill="{fill}" transform="translate({x - vx * s:.1f} {y - vy * s:.1f}) scale({s:.4f})"/>'


def txt(x, y, s, size, fill, weight=400, cls="", delay=None, anchor="start", extra=""):
    style = f"font-size:{size}px;font-weight:{weight};"
    if delay is not None:
        style += f"animation-delay:{delay:.2f}s;"
    c = f' class="{cls}"' if cls else ""
    return f'<text x="{x:.1f}" y="{y:.1f}" fill="{fill}" text-anchor="{anchor}" style="{style}"{c}{extra}>{escape(s)}</text>'


def svg(w, h, body, title):
    cyr = ""
    if any("\u0400" <= c <= "\u04ff" for c in body):
        cyr = f"@font-face{{font-family:R;src:url(data:font/woff2;base64,{FONT_CYR}) format('woff2');font-weight:400 800}}"
    css = f"""
@font-face{{font-family:G;src:url(data:font/woff2;base64,{FONT}) format('woff2');font-weight:400 800}}
{cyr}text{{font-family:G,R,'Google Sans','Segoe UI',Roboto,sans-serif;font-variation-settings:'ROND' 100}}
.up{{animation:up .8s cubic-bezier(.05,.7,.1,1) both}}
.pop{{transform-box:fill-box;transform-origin:center;animation:pop .6s cubic-bezier(.34,1.56,.64,1) both}}
.fade{{animation:fade .9s ease both}}
.spin{{transform-box:fill-box;transform-origin:center;animation:spin 40s linear infinite}}
.spin-r{{transform-box:fill-box;transform-origin:center;animation:spin 28s linear infinite reverse}}
.bob{{transform-box:fill-box;transform-origin:center;animation:bob 7s ease-in-out infinite}}
.breathe{{transform-box:fill-box;transform-origin:center;animation:breathe 6s ease-in-out infinite}}
.grow{{transform-box:fill-box;transform-origin:left center;animation:grow 1.1s cubic-bezier(.2,0,0,1) both}}
.wght{{animation:wght 1.6s cubic-bezier(.2,0,0,1) .2s both}}
.wave{{animation:wave 2.4s linear infinite}}
@keyframes up{{from{{opacity:0;transform:translateY(14px)}}to{{opacity:1;transform:none}}}}
@keyframes pop{{from{{opacity:0;transform:scale(.6)}}to{{opacity:1;transform:scale(1)}}}}
@keyframes fade{{from{{opacity:0}}to{{opacity:1}}}}
@keyframes spin{{to{{transform:rotate(360deg)}}}}
@keyframes bob{{0%,100%{{transform:translateY(0) rotate(0)}}50%{{transform:translateY(-10px) rotate(12deg)}}}}
@keyframes breathe{{0%,100%{{transform:scale(1)}}50%{{transform:scale(1.06)}}}}
@keyframes grow{{from{{transform:scaleX(0)}}to{{transform:scaleX(1)}}}}
@keyframes wght{{from{{font-variation-settings:'ROND' 100,'wght' 400}}to{{font-variation-settings:'ROND' 100,'wght' 760}}}}
@keyframes wave{{from{{transform:translateX(0)}}to{{transform:translateX(-48px)}}}}
@media (prefers-reduced-motion:reduce){{*{{animation:none!important}}}}
"""

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="{escape(title)}">'
        f"<title>{escape(title)}</title><style>{css}</style>{body}</svg>"
    )


def chip(x, y, label, p, ic=None, delay=0.0, h=36, size=15, style="outlined"):
    pad = 14
    iw = 18 if ic else 0
    gap = 8 if ic else 0
    w = pad * 2 + iw + gap + text_width(label, size, 500)
    if style == "tonal":
        bg = f'<rect x="{x}" y="{y}" width="{w:.1f}" height="{h}" rx="10" fill="{p["secondaryContainer"]}"/>'
        fg = p["onSecondaryContainer"]
    else:
        bg = f'<rect x="{x + .5}" y="{y + .5}" width="{w - 1:.1f}" height="{h - 1}" rx="10" fill="{p["surfaceContainerLow"]}" stroke="{p["outlineVariant"]}"/>'
        fg = p["onSurfaceVariant"]
    parts = [bg]
    if ic:
        parts.append(icon(ic, x + pad, y + (h - 18) / 2, 18, p["primary"]))
    parts.append(txt(x + pad + iw + gap, y + h / 2 + size * 0.36, label, size, fg, 500))
    return f'<g class="pop" style="animation-delay:{delay:.2f}s">{"".join(parts)}</g>', w


def avatar_data():
    try:
        req = urllib.request.Request(f"https://github.com/{USER}.png?size=320", headers={"User-Agent": "profile"})
        with urllib.request.urlopen(req, timeout=20) as r:
            kind = r.headers.get_content_type()
            return f"data:{kind};base64,{base64.b64encode(r.read()).decode()}"
    except Exception:
        return None


# Blocks
def hero(p, avatar):
    h = 300
    b = [f'<clipPath id="card"><rect width="{W}" height="{h}" rx="32"/></clipPath>']
    b.append(f'<rect width="{W}" height="{h}" rx="32" fill="{p["surfaceContainer"]}"/>')
    b.append('<g clip-path="url(#card)">')
    b.append(f'<path class="spin" d="{shape("flower", 780, 30, 150)}" fill="{p["primaryContainer"]}"/>')
    b.append(f'<path class="bob" d="{shape("clover", 690, 292, 62)}" fill="{p["tertiaryContainer"]}"/>')
    b.append(f'<path class="spin-r" d="{shape("sunny", 812, 236, 34)}" fill="{p["secondaryContainer"]}"/>')
    b.append("</g>")
    cx, cy = 150, 150
    b.append(f'<path class="spin" d="{shape("sunny", cx, cy, 112)}" fill="{p["primary"]}" opacity=".9"/>')
    b.append(f'<clipPath id="ava"><path d="{shape("cookie12", cx, cy, 98)}"/></clipPath>')
    b.append(f'<path d="{shape("cookie12", cx, cy, 102)}" fill="{p["surfaceContainer"]}"/>')
    if avatar:
        b.append(f'<g class="fade"><image href="{avatar}" x="{cx - 100}" y="{cy - 100}" width="200" height="200" clip-path="url(#ava)" preserveAspectRatio="xMidYMid slice"/></g>')
    else:
        b.append(f'<path d="{shape("cookie12", cx, cy, 98)}" fill="{p["primaryContainer"]}"/>')
    x = 294
    b.append(txt(x, 92, "Hi, I'm", 22, p["onSurfaceVariant"], 500, "up", 0.1))
    b.append(f'<g class="up" style="animation-delay:.2s">{txt(x - 3, 156, USER, 68, p["onSurface"], 400, "wght")}</g>')
    lines = wrap("Frontend developer and web designer. Sometimes I build small Windows utilities.", 19, 430, 400, 2)
    for i, line in enumerate(lines):
        b.append(txt(x, 194 + i * 26, line, 19, p["onSurfaceVariant"], 400, "up", 0.35 + i * 0.08))
    cx2 = x
    for i, (ic, label) in enumerate([("location_on", "KZ · Russia"), ("person", "he/her"), ("code", "TS · Python · Rust")]):
        g, w = chip(cx2, 236, label, p, ic, 0.6 + i * 0.1, style="tonal")
        b.append(g)
        cx2 += w + 8
    return svg(W, h, "".join(b), "Hi, I'm metawka")


def section_title(x, y, label, ic, p, delay=0.0):
    tile = f'<path class="pop" style="animation-delay:{delay:.2f}s" d="{shape("cookie", x + 20, y + 20, 20)}" fill="{p["primaryContainer"]}"/>'
    i = f'<g class="pop" style="animation-delay:{delay + .05:.2f}s">{icon(ic, x + 9, y + 9, 22, p["onPrimaryContainer"])}</g>'
    return tile + i + txt(x + 54, y + 28, label, 24, p["onSurface"], 600, "up", delay)


def about(p):
    row = 54
    h = 92 + row * len(ABOUT)
    b = [f'<rect width="{W}" height="{h}" rx="32" fill="{p["surfaceContainerLow"]}"/>']
    b.append(section_title(28, 26, "About me", "favorite", p))
    for i, (ic, label) in enumerate(ABOUT):
        y = 86 + i * row
        b.append(f'<g class="up" style="animation-delay:{0.15 + i * 0.1:.2f}s">')
        b.append(f'<rect x="28" y="{y}" width="{W - 56}" height="{row - 8}" rx="16" fill="{p["surfaceContainerHigh"]}"/>')
        b.append(f'<circle cx="54" cy="{y + (row - 8) / 2}" r="15" fill="{p["secondaryContainer"]}"/>')
        b.append(icon(ic, 45, y + (row - 8) / 2 - 9, 18, p["onSecondaryContainer"]))
        b.append(txt(82, y + (row - 8) / 2 + 6, label, 17, p["onSurface"], 500))
        b.append("</g>")
    return svg(W, h, "".join(b), "About me")


def stack(p):
    b = []
    y = 86
    d = 0.1
    groups = []
    for title, items in STACK:
        gy = y
        groups.append(txt(28, gy + 14, title.upper(), 12, p["onSurfaceVariant"], 600, "fade", d, extra=' letter-spacing="1.4"'))
        x = 28
        cy = gy + 26
        for ic, label in items:
            _, w = chip(0, 0, label, p, ic)
            if x + w > W - 28:
                x = 28
                cy += 44
            g, w = chip(x, cy, label, p, ic, d)
            groups.append(g)
            x += w + 8
            d += 0.05
        y = cy + 36 + 22
    h = y + 6
    b.append(f'<rect width="{W}" height="{h}" rx="32" fill="{p["surfaceContainerLow"]}"/>')
    b.append(section_title(28, 26, "Tech stack", "code", p))
    b.extend(groups)
    return svg(W, h, "".join(b), "Tech stack")


def pick_icon(pin):
    hay = f" {pin['name']} {pin['text']} {' '.join(pin['topics'])} ".lower().replace("-", " ")
    for keys, name in ICON_RULES:
        if any(k in hay for k in keys):
            return name
    return LANG_ICONS.get(pin["language"], "code")


def pin_tags(pin):
    tags = [pin["language"]] if pin["language"] else []
    hay = f"{pin['text']} {' '.join(pin['topics'])}".lower()
    if "winui" in hay and "WinUI 3" not in tags:
        tags.append("WinUI 3")
    return tags


def card(p, pin, index):
    w, h = 412, 232
    d0 = 0.08 * index
    proj = {
        "title": pin["name"],
        "text": pin["text"] or "No description yet.",
        "tags": pin_tags(pin),
        "icon": pick_icon(pin),
        "shape": SHAPES[index % len(SHAPES)],
        "fork": pin["fork"],
    }
    stars = pin["stars"]
    b = [f'<rect width="{w}" height="{h}" rx="28" fill="{p["surfaceContainerHigh"]}"/>']
    b.append(f'<g class="pop" style="animation-delay:{d0:.2f}s"><path class="spin" d="{shape(proj["shape"], 52, 52, 30)}" fill="{p["primaryContainer"]}"/></g>')
    b.append(f'<g class="pop" style="animation-delay:{d0 + .08:.2f}s">{icon(proj["icon"], 39, 39, 26, p["onPrimaryContainer"])}</g>')
    b.append(f'<circle cx="{w - 40}" cy="40" r="18" fill="{p["surfaceContainerHighest"]}"/>')
    b.append(icon("arrow_outward", w - 50, 30, 20, p["onSurfaceVariant"]))
    tx = 24
    b.append(txt(tx, 116, proj["title"], 23, p["onSurface"], 650, "up", d0 + 0.1))
    if proj.get("fork"):
        fw = text_width("Fork", 12, 600) + 18
        fx = tx + text_width(proj["title"], 23, 650) + 10
        b.append(f'<g class="pop" style="animation-delay:{d0 + .25:.2f}s"><rect x="{fx:.1f}" y="98" width="{fw:.1f}" height="22" rx="11" fill="{p["tertiaryContainer"]}"/>')
        b.append(txt(fx + fw / 2, 113, "Fork", 12, p["onTertiaryContainer"], 600, anchor="middle") + "</g>")
    for i, line in enumerate(wrap(proj["text"], 15, w - 48, 400, 2)):
        b.append(txt(tx, 142 + i * 21, line, 15, p["onSurfaceVariant"], 400, "up", d0 + 0.18 + i * 0.05))
    x = tx
    for i, tag in enumerate(proj["tags"]):
        g, cw = chip(x, 184, tag, p, None, d0 + 0.3 + i * 0.06, h=28, size=13, style="tonal")
        b.append(g)
        x += cw + 6
    if stars is not None:
        label = f"{stars}"
        sw = text_width(label, 14, 600)
        b.append(f'<g class="pop" style="animation-delay:{d0 + .4:.2f}s">')
        b.append(icon("star", w - 24 - sw - 22, 188, 19, p["primary"]))
        b.append(txt(w - 24, 203, label, 14, p["onSurfaceVariant"], 600, anchor="end"))
        b.append("</g>")
    return svg(w, h, "".join(b), proj["title"])


def stats(p, s):
    langs = s["languages"]
    total = sum(v for _, v in langs) or 1
    legend = []
    x, row = 28, 0
    for name, v in langs:
        label = f"{name} {100 * v / total:.1f}%".replace(".0%", "%")
        lw = 15 + text_width(label, 14, 500) + 18
        if x + lw > W - 28:
            x, row = 28, row + 1
        legend.append((x, row, label))
        x += lw
    h = 400 + row * 26
    b = [f'<rect width="{W}" height="{h}" rx="32" fill="{p["surfaceContainerLow"]}"/>']
    b.append(section_title(28, 26, "GitHub activity", "monitoring", p))
    tiles = [
        ("star", f"{s['stars']}", "Stars earned", "cookie"),
        ("commit", f"{s['contributions']}", "Contributions this year", "clover"),
        ("book_2", f"{s['repos']}", "Public repos", "sunny"),
        ("group", f"{s['followers']}", "Followers", "flower"),
    ]
    for i, (ic, value, label, sh) in enumerate(tiles):
        tx = 28 + (i % 2) * 196
        ty = 86 + (i // 2) * 106
        d = 0.1 + i * 0.08
        b.append(f'<g class="up" style="animation-delay:{d:.2f}s">')
        b.append(f'<rect x="{tx}" y="{ty}" width="184" height="96" rx="24" fill="{p["surfaceContainerHigh"]}"/>')
        b.append(f'<path d="{shape(sh, tx + 34, ty + 34, 18)}" fill="{p["primaryContainer"]}"/>')
        b.append(icon(ic, tx + 24, ty + 24, 20, p["onPrimaryContainer"]))
        b.append(txt(tx + 62, ty + 46, value, 30, p["onSurface"], 700))
        b.append(txt(tx + 20, ty + 78, label, 14, p["onSurfaceVariant"], 500))
        b.append("</g>")
    rx = 432
    b.append(txt(rx, 100, "Last 21 days", 14, p["onSurfaceVariant"], 600, "fade", 0.1))
    gap = 6
    cw = (W - 28 - rx - gap * 6) / 7
    ch = 46
    for i, letter in enumerate("SMTWTFS"):
        b.append(txt(rx + i * (cw + gap) + cw / 2, 124, letter, 12, p["onSurfaceVariant"], 600, "fade", 0.15, anchor="middle"))
    base = p["surfaceContainerHighest"]
    levels = [base, mix(base, p["primary"], .4), mix(base, p["primary"], .65), mix(base, p["primary"], .85), p["primary"]]
    peak = max([d["c"] for wk in s["days"] for d in wk if d] + [1])
    for wi, wk in enumerate(s["days"]):
        for di, d in enumerate(wk):
            x = rx + di * (cw + gap)
            y = 136 + wi * (ch + 6)
            delay = 0.2 + (wi * 7 + di) * 0.025
            if d is None:
                b.append(f'<rect class="pop" style="animation-delay:{delay:.3f}s" x="{x + .75:.1f}" y="{y + .75}" width="{cw - 1.5:.1f}" height="{ch - 1.5}" rx="14" fill="none" stroke="{p["outlineVariant"]}" stroke-width="1.5" stroke-dasharray="4 4"/>')
                continue
            lvl = 0 if d["c"] == 0 else min(4, 1 + int(3 * d["c"] / peak + 0.5))
            fg = p["onPrimary"] if lvl >= 3 else p["onSurfaceVariant"]
            cell = f'<rect x="{x:.1f}" y="{y}" width="{cw:.1f}" height="{ch}" rx="14" fill="{levels[lvl]}"/>'
            if d.get("today"):
                cell += f'<rect x="{x - 3:.1f}" y="{y - 3}" width="{cw + 6:.1f}" height="{ch + 6}" rx="17" fill="none" stroke="{p["primary"]}" stroke-width="2"/>'
            cell += txt(x + cw / 2, y + ch / 2 + 5, str(d["day"]), 14, fg, 600, anchor="middle")
            b.append(f'<g class="pop" style="animation-delay:{delay:.3f}s">{cell}</g>')
    ly = 322
    b.append(txt(28, ly, "Languages across all my repositories", 14, p["onSurfaceVariant"], 600, "fade", 0.3))
    surf = p["surfaceContainerLow"]
    colors = [p["primary"], p["tertiary"], p["secondary"], mix(p["primary"], surf, .45), mix(p["tertiary"], surf, .45), mix(p["secondary"], surf, .45), p["outline"], p["outlineVariant"]]
    bw = W - 56
    gaps = 4 * (len(langs) - 1)
    widths = [max(8.0, (bw - gaps) * v / total) for _, v in langs]
    k = (bw - gaps) / (sum(widths) or 1)
    x = 28
    segs = []
    for i, sw in enumerate(widths):
        segs.append(f'<rect x="{x:.1f}" y="{ly + 12}" width="{sw * k:.1f}" height="14" rx="7" fill="{colors[i % len(colors)]}"/>')
        x += sw * k + 4
    b.append(f'<g class="grow" style="animation-delay:.4s">{"".join(segs)}</g>')
    for i, (lx, lrow, label) in enumerate(legend):
        ly2 = ly + 50 + lrow * 26
        b.append(f'<g class="fade" style="animation-delay:{0.6 + i * 0.06:.2f}s"><circle cx="{lx + 5}" cy="{ly2 - 5}" r="5" fill="{colors[i % len(colors)]}"/>')
        b.append(txt(lx + 15, ly2, label, 14, p["onSurfaceVariant"], 500) + "</g>")
    return svg(W, h, "".join(b), "GitHub activity")


def button(p, label, ic, kind):
    h = 56
    size = 17
    w = 28 * 2 + 22 + 10 + text_width(label, size, 600)
    if kind == "filled":
        bg, fg = p["primary"], p["onPrimary"]
    else:
        bg, fg = p["secondaryContainer"], p["onSecondaryContainer"]
    b = [f'<g class="pop"><rect width="{w:.1f}" height="{h}" rx="28" fill="{bg}"/>']
    b.append(icon(ic, 28, (h - 22) / 2, 22, fg))
    b.append(txt(28 + 22 + 10, h / 2 + 6, label, size, fg, 600) + "</g>")
    return svg(round(w), h, "".join(b), label)


def wave(p):
    h = 28
    amp, length = 5, 48
    pts = []
    for i in range(0, W + length * 2 + 1, 4):
        pts.append(f"{i} {h / 2 + amp * math.sin(2 * math.pi * i / length):.1f}")
    d = "M" + " L".join(pts)
    b = [f'<clipPath id="w"><rect x="0" y="0" width="{W}" height="{h}"/></clipPath><g clip-path="url(#w)">']
    b.append(f'<path class="wave" d="{d}" fill="none" stroke="{p["primary"]}" stroke-width="5" stroke-linecap="round"/></g>')
    return svg(W, h, "".join(b), "divider")


# Data
def token():
    t = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if t:
        return t
    try:
        return subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        return None


NOISE = {"Inno Setup", "Batchfile", "PowerShell", "VBScript", "Shell", "Makefile", "Dockerfile"}


def graphql(t, q, variables=None):
    body = json.dumps({"query": q, "variables": variables or {}}).encode()
    req = urllib.request.Request("https://api.github.com/graphql", data=body, headers={"Authorization": f"bearer {t}", "User-Agent": "profile"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())["data"]


def all_languages(t):
    try:
        v = graphql(t, """{viewer{login repositories(ownerAffiliations:OWNER,first:100){nodes{isFork
          languages(first:10,orderBy:{field:SIZE,direction:DESC}){edges{size node{name}}}}}}}""")["viewer"]
    except Exception:
        return None
    if v["login"].lower() != USER.lower():
        return None
    langs = {}
    for r in v["repositories"]["nodes"]:
        if r["isFork"]:
            continue
        for e in r["languages"]["edges"]:
            name = e["node"]["name"]
            if name not in NOISE:
                langs[name] = langs.get(name, 0) + e["size"]
    return [list(kv) for kv in sorted(langs.items(), key=lambda kv: -kv[1])[:7]]


def fetch_stats(cached):
    t = token()
    if not t:
        return None
    u = graphql(t, """query($login:String!){user(login:$login){
      followers{totalCount}
      repositories(ownerAffiliations:OWNER,privacy:PUBLIC,first:100){totalCount nodes{name isFork stargazerCount}}
      pinnedItems(first:6,types:REPOSITORY){nodes{... on Repository{name url description isFork stargazerCount
        primaryLanguage{name} repositoryTopics(first:10){nodes{topic{name}}}}}}
      contributionsCollection{contributionCalendar{totalContributions
        weeks{contributionDays{contributionCount date weekday}}}}}}""", {"login": USER})["user"]
    repos = u["repositories"]["nodes"]
    today = datetime.date.today().isoformat()
    days = []
    for w in u["contributionsCollection"]["contributionCalendar"]["weeks"][-3:]:
        row = [None] * 7
        for d in w["contributionDays"]:
            row[d["weekday"]] = {"c": d["contributionCount"], "day": int(d["date"][8:]), "today": d["date"] == today}
        days.append(row)
    while len(days) < 3:
        days.insert(0, [None] * 7)
    return {
        "stars": sum(r["stargazerCount"] for r in repos if not r["isFork"]),
        "contributions": u["contributionsCollection"]["contributionCalendar"]["totalContributions"],
        "repos": u["repositories"]["totalCount"],
        "followers": u["followers"]["totalCount"],
        "languages": all_languages(t) or (cached or {}).get("languages", []),
        "days": days,
        "pins": [
            {
                "name": n["name"],
                "url": n["url"],
                "text": (n["description"] or "").strip(),
                "fork": n["isFork"],
                "stars": n["stargazerCount"],
                "language": (n["primaryLanguage"] or {}).get("name"),
                "topics": [t["topic"]["name"] for t in n["repositoryTopics"]["nodes"]],
            }
            for n in u["pinnedItems"]["nodes"]
            if n
        ],
    }


# Readme
def slug(name):
    return "".join(c if c.isalnum() else "-" for c in name.lower()).strip("-")


def pic(name, alt, width="100%"):
    return (f'<picture><source media="(prefers-color-scheme: dark)" srcset="assets/{name}-dark.svg">'
            f'<img src="assets/{name}-light.svg" width="{width}" alt="{escape(alt)}"></picture>')


def readme(pins):
    cards = [f'<a href="{pin["url"]}">{pic("project-" + slug(pin["name"]), pin["name"], "49%")}</a>' for pin in pins]
    rows = ["&nbsp;".join(cards[i:i + 2]) for i in range(0, len(cards), 2)]
    blocks = [
        pic("hero", f"Hi, I'm {USER}"),
        pic("about", "About me"),
        pic("stack", "Tech stack"),
        *rows,
        pic("stats", "GitHub activity"),
        pic("wave", ""),
        f'<a href="https://metawka.xyz">{pic("button-site", "metawka.xyz", "auto")}</a>&nbsp;&nbsp;'
        f'<a href="https://github.com/{USER}?tab=repositories">{pic("button-repos", "All repositories", "auto")}</a>',
    ]
    return '<div align="center">\n\n' + "\n\n".join(blocks) + "\n\n</div>\n"


# Main
def meaningful(s):
    return {k: v for k, v in s.items() if k != "days"}


def main():
    OUT.mkdir(exist_ok=True)
    cache = ROOT / "data/stats.json"
    cached = json.loads(cache.read_text(encoding="utf-8")) if cache.exists() else None
    try:
        s = fetch_stats(cached)
    except Exception as e:
        print("stats failed:", e)
        s = None
    if s is None:
        s = dict(cached)
    avatar = avatar_data()
    s["avatar"] = hashlib.sha1(avatar.encode()).hexdigest()[:12] if avatar else (cached or {}).get("avatar")
    if "--if-changed" in sys.argv and cached and meaningful(s) == meaningful(cached):
        print("no changes")
        return
    cache.write_text(json.dumps(s, indent=1))
    for theme in ("light", "dark"):
        p = PALETTE[theme]
        files = {
            "hero": hero(p, avatar),
            "about": about(p),
            "stack": stack(p),
            "stats": stats(p, s),
            "wave": wave(p),
        }
        for i, pin in enumerate(s["pins"]):
            files[f"project-{slug(pin['name'])}"] = card(p, pin, i)
        for key, label, ic, kind in BUTTONS:
            files[f"button-{key}"] = button(p, label, ic, kind)
        for name, content in files.items():
            (OUT / f"{name}-{theme}.svg").write_text(content, encoding="utf-8")
    keep = {f"project-{slug(pin['name'])}" for pin in s["pins"]}
    for old in OUT.glob("project-*.svg"):
        if old.stem.rsplit("-", 1)[0] not in keep:
            old.unlink()
    (ROOT / "README.md").write_text(readme(s["pins"]), encoding="utf-8")
    print("done")


if __name__ == "__main__":
    main()
