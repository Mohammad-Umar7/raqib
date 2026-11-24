"""Build the Raqib pitch deck (SCAMSHIELD AI Hackathon) as a 16:9 PowerPoint file.

Re-run after numbers or screenshots change:
    backend\\.venv\\Scripts\\python.exe docs\\deck\\build_deck.py

Inputs
  shots/*.png        screenshots of the running app (capture_shots.py)
  icons/*.png        lucide icons rasterised on first use (cached; needs Playwright + Chrome once)
Output
  Raqib-ScamShield-AI.pptx

Placeholders the team must fill in are written in [square brackets] and coloured orange.
"""

from __future__ import annotations

import re
from pathlib import Path

from lxml import etree
from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.dml import MSO_LINE
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, MSO_AUTO_SIZE, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Inches, Pt

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SHOTS = HERE / "shots"
CROPS = SHOTS / "crops"
ICONS = HERE / "icons"
OUT = HERE / "Raqib-ScamShield-AI.pptx"
LUCIDE = ROOT / "frontend" / "node_modules" / "lucide-react" / "dist" / "esm" / "icons"

# ----------------------------------------------------------------------------- facts read from the code
# (so the deck follows the product when it changes)


def _brand_count() -> int:
    import json
    try:
        data = json.loads((ROOT / "backend" / "raqib" / "data" / "registry.json").read_text(encoding="utf-8"))
        return len(data.get("entities", []))
    except Exception:
        return 0


def _detector_count() -> int:
    try:
        src = (ROOT / "backend" / "raqib" / "detectors.py").read_text(encoding="utf-8")
        return len(re.findall(r'^\s+"[a-z]+\.[a-z_]+": dict\(', src, flags=re.M))
    except Exception:
        return 0


N_BRANDS = _brand_count()
BRANDS_LABEL = f"{(N_BRANDS // 10) * 10}+" if N_BRANDS >= 30 else (str(N_BRANDS) if N_BRANDS else "30+")
N_DETECTORS = _detector_count()
DETECTORS_LABEL = f"{N_DETECTORS} deterministic detectors" if N_DETECTORS else "~20 deterministic detectors"

# ----------------------------------------------------------------------------- design tokens

BG = "07070A"
CARD = "16161D"
CARD2 = "101016"
BORDER = "24242E"
GOLD = "E5B85C"
GOLD_L = "F2D39A"
RED = "FB4A6C"
ORANGE = "FF8A3D"
GREEN = "34D399"
VIOLET = "A78BFA"
TEXT = "F2F0EA"
MUTED = "A3A1AB"
DIM = "6E6C78"

FONT = "Calibri"
MONO = "Consolas"
AR_FONT = "Arial"

SW, SH = 13.333, 7.5
M = 0.6
CW = SW - 2 * M
TOP = 1.8          # first content row
BOTTOM = 6.72      # content must end above this
FOOTER = "Raqib · SCAMSHIELD AI Hackathon · 42 Abu Dhabi × Abu Dhabi Police"


def rgb(h: str) -> RGBColor:
    return RGBColor.from_string(h)


def blend(fg: str, bg: str = CARD, a: float = 0.16) -> str:
    f = [int(fg[i:i + 2], 16) for i in (0, 2, 4)]
    b = [int(bg[i:i + 2], 16) for i in (0, 2, 4)]
    return "".join(f"{round(b[i] + (f[i] - b[i]) * a):02X}" for i in range(3))


def In(v: float) -> Emu:
    return Inches(v)


# ----------------------------------------------------------------------------- icons (lucide -> png)

_pw = None
_browser = None


def _icon_svg(name: str, color: str) -> str:
    src = (LUCIDE / f"{name}.mjs").read_text(encoding="utf-8")
    alias = re.search(r"export \{ default \} from '\./([\w-]+)\.mjs'", src)
    if alias:  # renamed icons re-export their new name
        return _icon_svg(alias.group(1), color)
    parts = []
    for tag, attrs in re.findall(r'\[\s*"(\w+)",\s*\{([^}]*)\}\s*\]', src):
        kv = re.findall(r'(\w+):\s*"([^"]*)"', attrs)
        a = " ".join(f'{k}="{v}"' for k, v in kv if k != "key")
        parts.append(f"<{tag} {a}/>")
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256" viewBox="0 0 24 24" fill="none" '
            f'stroke="#{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">{"".join(parts)}</svg>')


def icon_path(name: str, color: str) -> Path:
    global _pw, _browser
    ICONS.mkdir(parents=True, exist_ok=True)
    p = ICONS / f"{name}_{color}.png"
    if p.exists():
        return p
    if _browser is None:
        from playwright.sync_api import sync_playwright
        _pw = sync_playwright().start()
        _browser = _pw.chromium.launch(channel="chrome", headless=True)
    page = _browser.new_page(viewport={"width": 256, "height": 256})
    page.set_content(f"<html><body style='margin:0;background:transparent'>{_icon_svg(name, color)}</body></html>")
    page.screenshot(path=str(p), omit_background=True, clip={"x": 0, "y": 0, "width": 256, "height": 256})
    page.close()
    return p


def close_icon_browser() -> None:
    if _browser is not None:
        _browser.close()
        _pw.stop()


# ----------------------------------------------------------------------------- screenshot crops

def crop(name: str, box: tuple[float, float, float, float], out: str) -> Path:
    """box in the 2000x1250 coordinate frame of the 1600x1000 viewport (scaled to the real pixels)."""
    CROPS.mkdir(parents=True, exist_ok=True)
    src = Image.open(SHOTS / f"{name}.png").convert("RGB")
    k = src.width / 2000
    region = src.crop(tuple(int(v * k) for v in box))
    dst = CROPS / f"{out}.jpg"
    region.save(dst, "JPEG", quality=92, subsampling=0, optimize=True)
    return dst


def aspect(path: Path) -> float:
    with Image.open(path) as im:
        return im.width / im.height


# ----------------------------------------------------------------------------- primitives

def _set_rpr(run, *, size=None, color=None, bold=None, italic=None, font=None, ar=False, spc=None):
    f = run.font
    if size:
        f.size = Pt(size)
    if bold is not None:
        f.bold = bold
    if italic is not None:
        f.italic = italic
    if color:
        f.color.rgb = rgb(color)
    f.name = font or FONT
    rpr = run._r.get_or_add_rPr()
    if spc:
        rpr.set("spc", str(spc))
    if ar:
        rpr.set("lang", "ar-AE")
    cs = rpr.find(qn("a:cs"))
    if cs is None:
        cs = etree.SubElement(rpr, qn("a:cs"))
    cs.set("typeface", AR_FONT)


def _bullet(p, color: str, indent: float = 0.22):
    ppr = p._p.get_or_add_pPr()
    ppr.set("marL", str(int(In(indent))))
    ppr.set("indent", str(-int(In(indent))))
    clr = etree.SubElement(ppr, qn("a:buClr"))
    etree.SubElement(clr, qn("a:srgbClr")).set("val", color)
    etree.SubElement(ppr, qn("a:buFont")).set("typeface", "Arial")
    etree.SubElement(ppr, qn("a:buChar")).set("char", "•")


