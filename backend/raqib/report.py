"""Police action pack: case report (PDF/JSON), takedown drafts, blocklist export, public warning."""

from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from pathlib import Path

from . import config
from .domains import registrable

STRENGTH_COLORS = {"strong": "#D6336C", "medium": "#F08C00", "weak": "#868E96"}


def defang(domain: str) -> str:
    return domain.replace(".", "[.]")


# --------------------------------------------------------------------------- text packs

def public_warning(ctx: dict) -> dict:
    brand = ctx.get("brand") or {}
    official = (brand.get("domains") or [""])[0]
    dom = defang(ctx["domain"])
    st = ctx["scam_type"]
    if st in ("investment",):
        en = f"Scam alert: the website {dom} promises guaranteed returns and asks for cryptocurrency deposits. No licensed investment firm guarantees returns. Do not send money, and check any company with the regulator before investing."
        ar = f"تنبيه احتيال: الموقع {dom} يَعِد بعوائد مضمونة ويطلب إيداعات بعملات رقمية. لا توجد شركة استثمار مرخّصة تضمن العوائد. لا تحوّل أموالاً وتحقق من أي شركة لدى الجهة الرقابية قبل الاستثمار."
    elif st in ("advance_fee_loan", "job_offer"):
        en = f"Scam alert: the website {dom} asks for an upfront fee before a loan or job offer. Genuine lenders and employers do not ask for advance payments. Do not pay."
        ar = f"تنبيه احتيال: الموقع {dom} يطلب رسوماً مقدّمة مقابل قرض أو عرض وظيفي. الجهات الحقيقية لا تطلب دفعات مسبقة. لا تدفع."
    elif brand:
        en = (f"Scam alert: a fake {brand['name']} website ({dom}) is asking people for card details and SMS codes. {brand['name']} will not ask for this by link or message. "
              f"Do not click links in SMS messages. Use the official website ({official}) or app. If you entered your details, call your bank immediately and report it to the police.")
        ar = (f"تنبيه احتيال: موقع مزيف يدّعي أنه {brand['name_ar']} ({dom}) يطلب من الناس بيانات البطاقة ورموز الرسائل. {brand['name_ar']} لا تطلب ذلك عبر رابط أو رسالة. "
              f"لا تضغط على الروابط في الرسائل واستخدم الموقع أو التطبيق الرسمي ({official}). إذا أدخلت بياناتك فاتصل بالبنك فوراً وأبلغ الشرطة.")
    else:
        en = f"Scam alert: the website {dom} has been identified as fraudulent. Do not enter personal or payment details. If you did, contact your bank and report it to the police."
        ar = f"تنبيه احتيال: تم رصد الموقع {dom} كموقع احتيالي. لا تُدخل بيانات شخصية أو بيانات دفع. إذا فعلت فاتصل ببنكك وأبلغ الشرطة."
    return {"en": en, "ar": ar}


def _evidence_lines(ctx: dict) -> str:
    return "\n".join(f"  {e['id']}  {e['kind']:<10} sha256:{e['sha256']}" for e in ctx["evidence"])


def takedown_draft(ctx: dict, target: str) -> dict:
    dom, infra = ctx["domain"], ctx.get("infra", {})
    sigs = "\n".join(f"  - {s['label']}" for s in sorted(ctx["signals"], key=lambda s: -s["weight"])[:6])
    footer = (f"\nEvidence (SHA-256, manifest {ctx['manifest'][:16]}…):\n{_evidence_lines(ctx)}\n\n"
              "This is a draft prepared by Raqib for officer review. It has not been sent.")
    if target == "registrar":
        return {"to": infra.get("registrar", "Domain registrar abuse contact"), "subject": f"Urgent abuse report: phishing domain {dom}",
                "body": f"We request suspension of the domain {dom} (registered {infra.get('domain_created', 'recently')}).\n\n"
                        f"The site impersonates {(ctx.get('brand') or {}).get('name', 'a trusted organisation')} and collects payment or identity data from UAE residents.\nFindings:\n{sigs}\n{footer}"}
    if target == "host":
        return {"to": f"Abuse contact of {infra.get('asn_org', 'hosting provider')} ({infra.get('asn', '')})", "subject": f"Abuse report: fraudulent website hosted at {infra.get('ip', dom)}",
                "body": f"A fraudulent website ({dom}) is hosted on {infra.get('ip', 'your network')}. Please disable it and preserve logs for law enforcement.\nFindings:\n{sigs}\n{footer}"}
    if target == "safebrowsing":
        return {"to": "Google Safe Browsing - report phishing", "subject": f"Phishing page: {dom}",
                "body": f"URL: {ctx.get('final_url') or ctx['input_url']}\nCategory: phishing / social engineering\nFindings:\n{sigs}\n{footer}"}
    if target == "maps":
        listings = [r for r in ctx.get("related", []) if r.get("kind") == "maps_listing"]
        names = "\n".join(f"  - {r['label']}" for r in listings) or "  - (none linked)"
        return {"to": "Google Maps - report a problem with a place", "subject": "Fraudulent business listings linked to a scam campaign",
                "body": f"The following listings share contact details with a scam campaign:\n{names}\nCampaign {ctx.get('cluster_id') or ''}, linked site {dom}.\n{footer}"}
    return {"to": "", "subject": "", "body": ""}