ALIGN = {"l": PP_ALIGN.LEFT, "c": PP_ALIGN.CENTER, "r": PP_ALIGN.RIGHT}
ANCHOR = {"t": MSO_ANCHOR.TOP, "m": MSO_ANCHOR.MIDDLE, "b": MSO_ANCHOR.BOTTOM}


def fill_tf(tf, paras, *, size=14, color=TEXT, bold=False, align="l", font=None, space_after=0, line=None):
    """paras: str | list of (str | list[(text, opts)] | dict(runs=..., bullet=..., align=..., after=..., rtl=...))."""
    if isinstance(paras, str):
        paras = [paras]
    first = True
    for para in paras:
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        spec = para if isinstance(para, dict) else {"runs": para}
        runs = spec["runs"]
        if isinstance(runs, str):
            runs = [(runs, {})]
        p.alignment = ALIGN[spec.get("align", align)]
        if spec.get("rtl"):
            p._p.get_or_add_pPr().set("rtl", "1")
        if line or spec.get("line"):
            p.line_spacing = spec.get("line", line)
        after = spec.get("after", space_after)
        if after:
            p.space_after = Pt(after)
        if spec.get("before"):
            p.space_before = Pt(spec["before"])
        if spec.get("bullet"):
            _bullet(p, spec.get("bullet_color", GOLD))
        for text, opts in runs:
            r = p.add_run()
            r.text = text
            _set_rpr(r, size=opts.get("size", spec.get("size", size)), color=opts.get("color", spec.get("color", color)),
                     bold=opts.get("bold", spec.get("bold", bold)), italic=opts.get("italic"),
                     font=opts.get("font", font), ar=opts.get("ar", spec.get("rtl", False)), spc=opts.get("spc"))


def text(slide, x, y, w, h, paras, *, size=14, color=TEXT, bold=False, align="l", anchor="t", font=None,
         space_after=0, line=None, name=None):
    tb = slide.shapes.add_textbox(In(x), In(y), In(w), In(h))
    if name:
        tb.name = name
    tf = tb.text_frame
    tf.word_wrap = True
    tf.auto_size = MSO_AUTO_SIZE.NONE
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = ANCHOR[anchor]
    fill_tf(tf, paras, size=size, color=color, bold=bold, align=align, font=font, space_after=space_after, line=line)
    return tb


def box(slide, x, y, w, h, *, fill=CARD, line=BORDER, radius=0.14, dash=False, lw=0.75, shape=None, name=None):
    kind = shape or (MSO_SHAPE.ROUNDED_RECTANGLE if radius else MSO_SHAPE.RECTANGLE)
    s = slide.shapes.add_shape(kind, In(x), In(y), In(w), In(h))
    if name:
        s.name = name
    if kind == MSO_SHAPE.ROUNDED_RECTANGLE:
        s.adjustments[0] = min(0.5, radius / min(w, h))
    if fill:
        s.fill.solid()
        s.fill.fore_color.rgb = rgb(fill)
    else:
        s.fill.background()
    if line:
        s.line.color.rgb = rgb(line)
        s.line.width = Pt(lw)
        if dash:
            s.line.dash_style = MSO_LINE.DASH
    else:
        s.line.fill.background()
    s.shadow.inherit = False
    s.text_frame.text = ""
    return s


def glow(slide, cx, cy, r, color, alpha=24):
    """Soft radial glow (an oval with a transparent radial gradient), drawn behind content."""
    s = slide.shapes.add_shape(MSO_SHAPE.OVAL, In(cx - r), In(cy - r), In(2 * r), In(2 * r))
    s.name = "Glow"
    s.line.fill.background()
    s.shadow.inherit = False
    sppr = s._element.spPr
    for tag in ("a:solidFill", "a:noFill", "a:gradFill"):
        for el in sppr.findall(qn(tag)):
            sppr.remove(el)
    grad = etree.fromstring(
        f'<a:gradFill xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" rotWithShape="1"><a:gsLst>'
        f'<a:gs pos="0"><a:srgbClr val="{color}"><a:alpha val="{alpha * 1000}"/></a:srgbClr></a:gs>'
        f'<a:gs pos="70000"><a:srgbClr val="{BG}"><a:alpha val="0"/></a:srgbClr></a:gs>'
        f'<a:gs pos="100000"><a:srgbClr val="{BG}"><a:alpha val="0"/></a:srgbClr></a:gs></a:gsLst>'
        f'<a:path path="circle"><a:fillToRect l="50000" t="50000" r="50000" b="50000"/></a:path></a:gradFill>')
    prst = sppr.find(qn("a:prstGeom"))
    prst.addnext(grad)
    tree = s._element.getparent()  # send to back, behind the title placeholder too
    tree.remove(s._element)
    tree.insert(2, s._element)
    return s


def icon(slide, name, color, x, y, size):
    pic = slide.shapes.add_picture(str(icon_path(name, color)), In(x), In(y), In(size), In(size))
    pic.name = f"Icon {name}"
    return pic


def badge(slide, name, color, x, y, d=0.56, bg=CARD):
    c = slide.shapes.add_shape(MSO_SHAPE.OVAL, In(x), In(y), In(d), In(d))
    c.name = f"Badge {name}"
    c.fill.solid()
    c.fill.fore_color.rgb = rgb(blend(color, bg, 0.18))
    c.line.color.rgb = rgb(blend(color, bg, 0.45))
    c.line.width = Pt(0.75)
    c.shadow.inherit = False
    s = d * 0.52
    icon(slide, name, color, x + (d - s) / 2, y + (d - s) / 2, s)
    return c


def picture(slide, path, x, y, w=None, h=None, *, radius=0.1, border=BORDER, name="Screenshot"):
    ar = aspect(path)
    if w and h:  # fit inside the box, centred
        if w / h > ar:
            nw = h * ar
            x, w = x + (w - nw) / 2, nw
        else:
            nh = w / ar
            y, h = y + (h - nh) / 2, nh
    elif w:
        h = w / ar
    else:
        w = h * ar
    pic = slide.shapes.add_picture(str(path), In(x), In(y), In(w), In(h))
    pic.name = name
    if radius:
        pic.auto_shape_type = MSO_SHAPE.ROUNDED_RECTANGLE
        prst = pic._element.spPr.find(qn("a:prstGeom"))
        av = prst.find(qn("a:avLst"))
        if av is None:
            av = etree.SubElement(prst, qn("a:avLst"))
        for g in list(av):
            av.remove(g)
        gd = etree.SubElement(av, qn("a:gd"))
        gd.set("name", "adj")
        gd.set("fmla", f"val {int(radius / min(w, h) * 100000)}")
    if border:
        pic.line.color.rgb = rgb(border)
        pic.line.width = Pt(1)
    return pic, (x, y, w, h)


def arrow(slide, x1, y1, x2, y2, color=DIM, width=1.5, dash=False):
    c = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, In(x1), In(y1), In(x2), In(y2))
    c.line.color.rgb = rgb(color)
    c.line.width = Pt(width)
    if dash:
        c.line.dash_style = MSO_LINE.DASH
    ln = c.line._get_or_add_ln()
    tail = etree.SubElement(ln, qn("a:tailEnd"))
    tail.set("type", "triangle")
    tail.set("w", "med")
    tail.set("h", "med")
    return c


def chip(slide, x, y, label, *, color=GOLD, size=13, h=0.38, pad=0.16, fill=None, text_color=None, dash=False):
    w = est_w(label, size) + 2 * pad
    box(slide, x, y, w, h, fill=fill or blend(color, BG, 0.10), line=blend(color, BG, 0.55), radius=h / 2, dash=dash)
    text(slide, x, y, w, h, [[(label, {})]], size=size, color=text_color or color, align="c", anchor="m")
    return w


def est_w(label: str, size: float) -> float:
    """Rough Calibri width in inches (good enough to size chips)."""
    narrow = set("ilI.,:;'|!()[]/ ·-")
    wide = set("MWmw@%")
    units = sum(0.28 if ch in narrow else 0.78 if ch in wide else 0.52 if ch.isupper() else 0.47 for ch in label)
    return units * size / 72


def chips(slide, x, y, w, labels, *, size=13, h=0.38, gap=0.12, row_gap=0.14, colors=None, color=GOLD):
    cx, cy = x, y
    for i, label in enumerate(labels):
        c = colors[i] if colors else color
        need = est_w(label, size) + 0.32
        if cx + need > x + w + 0.01 and cx > x:
            cx, cy = x, cy + h + row_gap
        cx += chip(slide, cx, cy, label, color=c, size=size, h=h) + gap
    return cy + h


# ----------------------------------------------------------------------------- slide frame

def footer(slide, n: int):
    text(slide, M, 7.02, 9.0, 0.26, [[(FOOTER, {})]], size=10, color=DIM, anchor="m", name="Footer")
    tb = slide.shapes.add_textbox(In(SW - M - 1.0), In(7.02), In(1.0), In(0.26))
    tb.name = "Slide number"
    tf = tb.text_frame
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.RIGHT
    fld = etree.SubElement(p._p, qn("a:fld"))
    fld.set("id", "{B6F15528-21DE-4FAA-801E-634DDDAF4B2B}")
    fld.set("type", "slidenum")
    rpr = etree.SubElement(fld, qn("a:rPr"))
    rpr.set("lang", "en-US")
    rpr.set("sz", "1000")
    sf = etree.SubElement(rpr, qn("a:solidFill"))
    etree.SubElement(sf, qn("a:srgbClr")).set("val", DIM)
    etree.SubElement(rpr, qn("a:latin")).set("typeface", FONT)
    t = etree.SubElement(fld, qn("a:t"))
    t.text = str(n)


def set_title(slide, runs, x=M, y=0.74, w=CW, h=0.7, size=34):
    t = slide.shapes.title
    t.left, t.top, t.width, t.height = In(x), In(y), In(w), In(h)
    tf = t.text_frame
    tf.word_wrap = True
    tf.auto_size = MSO_AUTO_SIZE.NONE
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = MSO_ANCHOR.TOP
    for p in list(tf.paragraphs)[1:]:
        p._p.getparent().remove(p._p)
    tf.paragraphs[0].text = ""
    if isinstance(runs, str):
        runs = [(runs, {})]
    fill_tf(tf, [runs], size=size, color=TEXT, bold=True)
    return t


def new_slide(prs, kicker=None, title=None, ar=None, notes=None):
    s = prs.slides.add_slide(prs.slide_layouts[5])  # "Title Only": keeps a real title for outline / screen readers
    s.background.fill.solid()
    s.background.fill.fore_color.rgb = rgb(BG)
    if kicker:
        text(s, M, 0.4, 7.4, 0.3, [[(kicker.upper(), {"spc": 200})]], size=12, color=GOLD, bold=True, anchor="m",
             name="Kicker")
    if ar:
        text(s, SW - M - 5.2, 0.36, 5.2, 0.38, [{"runs": [(ar, {})], "rtl": True, "align": "r"}], size=16,
             color=GOLD_L, anchor="m", name="Arabic subtitle")
    if title:
        set_title(s, title)
    if notes:
        s.notes_slide.notes_text_frame.text = notes
    footer(s, len(prs.slides))
    return s


def card(slide, x, y, w, h, icon_name=None, color=GOLD, title=None, body=None, *, title_size=17, body_size=14,
         fill=CARD, d=0.56, body_color=MUTED, layout="side"):
    """Rounded card: icon badge + bold title + muted body. layout 'side' puts text right of the badge."""
    box(slide, x, y, w, h, fill=fill)
    pad = 0.26
    th = title_size * 1.3 / 72 + 0.06  # title line height + gap before the body
    if layout == "side":
        if icon_name:
            badge(slide, icon_name, color, x + pad, y + pad, d, bg=fill)
        tx = x + pad + (d + 0.2 if icon_name else 0)
        tw = w - (tx - x) - pad
        if title:
            text(slide, tx, y + pad - 0.02, tw, 0.4, [[(title, {})]], size=title_size, bold=True)
        if body:
            text(slide, tx, y + pad + th, tw, h - 2 * pad - th, body, size=body_size, color=body_color, line=1.05)
    else:  # stacked: badge on top, then title, then body
        if icon_name:
            badge(slide, icon_name, color, x + pad, y + pad, d, bg=fill)
        ty = y + pad + (d + 0.18 if icon_name else 0)
        if title:
            text(slide, x + pad, ty, w - 2 * pad, 0.4, [[(title, {})]], size=title_size, bold=True)
        if body:
            text(slide, x + pad, ty + th, w - 2 * pad, h - (ty - y) - th - pad, body, size=body_size,
                 color=body_color, line=1.05)


def label(slide, x, y, w, s, color=MUTED):
    text(slide, x, y, w, 0.26, [[(s.upper(), {"spc": 150})]], size=11, color=color, bold=True, anchor="m")


PH = ORANGE  # colour for placeholders the team fills in

# ----------------------------------------------------------------------------- slides


def slide_title(prs):
    s = new_slide(prs, notes=(
        "Raqib means 'watchful guardian' in Arabic. It is a proactive scam-hunting system for police: it finds scam "
        "websites in search results, Google Maps and newly registered domains before citizens click them. "
        "In the next minute we explain the idea, then we show it working live in the dashboard."))
    glow(s, 10.2, 3.5, 4.2, VIOLET, 22)
    glow(s, 2.0, 1.2, 2.6, GOLD, 10)
    s.shapes.add_picture(str(SHOTS / "logo.png"), In(M), In(0.62), In(0.95), In(0.95)).name = "Raqib logo"
    text(s, M, 1.78, 6.4, 0.3, [[("SCAMSHIELD AI HACKATHON  ·  42 ABU DHABI × ABU DHABI POLICE", {"spc": 150})]],
         size=12, color=GOLD, bold=True, anchor="m")
    set_title(s, [("Raqib ", {"size": 66}), ("رقيب", {"size": 56, "color": GOLD, "ar": True})],
              x=M, y=2.12, w=6.4, h=1.15, size=66)
    text(s, M, 3.4, 6.4, 1.05, ["Find scam sites before", "citizens click them."], size=30, bold=True,
         color=TEXT, line=0.95)
    text(s, M, 4.52, 6.2, 0.62, ["Proactive scam hunting for police.", "Hunt · investigate · explain · link · act"],
         size=16, color=MUTED)
    # team placeholders
    box(s, M, 5.32, 6.1, 1.3, fill=CARD2, line=PH, dash=True, radius=0.14)
    text(s, M + 0.28, 5.46, 5.6, 0.25, [[("TEAM · FILL IN", {"spc": 150})]], size=10, color=PH, bold=True)
    text(s, M + 0.28, 5.74, 5.6, 0.4, [[("[TEAM NAME]", {})]], size=20, bold=True, color=PH)
    text(s, M + 0.28, 6.16, 5.6, 0.32, [[("[MEMBER 1]  ·  [MEMBER 2]  ·  [MEMBER 3]  ·  [MEMBER 4]", {})]],
         size=14, color=PH)
    radar = crop("command", (1162, 93, 1983, 707), "title_radar")
    picture(s, radar, 7.25, 1.0, 5.48, 5.6, name="Hunt radar screenshot")