def blocklist_csv(ctx: dict) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["domain", "role", "score", "verdict", "campaign", "link_strength", "evidence_manifest"])
    w.writerow([ctx["domain"], "this case", ctx["score"], ctx["verdict"], ctx.get("cluster_id") or "", "", ctx["manifest"]])
    for r in ctx.get("related", []):
        if r.get("kind") == "site" and r["strength"] in ("strong", "medium") and r["verdict"] in ("confirmed_scam", "likely_scam"):
            w.writerow([registrable(r["host"]), "linked site", r["score"], r["verdict"], ctx.get("cluster_id") or "", r["strength"], ""])
    return buf.getvalue()


def action_pack(ctx: dict) -> dict:
    return {
        "warning": public_warning(ctx),
        "takedowns": {t: takedown_draft(ctx, t) for t in ("registrar", "host", "safebrowsing", "maps")},
        "blocklist_csv": blocklist_csv(ctx),
    }


# --------------------------------------------------------------------------- PDF

def _arabic(text: str) -> str:
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display

        return get_display(arabic_reshaper.reshape(text))
    except Exception:
        return text


def _arabic_font() -> str | None:
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    for path in ("C:/Windows/Fonts/tahoma.ttf", "C:/Windows/Fonts/arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/Library/Fonts/Arial Unicode.ttf"):
        if Path(path).is_file():
            try:
                pdfmetrics.registerFont(TTFont("RaqibAr", path))
                return "RaqibAr"
            except Exception:
                continue
    return None