def slide_problem(prs):
    s = new_slide(prs, "The problem", "Scam sites wear trusted UAE brands", "الاحتيال ينتحل جهات موثوقة", notes=(
        "Citizens meet these scams in three places: an SMS with a link, a search result or sponsored ad, and a fake "
        "Google Maps listing. The sites copy brands people trust, like RTA, Salik, Emirates Post, banks, UAE PASS and TAMM. "
        "Today takedowns start after victims report, and one operator simply moves the same kit to a fresh domain. "
        "Add a sourced statistic here if you have one; do not quote a number you cannot source."))
    label(s, M, TOP, 6, "Where citizens meet them")
    w = (CW - 2 * 0.3) / 3
    items = [
        ("message-square-warning", RED, "SMS lures", "“Parcel on hold”, “unpaid fine”: a link to a look-alike payment page."),
        ("search", ORANGE, "Search results & ads", "Sponsored ads and SEO pages for brand searches lead to fake sites."),
        ("map-pin", VIOLET, "Google Maps listings", "Fake helplines, unclaimed listings and WhatsApp-only “support”."),
    ]
    for i, (ic, c, t, b) in enumerate(items):
        card(s, M + i * (w + 0.3), TOP + 0.36, w, 1.55, ic, c, t, b)
    label(s, M, 3.98, 6, "Who they pretend to be")
    chips(s, M, 4.32, CW, ["RTA", "Salik", "Emirates Post", "UAE banks", "UAE PASS", "TAMM", "Police fines", "Couriers"],
          size=14, h=0.42, gap=0.14)
    y = 5.08
    w2 = 4.62
    card(s, M, y, w2, 1.62, "clock", ORANGE, "Takedowns are reactive",
         "Sites are blocked after victims report them, when the lure has already spread.")
    card(s, M + w2 + 0.3, y, w2, 1.62, "layers", RED, "One operator, many sites",
         "Take one domain down and the same kit, bot and phone number return on a new one.")
    sx = M + 2 * (w2 + 0.3)
    sw = SW - M - sx
    box(s, sx, y, sw, 1.62, fill=CARD2, line=PH, dash=True)
    text(s, sx + 0.22, y + 0.26, sw - 0.44, 0.55, [[("[stat]", {})]], size=28, bold=True, color=PH)
    text(s, sx + 0.22, y + 0.86, sw - 0.44, 0.6, [[("[stat: source]", {})]], size=13, color=PH)


def slide_solution(prs):
    s = new_slide(prs, "The solution", "One pipeline from discovery to police action", "الحل: من الرصد إلى الإجراء", notes=(
        "Raqib works like an analyst who never sleeps. It hunts new candidates, triages them cheaply without a browser, "
        "opens only the suspicious ones in an isolated browser, scores them with explainable detectors, links sites run "
        "by the same operator, and produces a police action pack. AI writes and lays out the case; the numbers always "
        "come from deterministic code, and an officer approves every action."))
    text(s, M, TOP - 0.05, CW, 0.75, [[(
        "Raqib hunts scam sites in newly registered domains, Search and Maps, investigates them in a sandbox, "
        "and hands officers an explainable case that is ready to act on.", {})]], size=18, color=MUTED, line=1.05)
    steps = [
        ("radar", GOLD, "Hunt", "New domains, Search & ads, Maps, citizen reports"),
        ("filter", GOLD, "Triage", "Cheap checks, no browser: look-alikes, lure words, age"),
        ("smartphone", ORANGE, "Sandbox investigation", "Isolated mobile browser follows the victim's path"),
        ("gauge", RED, "Explainable score", "Deterministic detectors; every signal has a reason"),
        ("network", VIOLET, "Campaign linking", "Shared bots, wallets, phones and kits link sites"),
        ("file-check", GREEN, "Police action pack", "Evidence, PDF report, takedown drafts, blocklist"),
    ]
    gap = 0.34
    w = (CW - 5 * gap) / 6
    y, h = 2.78, 2.6
    for i, (ic, c, t, b) in enumerate(steps):
        x = M + i * (w + gap)
        box(s, x, y, w, h)
        text(s, x + 0.16, y + 0.14, 0.6, 0.25, [[(f"0{i + 1}", {})]], size=11, color=DIM, bold=True)
        badge(s, ic, c, x + (w - 0.62) / 2, y + 0.32, 0.62)
        text(s, x + 0.12, y + 1.06, w - 0.24, 0.55, [[(t, {})]], size=15, bold=True, align="c", anchor="m", line=0.95)
        text(s, x + 0.14, y + 1.66, w - 0.28, 0.86, [[(b, {})]], size=12, color=MUTED, align="c", line=1.0)
        if i < 5:
            icon(s, "chevron-right", GOLD, x + w + (gap - 0.26) / 2, y + h / 2 - 0.13, 0.26)
    y2 = 5.72
    w3 = (CW - 2 * 0.3) / 3
    principles = [
        ("filter", GOLD, "Browser only for suspects", "Triage is cheap, so coverage scales."),
        ("gauge", GREEN, "AI writes, the pipeline scores", "Numbers always come from deterministic code."),
        ("user-check", VIOLET, "Officer in the loop", "Takedowns and warnings are drafts, never auto-sent."),
    ]
    for i, (ic, c, t, b) in enumerate(principles):
        x = M + i * (w3 + 0.3)
        box(s, x, y2, w3, 0.98, fill=CARD2)
        badge(s, ic, c, x + 0.2, y2 + 0.21, 0.56, bg=CARD2)
        text(s, x + 0.92, y2 + 0.15, w3 - 1.1, 0.34, [[(t, {})]], size=15, bold=True, anchor="m")
        text(s, x + 0.92, y2 + 0.5, w3 - 1.1, 0.34, [[(b, {})]], size=13, color=MUTED, anchor="m")


def slide_detection(prs):
    s = new_slide(prs, "Detection accuracy · 30%", "A real scanner with an explainable score", "دقة الكشف", notes=(
        "Raqib is not a keyword filter. The scanner opens any URL, follows redirect chains and URL shorteners, compares "
        "what a phone and a desktop see to catch cloaking, and records the screenshot, DOM and scripts as evidence. "
        f"{DETECTORS_LABEL[0].upper() + DETECTORS_LABEL[1:]} turn that evidence into a noisy-OR score where every signal has a reason. "
        "Official UAE brands, .gov.ae and trusted domains are protected against false positives, and the batch evaluator "
        "reports precision, recall and F1 on a labelled list. Fill the metric placeholders with your latest run."))
    lw = 7.55
    # scanner card
    box(s, M, TOP, lw, 2.02)
    text(s, M + 0.26, TOP + 0.2, 5, 0.36, [[("Scanner for any URL", {})]], size=17, bold=True)
    feats = [
        ("link", GOLD, "Follows redirect chains, expands URL shorteners"),
        ("eye-off", ORANGE, "Detects cloaking: mobile vs desktop content"),
        ("camera", GREEN, "Captures screenshot, DOM and scripts"),
        ("smartphone", VIOLET, "Isolated mobile browser, UAE locale"),
    ]
    cw2 = (lw - 0.52 - 0.3) / 2
    for i, (ic, c, t) in enumerate(feats):
        x = M + 0.26 + (i % 2) * (cw2 + 0.3)
        y = TOP + 0.72 + (i // 2) * 0.6
        badge(s, ic, c, x, y, 0.44)
        text(s, x + 0.56, y, cw2 - 0.56, 0.44, [[(t, {})]], size=13.5, color=TEXT, anchor="m", line=0.95)
    # detectors card
    y = TOP + 2.24
    h = BOTTOM - y
    box(s, M, y, lw, h)
    text(s, M + 0.26, y + 0.2, 6, 0.36, [[(DETECTORS_LABEL[0].upper() + DETECTORS_LABEL[1:], {})]], size=17, bold=True)
    det = [("Brand impersonation", GOLD), ("Look-alike / homoglyph", GOLD), ("Card & CVV form", RED),
           ("OTP request", RED), ("Emirates ID", RED), ("Credentials", RED),
           ("Telegram bot", VIOLET), ("Discord webhook", VIOLET), ("New domain", MUTED),
           ("Guaranteed returns", ORANGE), ("Upfront fees", ORANGE), ("Crypto wallets", ORANGE),
           ("Urgency & threats", ORANGE)]
    end = chips(s, M + 0.26, y + 0.64, lw - 0.52, [d[0] for d in det], colors=[d[1] for d in det], size=12.5,
                h=0.34, gap=0.1, row_gap=0.1)
    text(s, M + 0.26, end + 0.14, lw - 0.52, 0.4, [[("Score = 1 − Π(1 − wᵢ)", {"font": MONO, "color": GOLD_L, "size": 14}),
                                                    ("   noisy-OR: every signal adds a weight and a reason (EN + AR)", {})]],
         size=13, color=MUTED, anchor="m")
    # right column
    rx = M + lw + 0.3
    rw = SW - M - rx
    box(s, rx, TOP, rw, 2.02)
    badge(s, "shield-check", GREEN, rx + 0.24, TOP + 0.2, 0.5)
    text(s, rx + 0.86, TOP + 0.2, rw - 1.0, 0.5, [[("False-positive guard", {})]], size=17, bold=True, anchor="m")
    text(s, rx + 0.26, TOP + 0.84, rw - 0.5, 1.1, [
        {"runs": "Official registry of UAE brands and domains", "bullet": True, "bullet_color": GREEN, "after": 3},
        {"runs": ".gov.ae trust and a trusted-domain list", "bullet": True, "bullet_color": GREEN, "after": 3},
        {"runs": "Domain age weighs in, never decides alone", "bullet": True, "bullet_color": GREEN},
    ], size=13.5, color=TEXT)
    y = TOP + 2.24
    h = BOTTOM - y
    box(s, rx, y, rw, h)
    badge(s, "list-checks", GOLD, rx + 0.24, y + 0.2, 0.5)
    text(s, rx + 0.86, y + 0.2, rw - 1.0, 0.5, [[("Measured, not claimed", {})]], size=17, bold=True, anchor="m")
    text(s, rx + 0.26, y + 0.78, rw - 0.5, 0.3, [[("Validation set: 18 demo cases + 20 live UAE sites", {})]],
         size=12.5, color=MUTED)
    for i, (k, v) in enumerate((("Precision", "100%"), ("Recall", "100%"), ("UAE sites flagged", "0 / 20"))):
        ry = y + 1.2 + i * 0.48
        box(s, rx + 0.26, ry, rw - 0.52, 0.4, fill=CARD2, radius=0.1)
        text(s, rx + 0.44, ry, 1.6, 0.4, [[(k, {})]], size=13.5, color=TEXT, anchor="m")
        text(s, rx + 1.9, ry, rw - 2.34, 0.4, [[(v, {})]], size=16, bold=True, color=GREEN, align="r", anchor="m")


def slide_coverage(prs):
    s = new_slide(prs, "Early detection & coverage · 25%", "Four sources feed one triage funnel",
                  "الرصد المبكر والتغطية", notes=(
        "Raqib looks where scams are born, not only where they are reported. A newly registered look-alike domain "
        "is often the first public trace, so we check every domain registered each day (about 70,000). Search results, sponsored "
        "ads and Google Maps listings show what citizens actually see, and citizen and hotline reports close the loop. "
        "Everything lands in one funnel: cheap triage first, the sandbox browser only for suspects."))
    srcs = [
        ("certificate", GOLD, "Newly registered domains", "Live daily feed (~70,000/day) checked for UAE brand look-alikes"),
        ("search", ORANGE, "Google Search & ads", "Organic results and sponsored ads for brand searches"),
        ("map-pin", VIOLET, "Google Maps listings", "Fake helplines, unclaimed listings, WhatsApp-only support"),
        ("user-round", GREEN, "Citizen & hotline reports", "SMS links and URLs reported by the public"),
    ]
    lw = 4.45
    h = 1.08
    g = (BOTTOM - TOP - 4 * h) / 3
    for i, (ic, c, t, b) in enumerate(srcs):
        card(s, M, TOP + i * (h + g), lw, h, ic, c, t, b, title_size=15, body_size=12.5, d=0.5)
    rx = M + lw + 0.35
    rw = SW - M - rx
    shot = crop("command", (100, 92, 1990, 910), "command_wide")
    _, (px, py, pw, ph) = picture(s, shot, rx, TOP, rw, name="Command center screenshot")
    # mini funnel under the screenshot
    fy = py + ph + 0.3
    steps = [("Candidates", MUTED), ("Triage", GOLD), ("Sandbox", RED), ("Case + campaign", GREEN)]
    fw = (rw - 3 * 0.34) / 4
    for i, (t, c) in enumerate(steps):
        fx = rx + i * (fw + 0.34)
        box(s, fx, fy, fw, 0.48, fill=blend(c, BG, 0.12), line=blend(c, BG, 0.5), radius=0.24)
        text(s, fx, fy, fw, 0.48, [[(t, {})]], size=13, bold=True, color=c, align="c", anchor="m")
        if i < 3:
            icon(s, "chevron-right", DIM, fx + fw + 0.06, fy + 0.11, 0.22)
    text(s, rx, fy + 0.62, rw, 0.5, [[(
        f"Triage needs no browser: look-alikes of {BRANDS_LABEL} protected UAE brands, lure words, risky Maps "
        "categories, domain age. Only suspects reach the sandbox.",
        {})]], size=12.5, color=MUTED)


def slide_live(prs):
    s = new_slide(prs, "Sandbox investigation", "The agent walks the victim's path, safely",
                  "تحقيق آمن في متصفح معزول", notes=(
        "This is the live investigation view. A throwaway browser with a mobile profile and UAE locale opens the link, "
        "and an agent crew works in parallel: the browser agent follows the victim's path, detectors score what it "
        "sees, the campaign linker looks for related sites and the case writer prepares the file. Notice the log: on the "
        "card page the agent inspects each field but never types into card, OTP or ID fields; that rule is enforced in code."))
    shot = crop("live_late", (100, 180, 1990, 1250), "live")
    pw = 8.35
    picture(s, shot, M, TOP, pw, BOTTOM - TOP, name="Live investigation screenshot")
    rx = M + pw + 0.35
    rw = SW - M - rx
    items = [
        ("smartphone", GOLD, "Isolated browser", "Mobile profile, UAE locale, fresh throwaway context"),
        ("bot", VIOLET, "Agent crew", "Browser agent, detectors, campaign linker, case writer"),
        ("scroll-text", ORANGE, "Activity log", "Every action and signal, timestamped"),
        ("lock", RED, "Sensitive fields flagged", "Never types into card, OTP, ID or password fields"),
    ]
    h = 1.08
    g = (BOTTOM - TOP - 4 * h) / 3
    for i, (ic, c, t, b) in enumerate(items):
        y = TOP + i * (h + g)
        badge(s, ic, c, rx, y + 0.04, 0.5, bg=BG)
        text(s, rx + 0.64, y, rw - 0.64, 0.36, [[(t, {})]], size=15, bold=True, anchor="m")
        text(s, rx + 0.64, y + 0.38, rw - 0.64, 0.66, [[(b, {})]], size=13, color=MUTED, line=1.0)


def slide_explain(prs):
    s = new_slide(prs, "Explainability & actionability · 20%", "Every verdict comes with evidence and next steps",
                  "أدلة واضحة وإجراءات جاهزة", notes=(
        "Officers need to trust and use the result. Every signal carries a plain reason and a weight in English and "
        "Arabic, so the score can be explained line by line. Every artefact is SHA-256 hashed into a manifest for chain "
        "of custody. The report pack gives a bilingual PDF, takedown drafts for the registrar, host, Google Safe Browsing "
        "and Google Maps, a blocklist export and a public warning, all as drafts for officer review."))
    lw = 4.55
    blocks = [
        ("gauge", GOLD, "Explain", ["Every signal: reason + weight", "English and Arabic wording"]),
        ("file-lock", GREEN, "Prove", ["SHA-256 per artefact + manifest", "Screenshots, WHOIS/RDAP, hosting, timestamps"]),
        ("send", RED, "Act", ["PDF case report (EN + AR)", "Takedown drafts: registrar, host, Safe Browsing, Maps",
                              "Blocklist CSV / JSON, public warning text"]),
    ]
    hs = [1.32, 1.5, 1.9]
    y = TOP
    for (ic, c, t, lines), h in zip(blocks, hs):
        box(s, M, y, lw, h)
        badge(s, ic, c, M + 0.24, y + 0.22, 0.5)
        text(s, M + 0.88, y + 0.22, lw - 1.1, 0.5, [[(t.upper(), {"spc": 150})]], size=13, bold=True, color=c, anchor="m")
        text(s, M + 0.88, y + 0.74, lw - 1.1, h - 0.86,
             [{"runs": ln, "bullet": True, "bullet_color": c, "after": 2} for ln in lines], size=13.5, color=TEXT, line=1.0)
        y += h + 0.2
    rx = M + lw + 0.35
    rw = SW - M - rx
    shot = crop("report", (112, 340, 1990, 1250), "report")
    _, (px, py, pw, ph) = picture(s, shot, rx, TOP, rw, name="Report pack screenshot")
    # chain of custody strip
    cy = py + ph + 0.32
    label(s, rx, cy, rw, "Chain of custody")
    cy += 0.36
    chain = [("screenshot.png", MUTED), ("sha256 96f4…8627", GOLD_L), ("manifest.json", GREEN), ("case report", RED)]
    cwid = (rw - 3 * 0.34) / 4
    for i, (t, c) in enumerate(chain):
        cx = rx + i * (cwid + 0.34)
        box(s, cx, cy, cwid, 0.5, fill=CARD2, radius=0.1)
        text(s, cx, cy, cwid, 0.5, [[(t, {})]], size=12, color=c, align="c", anchor="m", font=MONO)
        if i < 3:
            icon(s, "chevron-right", DIM, cx + cwid + 0.06, cy + 0.14, 0.22)


def slide_campaign(prs):
    s = new_slide(prs, "Campaign linking · innovation", "One operator, many sites, linked by evidence",
                  "ربط المواقع بالمشغّل نفسه", notes=(
        "Taking down one site does little if the operator has ten more. Raqib fingerprints every site: kit-file hashes, "
        "Telegram bot IDs, wallets, phone and WhatsApp numbers, favicons, analytics IDs, redirectors, registration "
        "batches and visual similarity. Links are graded: shared tooling or contact details is strong; looking alike "
        "is only weak, because two gangs can copy the same brand. Here one Telegram bot ties together parcel, fine and "
        "toll scams that look unrelated."))
    shot = crop("campaign", (115, 348, 1275, 1125), "campaign_graph")
    gw = 6.55
    picture(s, shot, M, TOP, gw, BOTTOM - TOP, name="Campaign graph screenshot")
    rx = M + gw + 0.4
    rw = SW - M - rx
    label(s, rx, TOP, rw, "Fingerprints")
    end = chips(s, rx, TOP + 0.36, rw, ["Kit-file hashes", "Telegram bot IDs", "Crypto wallets", "Phone / WhatsApp",
                                        "Favicon", "Analytics IDs", "Redirectors", "Registration batch",
                                        "Visual similarity"], size=13, h=0.38, gap=0.1, row_gap=0.12)
    y = end + 0.34
    label(s, rx, y, rw, "Graded links")
    y += 0.38
    grades = [("Strong", RED, False, "shared operator tooling or contact details"),
              ("Medium", ORANGE, False, "shared fingerprints unlikely by chance"),
              ("Weak", MUTED, True, "same host, similar layout or wording")]
    for i, (g, c, dashed, d) in enumerate(grades):
        yy = y + i * 0.42
        ln = s.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, In(rx), In(yy + 0.17), In(rx + 0.5), In(yy + 0.17))
        ln.line.color.rgb = rgb(c)
        ln.line.width = Pt(2.5)
        if dashed:
            ln.line.dash_style = MSO_LINE.DASH
        text(s, rx + 0.66, yy, 0.9, 0.34, [[(g, {})]], size=14, bold=True, color=c, anchor="m")
        text(s, rx + 1.5, yy, rw - 1.5, 0.34, [[(d, {})]], size=13, color=MUTED, anchor="m")
    qy = y + 3 * 0.42 + 0.22
    qh = BOTTOM - qy
    box(s, rx, qy, rw, qh, fill=blend(GOLD, BG, 0.08), line=blend(GOLD, BG, 0.4))
    text(s, rx + 0.28, qy, rw - 0.56, qh, [
        {"runs": [("Looking alike ≠ same operator", {})], "size": 20, "bold": True, "color": GOLD, "after": 4},
        {"runs": [("Two gangs copying the same brand are never merged into one campaign.", {})], "size": 13,
         "color": MUTED},
    ], anchor="m")