def build_pdf(result: dict) -> bytes:
    from reportlab.graphics.shapes import Circle, Drawing, Line, String
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_RIGHT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    ctx, refined = result["ctx"], result["refined"]
    pack = action_pack(ctx)
    ss = getSampleStyleSheet()
    H1 = ParagraphStyle("H1", parent=ss["Heading1"], fontName="Helvetica-Bold", fontSize=18, textColor=colors.HexColor("#0B1B3A"), spaceAfter=4)
    H2 = ParagraphStyle("H2", parent=ss["Heading2"], fontName="Helvetica-Bold", fontSize=11.5, textColor=colors.HexColor("#0B1B3A"), spaceBefore=10, spaceAfter=4)
    P = ParagraphStyle("P", parent=ss["BodyText"], fontName="Helvetica", fontSize=9, leading=12.5)
    SM = ParagraphStyle("SM", parent=P, fontSize=7.5, leading=10, textColor=colors.HexColor("#495057"))
    MONO = ParagraphStyle("MONO", parent=P, fontName="Courier", fontSize=6.6, leading=8)
    tone = {"confirmed_scam": "#C92A2A", "likely_scam": "#E03131", "suspicious": "#E67700", "no_indicators": "#2B8A3E", "official": "#2B8A3E"}[ctx["verdict"]]

    def table(rows, widths, header=True):
        t = Table(rows, colWidths=widths, repeatRows=1 if header else 0)
        style = [("FONTSIZE", (0, 0), (-1, -1), 8), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#CED4DA")),
                 ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4)]
        if header:
            style += [("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E7EDF7")), ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold")]
        t.setStyle(TableStyle(style))
        return t

    story = [Paragraph("RAQIB · Scam investigation case report", H1),
             Paragraph(f"Case <b>{result['run_id'].upper()}</b> · generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} · evidence mode: {ctx.get('evidence_mode', 'replay')} · summary by: {result['source']}", SM),
             Spacer(1, 6)]
    hero = Table([[Paragraph(f"<font size=26 color='{tone}'><b>{ctx['score']}</b></font><font size=9 color='#495057'> / 100</font>", P),
                   Paragraph(f"<b>{refined['headline']}</b><br/><font size=8.5>{refined['summary']}</font>", P)]], colWidths=[28 * mm, 142 * mm])
    hero.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor(tone)), ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8F9FA")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 8)]))
    story += [hero, Paragraph("Subject", H2), table([["Input URL", ctx["input_url"]], ["Final URL", ctx.get("final_url") or "-"], ["Domain", ctx["domain"]], ["Scam type", ctx["scam_label"]["en"]],
                                                    ["Impersonated", (ctx.get("brand") or {}).get("name", "-")], ["Campaign", f"{ctx.get('cluster_id') or '-'} ({ctx.get('cluster_size', 1)} sites)"],
                                                    ["Public blocklist", "listed" if ctx.get("on_blocklist") else "not listed"]], [35 * mm, 135 * mm], header=False)]
    shot = config.EVIDENCE_DIR / result["run_id"] / "p1.png"
    if shot.is_file():
        from reportlab.platypus import Image as RLImage

        img = RLImage(str(shot))
        ratio = img.imageHeight / float(img.imageWidth or 1)
        img.drawWidth, img.drawHeight = 52 * mm, 52 * mm * ratio
        chain = " → ".join(h["url"] for h in ctx.get("redirect_chain", [])[:4]) or ctx.get("final_url") or ctx["input_url"]
        side = [Paragraph("<b>Screenshot captured by the isolated browser</b>", P), Spacer(1, 4),
                Paragraph(f"Mobile Chrome, UAE locale. Captured {ctx.get('observed_at', '')}. SHA-256 in the evidence table.", SM), Spacer(1, 6),
                Paragraph("<b>Redirect chain</b>", P), Paragraph(chain, MONO)]
        t = Table([[img, side]], colWidths=[58 * mm, 112 * mm])
        t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
        story += [Paragraph("Evidence screenshot", H2), t]
    if ctx["verdict"] not in ("no_indicators", "official"):
        story += [Paragraph("How the victim is deceived", H2), Paragraph(refined["victim_impact"], P)]
    story += [Paragraph("Why this score", H2),
              table([["Signal", "Category", "Weight"]] + [[Paragraph(s["label"], P), s["category"], f"{int(s['weight'] * 100)}"] for s in sorted(ctx["signals"], key=lambda s: -s["weight"])], [115 * mm, 35 * mm, 20 * mm])]

    ind = [["Indicator", "Value"]]
    for k, label in (("telegram_bot_ids", "Telegram bot ID"), ("discord_webhook_ids", "Discord webhook ID"), ("wallets", "Crypto wallet")):
        for v in ctx["iocs"].get(k, []):
            ind.append([label, v])
    for k, label in (("whatsapp", "WhatsApp"), ("phones", "Phone"), ("emails", "E-mail")):
        for v in ctx["contacts"].get(k, []):
            ind.append([label, v])
    if len(ind) > 1:
        story += [Paragraph("Indicators extracted", H2), table(ind, [50 * mm, 120 * mm])]

    if ctx.get("related"):
        story += [Paragraph(f"Campaign {ctx.get('cluster_id') or ''}: connected sites", H2)]
        d = Drawing(480, 250)
        cx, cy, R = 240, 125, 95
        import math

        rel = ctx["related"][:14]
        pos = {}
        for i, r in enumerate(rel):
            a = 2 * math.pi * i / max(len(rel), 1) - math.pi / 2
            pos[r["case_id"]] = (cx + R * 1.9 * math.cos(a), cy + R * 1.1 * math.sin(a))
        for r in rel:
            x, y = pos[r["case_id"]]
            ln = Line(cx, cy, x, y, strokeColor=colors.HexColor(STRENGTH_COLORS[r["strength"]]), strokeWidth=2 if r["strength"] == "strong" else 1)
            if r["strength"] == "weak":
                ln.strokeDashArray = [3, 3]
            d.add(ln)
        d.add(Circle(cx, cy, 9, fillColor=colors.HexColor(tone), strokeColor=colors.white))
        d.add(String(cx, cy - 18, ctx["domain"], fontSize=6.5, textAnchor="middle"))
        for r in rel:
            x, y = pos[r["case_id"]]
            d.add(Circle(x, y, 5.5, fillColor=colors.HexColor("#845EF7" if r.get("kind") == "maps_listing" else "#343A40"), strokeColor=colors.white))
            d.add(String(x, y - 12, r["host"][:30], fontSize=6, textAnchor="middle"))
        story += [d, table([["Site", "Score", "Link", "Why"]] + [[Paragraph(r["host"], SM), str(r["score"]), r["strength"], Paragraph(r["reasons"][0]["text"], SM)] for r in ctx["related"]],
                           [52 * mm, 14 * mm, 18 * mm, 86 * mm]),
                  Paragraph("Strong links are shared operator tooling or contact details (bot, wallet, phone, kit file). Weak links (layout, hosting) do not prove a shared operator.", SM)]

    i = ctx.get("infra", {})
    if i:
        story += [Paragraph("Infrastructure indicators", H2),
                  table([["Registered", f"{i.get('domain_created')} at {i.get('registrar')}"], ["Hosting", f"{i.get('asn_org')} ({i.get('asn')}), server {i.get('ip')}"],
                         ["Hosting country", f"{i.get('country')}  (infrastructure indicator only, not the operator's location)"], ["TLS certificate", f"issued {i.get('cert_issued')} by {i.get('cert_issuer')}"]],
                        [35 * mm, 135 * mm], header=False)]

    story += [Paragraph("Recommended actions", H2),
              table([["Priority", "Action"]] + [[a["priority"].upper(), Paragraph(a["label"], P)] for a in refined["recommended_actions"]], [22 * mm, 148 * mm])]
    story += [PageBreak(), Paragraph("Evidence chain of custody", H2),
              Paragraph(f"Manifest SHA-256: <font name='Courier' size=7>{ctx['manifest']}</font>. Every artefact was hashed when it was recorded; changing any of them changes the manifest.", P), Spacer(1, 4),
              table([["ID / kind", "Artefact", "SHA-256 · recorded (UTC)"]] + [[f"{e['id']}\n{e['kind']}", Paragraph(e["label"], SM), Paragraph(f"{e['sha256']}<br/>{e['ts']}", MONO)] for e in ctx["evidence"]],
                    [24 * mm, 66 * mm, 80 * mm])]
    story += [Paragraph("Public warning (draft)", H2), Paragraph(pack["warning"]["en"], P)]

    font = _arabic_font()
    if font:
        AR = ParagraphStyle("AR", parent=P, fontName=font, alignment=TA_RIGHT, fontSize=10, leading=15)
        ARH = ParagraphStyle("ARH", parent=AR, fontSize=13, leading=18, textColor=colors.HexColor("#0B1B3A"))
        story += [PageBreak(), Paragraph(_arabic("ملخص القضية"), ARH), Spacer(1, 4), Paragraph(_arabic(refined["headline_ar"]), ARH), Paragraph(_arabic(refined["summary_ar"]), AR),
                  Spacer(1, 6), Paragraph(_arabic("كيف يُخدع الضحية"), ARH), Paragraph(_arabic(refined["victim_impact_ar"]), AR), Spacer(1, 6),
                  Paragraph(_arabic("أسباب النتيجة"), ARH)] + [Paragraph(_arabic("• " + s["label_ar"]), AR) for s in sorted(ctx["signals"], key=lambda s: -s["weight"])] + \
                 [Spacer(1, 6), Paragraph(_arabic("الإجراءات الموصى بها"), ARH)] + [Paragraph(_arabic("• " + a["label_ar"]), AR) for a in refined["recommended_actions"]] + \
                 [Spacer(1, 6), Paragraph(_arabic("تنبيه للجمهور (مسودة)"), ARH), Paragraph(_arabic(pack["warning"]["ar"]), AR)]

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=16 * mm, bottomMargin=16 * mm, title=f"Raqib case {result['run_id']}", author="Raqib")

    def footer(canvas, _doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#868E96"))
        canvas.drawString(20 * mm, 10 * mm, f"Raqib · case {result['run_id'].upper()} · manifest {ctx['manifest'][:16]}… · decision support, officer review required")
        canvas.drawRightString(190 * mm, 10 * mm, f"Page {_doc.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()