def slide_uae(prs):
    s = new_slide(prs, "UAE relevance & innovation · 15%", "Built for the UAE, with AI that cannot invent numbers",
                  "مصمَّم لدولة الإمارات", notes=(
        f"Everything is bilingual, from the dashboard to the PDF case file, and the detectors read Arabic lures. "
        f"The registry protects {BRANDS_LABEL} UAE brands, from banks and RTA to UAE PASS, ICP and the police. "
        "Claude Sonnet 5.5 composes the case file as structured output and checks screenshots visually, but every number "
        "on screen comes from the deterministic pipeline. The maps show hosting infrastructure; hosting is an indicator, "
        "never the scammer's location."))
    cards = [
        ("languages", GOLD, "Bilingual by design", "Arabic / English UI and case files; detects Arabic-language lures."),
        ("building-2", GOLD, f"{BRANDS_LABEL} protected UAE brands",
         "Banks, RTA, Salik, TAMM, UAE PASS, Emirates Post, ICP, MOI, Dubai & Abu Dhabi Police."),
        ("car", ORANGE, "Traffic-fine & toll scams", "Fake RTA, Salik and police-fine pages are a first-class scam type."),
        ("sparkles", VIOLET, "Generative case UI",
         "Claude Sonnet 5.5 composes the case file as structured output; numbers always come from the pipeline."),
        ("scan-eye", VIOLET, "Claude vision check", "Screenshots are checked for visual brand impersonation."),
        ("globe", GREEN, "Networks & infrastructure maps",
         "Scam domains linked into networks; UAE + world maps. Hosting is an indicator, not the scammer's location."),
    ]
    w = (CW - 2 * 0.3) / 3
    h = (BOTTOM - TOP - 0.3) / 2
    for i, (ic, c, t, b) in enumerate(cards):
        x = M + (i % 3) * (w + 0.3)
        y = TOP + (i // 3) * (h + 0.3)
        card(s, x, y, w, h, ic, c, t, b, layout="stacked", title_size=17, body_size=14)


def slide_arch(prs):
    s = new_slide(prs, "Architecture & scalability", "Simple to deploy, built to scale out", "البنية وقابلية التوسع",
                  notes=(
        "The backend is FastAPI; hunters and triage feed an orchestrator that hands suspects to scan workers. Each worker "
        "runs Playwright inside a hardened container: no host mounts, all capabilities dropped, read-only filesystem and "
        "a loopback-only port. Workers are independent, so throughput grows by adding workers. Evidence is stored in "
        "SQLite and JSON with hashes, and the React dashboard reads it through the API. New sources plug in as adapters."))
    top = TOP
    # column A: sources
    ax, aw = M, 2.35
    label(s, ax, top, aw, "Sources")
    srcs = ["CT log stream", "Search / Ads API", "Maps API", "Citizen reports"]
    for i, t in enumerate(srcs):
        y = top + 0.4 + i * 0.7
        box(s, ax, y, aw, 0.54, fill=CARD2)
        text(s, ax, y, aw, 0.54, [[(t, {})]], size=13.5, align="c", anchor="m")
        arrow(s, ax + aw + 0.04, y + 0.27, ax + aw + 0.42, top + 0.4 + 1.32, color=DIM, width=1.25)
    # column B: backend
    bx, bw = ax + aw + 0.46, 3.45
    bh = 3.3
    box(s, bx, top, bw, bh, fill=blend(GOLD, BG, 0.06), line=blend(GOLD, BG, 0.45))
    text(s, bx + 0.2, top + 0.1, bw - 0.4, 0.4, [[("FastAPI backend", {})]], size=16, bold=True, color=GOLD, anchor="m")
    mods = ["Hunters & triage", "Orchestrator", "Detectors & scoring", "Campaign linker", "Report & takedown pack"]
    for i, t in enumerate(mods):
        y = top + 0.6 + i * 0.53
        box(s, bx + 0.2, y, bw - 0.4, 0.43, fill=CARD, radius=0.08)
        text(s, bx + 0.2, y, bw - 0.4, 0.43, [[(t, {})]], size=13, align="c", anchor="m")
    # column C: workers + Claude
    cx, cw = bx + bw + 0.5, 3.0
    for k in (2, 1):
        box(s, cx + k * 0.1, top - k * 0.08 + 0.08, cw, 1.55, fill=CARD2, line=BORDER)
    box(s, cx, top + 0.08, cw, 1.55, fill=CARD, line=blend(RED, BG, 0.5))
    text(s, cx + 0.2, top + 0.2, cw - 0.4, 0.36, [[("Scan workers × N", {})]], size=15, bold=True, color=RED, anchor="m")
    text(s, cx + 0.2, top + 0.6, cw - 0.4, 0.95, [[("Playwright sandbox in a hardened container", {})]], size=13,
         color=MUTED, line=1.0)
    arrow(s, bx + bw + 0.04, top + 0.95, cx - 0.04, top + 0.95, color=GOLD, width=1.5)
    cy2 = top + 1.95
    box(s, cx, cy2, cw, 1.35, fill=blend(VIOLET, BG, 0.1), line=blend(VIOLET, BG, 0.5))
    text(s, cx + 0.2, cy2 + 0.12, cw - 0.4, 0.36, [[("Claude Sonnet 5.5", {})]], size=15, bold=True, color=VIOLET, anchor="m")
    text(s, cx + 0.2, cy2 + 0.52, cw - 0.4, 0.8, [[("Browser agent · case writer · vision check (optional)", {})]],
         size=13, color=MUTED, line=1.0)
    arrow(s, bx + bw + 0.04, cy2 + 0.6, cx - 0.04, cy2 + 0.6, color=VIOLET, width=1.5, dash=True)
    # column D: store + dashboard
    dx = cx + cw + 0.5
    dw = SW - M - dx
    box(s, dx, top + 0.08, dw, 1.0, fill=CARD)
    text(s, dx + 0.15, top + 0.08, dw - 0.3, 1.0, [{"runs": [("Evidence store", {})], "bold": True, "size": 14.5},
                                                     {"runs": [("SQLite / JSON", {})], "size": 12.5, "color": MUTED},
                                                     {"runs": [("SHA-256 hashed", {})], "size": 12.5, "color": MUTED}], align="c", anchor="m")
    box(s, dx, top + 1.28, dw, 1.0, fill=CARD)
    text(s, dx + 0.15, top + 1.28, dw - 0.3, 1.0, [{"runs": [("React dashboard", {})], "bold": True, "size": 14.5},
                                                    {"runs": [("EN / AR, live updates", {})], "size": 12.5,
                                                     "color": MUTED}], align="c", anchor="m")
    box(s, dx, top + 2.48, dw, 0.82, fill=blend(GREEN, BG, 0.1), line=blend(GREEN, BG, 0.5))
    text(s, dx, top + 2.48, dw, 0.82, [[("Officers review & act", {})]], size=14, bold=True, color=GREEN, align="c",
         anchor="m")
    arrow(s, cx + cw + 0.04, top + 0.58, dx - 0.04, top + 0.58, color=DIM, width=1.25)
    arrow(s, dx + dw / 2, top + 1.1, dx + dw / 2, top + 1.26, color=DIM, width=1.25)
    arrow(s, dx + dw / 2, top + 2.3, dx + dw / 2, top + 2.46, color=DIM, width=1.25)
    # notes row
    ny = 5.32
    nw = (CW - 2 * 0.3) / 3
    notes = [
        ("container", RED, "Hardened sandbox", "No host mounts, dropped capabilities, read-only FS, loopback-only port"),
        ("layers", GOLD, "Scales horizontally", "Scan workers are independent: add workers to add throughput"),
        ("plug", GREEN, "Pluggable sources", "CT logs, SERP / Maps APIs, citizen reports: one adapter each"),
    ]
    for i, (ic, c, t, b) in enumerate(notes):
        x = M + i * (nw + 0.3)
        card(s, x, ny, nw, BOTTOM - ny, ic, c, t, b, title_size=15, body_size=12.5, d=0.5, fill=CARD2)


def slide_pilot(prs):
    s = new_slide(prs, "Route to a police pilot", "A realistic path from demo to deployment",
                  "الطريق إلى تجربة مع الشرطة", notes=(
        "We propose a small, measurable start. Phase one runs for four weeks on Abu Dhabi Police's own infrastructure "
        "with citizen SMS reports and the new-domain feed, and analysts review every case so we can measure precision on "
        "real reports. Phase two adds Search and Maps feeds, a takedown workflow and a shared blocklist with TDRA and ISPs. "
        "Phase three is a national rollout with legal-request templates for telecoms and exchanges."))
    phases = [
        ("PHASE 1 · 4 WEEKS", GOLD, "Pilot on AD Police infrastructure", "flag",
         ["Runs on AD Police's own servers", "Ingest citizen SMS reports + CT feed", "Analysts review every case",
          "Measure precision on real reports"]),
        ("PHASE 2 · AFTER PILOT REVIEW", ORANGE, "Wider feeds, real takedowns", "send",
         ["Search & Maps API feeds", "Takedown workflow with registrars, hosts and Google",
          "Shared blocklist with TDRA / ISPs"]),
        ("PHASE 3 · NATIONAL", GREEN, "National rollout", "rocket",
         ["Rollout to other police forces", "Legal-request templates for telecoms and exchanges",
          "Accuracy reported on every release"]),
    ]
    w = (CW - 2 * 0.3) / 3
    card_h = 3.55
    ly = TOP + (BOTTOM - TOP - (0.85 + card_h)) / 2 + 0.3  # centre the timeline + cards in the content area
    line = s.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, In(M + w / 2), In(ly), In(M + 2.5 * w + 0.6), In(ly))
    line.line.color.rgb = rgb(BORDER)
    line.line.width = Pt(2)
    for i, (ph, c, t, ic, items) in enumerate(phases):
        x = M + i * (w + 0.3)
        badge(s, ic, c, x + w / 2 - 0.3, ly - 0.3, 0.6, bg=BG)
        y = ly + 0.55
        h = card_h
        box(s, x, y, w, h)
        text(s, x + 0.28, y + 0.26, w - 0.56, 0.3, [[(ph, {"spc": 120})]], size=12, bold=True, color=c)
        text(s, x + 0.28, y + 0.62, w - 0.56, 0.8, [[(t, {})]], size=20, bold=True, line=0.95)
        text(s, x + 0.28, y + 1.5, w - 0.56, h - 1.7,
             [{"runs": it, "bullet": True, "bullet_color": c, "after": 7} for it in items], size=15, color=TEXT,
             line=1.0)


def slide_close(prs):
    s = new_slide(prs, "Honest limits", "What Raqib is, and is not, yet", "حدود صريحة · شكراً لكم", notes=(
        "We want to be clear about limits. The demo replays recorded, fictional cases so we never open real scam sites on "
        "stage; live mode scans any URL. Live Search and Maps feeds need API keys. A hosting country is not the attacker's "
        "location. Raqib is decision support: an officer reviews every case before anything is sent. Thank you; we are "
        "happy to take questions."))
    lim = [
        ("clapperboard", ORANGE, "Demo replays recorded, fictional cases", "For safety on stage; live mode scans any URL."),
        ("key-round", GOLD, "Live Search & Maps feeds need API keys", "Recorded feeds stand in for them in the demo."),
        ("globe", VIOLET, "Hosting country ≠ attacker location", "Infrastructure is an indicator, not attribution."),
        ("user-check", GREEN, "Decision support, not a verdict", "An officer reviews every case before any action."),
    ]
    lw = 6.75
    h = 1.08
    g = (BOTTOM - TOP - 4 * h) / 3
    for i, (ic, c, t, b) in enumerate(lim):
        card(s, M, TOP + i * (h + g), lw, h, ic, c, t, b, title_size=16, body_size=13.5, d=0.52)
    rx = M + lw + 0.35
    rw = SW - M - rx
    glow(s, rx + rw / 2, TOP + 2.45, 2.6, VIOLET, 20)
    box(s, rx, TOP, rw, BOTTOM - TOP, fill=None, line=BORDER)
    s.shapes.add_picture(str(SHOTS / "logo.png"), In(rx + rw / 2 - 0.5), In(TOP + 0.45), In(1.0), In(1.0)).name = "Raqib logo"
    text(s, rx, TOP + 1.6, rw, 0.85, [[("Thank you", {})]], size=46, bold=True, align="c", anchor="m")
    text(s, rx, TOP + 2.45, rw, 0.7, [{"runs": [("شكراً لكم", {})], "rtl": True, "align": "c"}], size=32, color=GOLD,
         anchor="m")
    text(s, rx, TOP + 3.2, rw, 0.45, [[("Questions? Live demo next.", {})]], size=18, color=MUTED, align="c", anchor="m")
    text(s, rx, TOP + 4.1, rw, 0.4, [[("[TEAM NAME]", {})]], size=16, bold=True, color=PH, align="c", anchor="m")


# ----------------------------------------------------------------------------- build


def build() -> Path:
    prs = Presentation()
    prs.slide_width = In(SW)
    prs.slide_height = In(SH)
    prs.core_properties.title = "Raqib: find scam sites before citizens click them"
    prs.core_properties.subject = "SCAMSHIELD AI Hackathon · 42 Abu Dhabi × Abu Dhabi Police"
    prs.core_properties.author = "[TEAM NAME]"
    master = prs.slide_master
    master.background.fill.solid()
    master.background.fill.fore_color.rgb = rgb(BG)

    for fn in (slide_title, slide_problem, slide_solution, slide_detection, slide_coverage, slide_live, slide_explain,
               slide_campaign, slide_uae, slide_arch, slide_pilot, slide_close):
        fn(prs)
    close_icon_browser()
    prs.save(OUT)
    return OUT


if __name__ == "__main__":
    out = build()
    print(f"wrote {out}  (brands={N_BRANDS} -> '{BRANDS_LABEL}', detectors={N_DETECTORS})")
