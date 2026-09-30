"""Render the human-readable invoice PDF (the part people see).

Fonts are embedded (DejaVu) because PDF/A-3 forbids non-embedded fonts.
"""
from __future__ import annotations

import io
from decimal import Decimal
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.lib.styles import ParagraphStyle

from .model import Invoice

ASSETS = Path(__file__).parent / "assets"  # fonts ship with the project, works on Windows/Mac/Linux
pdfmetrics.registerFont(TTFont("DejaVu", str(ASSETS / "DejaVuSans.ttf")))
pdfmetrics.registerFont(TTFont("DejaVu-Bold", str(ASSETS / "DejaVuSans-Bold.ttf")))

UNIT_LABEL = {"C62": "Stk.", "HUR": "Std.", "MON": "Monat"}
TITLE = {"380": "RECHNUNG", "381": "RECHNUNGSKORREKTUR"}


def eur(value: Decimal) -> str:
    s = f"{value:,.2f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".") + " €"


def render_pdf(inv: Invoice) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=18 * mm, bottomMargin=18 * mm,
        title=f"{TITLE.get(inv.type_code, 'RECHNUNG')} {inv.number}",
        author=inv.seller.name,
    )
    body = ParagraphStyle("b", fontName="DejaVu", fontSize=9, leading=12)
    small = ParagraphStyle("s", parent=body, fontSize=7.5, textColor=colors.grey)
    h1 = ParagraphStyle("h1", parent=body, fontName="DejaVu-Bold", fontSize=16, leading=20)

    s, b = inv.seller, inv.buyer
    story = [
        Paragraph(f"{s.name} · {s.address.street} · {s.address.postcode} {s.address.city}", small),
        Spacer(1, 4 * mm),
        Paragraph(f"{b.name}<br/>{b.address.street}<br/>{b.address.postcode} {b.address.city}"
                  f"<br/>{b.address.country}"
                  + (f"<br/>USt-IdNr.: {b.vat_id}" if b.vat_id else ""), body),
        Spacer(1, 10 * mm),
        Paragraph(TITLE.get(inv.type_code, "RECHNUNG"), h1),
        Spacer(1, 3 * mm),
    ]

    meta = [
        ["Rechnungsnummer", inv.number],
        ["Rechnungsdatum", f"{inv.issue_date:%d.%m.%Y}"],
        ["Leistungsdatum", f"{inv.delivery_date:%d.%m.%Y}"],
    ]
    if inv.buyer_reference:
        meta.append(["Ihre Referenz", inv.buyer_reference])
    if inv.preceding_invoice:
        meta.append(["Bezieht sich auf", f"{inv.preceding_invoice[0]} vom "
                                          f"{inv.preceding_invoice[1]:%d.%m.%Y}"])
    t = Table(meta, colWidths=[40 * mm, 80 * mm], hAlign="LEFT")
    t.setStyle(TableStyle([("FONT", (0, 0), (-1, -1), "DejaVu", 9),
                           ("FONT", (0, 0), (0, -1), "DejaVu-Bold", 9)]))
    story += [t, Spacer(1, 6 * mm)]

    rows = [["Pos.", "Beschreibung", "Menge", "Einzelpreis", "USt.", "Betrag"]]
    for i, l in enumerate(inv.lines, 1):
        rows.append([str(i), Paragraph(l.description, body),
                     f"{l.quantity.normalize():f} {UNIT_LABEL.get(l.unit_code, l.unit_code)}",
                     eur(l.unit_price), f"{l.vat_rate.normalize():f} %", eur(l.net_amount)])
    lt = Table(rows, colWidths=[12 * mm, 68 * mm, 22 * mm, 26 * mm, 14 * mm, 28 * mm], repeatRows=1)
    lt.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -1), "DejaVu", 9),
        ("FONT", (0, 0), (-1, 0), "DejaVu-Bold", 9),
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, colors.black),
        ("LINEBELOW", (0, -1), (-1, -1), 0.4, colors.grey),
        ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story += [lt, Spacer(1, 4 * mm)]

    totals = [["Summe netto", eur(inv.line_total)]]
    for a in inv.allowances:
        totals.append([f"Nachlass ({a.reason})", "−" + eur(a.amount)])
    if inv.allowances:
        totals.append(["Netto nach Nachlass", eur(inv.tax_basis_total)])
    for g in inv.vat_breakdown():
        label = ("USt. 0 % (Reverse Charge)" if g["category"] == "AE"
                 else f"USt. {g['rate'].normalize():f} % auf {eur(g['basis'])}")
        totals.append([label, eur(g["tax"])])
    totals.append(["Gesamtbetrag", eur(inv.grand_total)])
    tt = Table(totals, colWidths=[70 * mm, 30 * mm], hAlign="RIGHT")
    tt.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -1), "DejaVu", 9),
        ("FONT", (0, -1), (-1, -1), "DejaVu-Bold", 10),
        ("LINEABOVE", (0, -1), (-1, -1), 0.8, colors.black),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
    ]))
    story += [tt, Spacer(1, 8 * mm)]

    if inv.exemption_reason:
        story.append(Paragraph(inv.exemption_reason, body))
        story.append(Spacer(1, 3 * mm))
    story.append(Paragraph(
        f"Bitte überweisen Sie den Betrag bis {inv.due_date:%d.%m.%Y} auf IBAN {inv.iban}.", body))
    story.append(Spacer(1, 10 * mm))
    ids = []
    if s.vat_id:
        ids.append(f"USt-IdNr.: {s.vat_id}")
    if s.tax_number:
        ids.append(f"Steuernummer: {s.tax_number}")
    story.append(Paragraph(" · ".join([s.name] + ids + ([s.email] if s.email else [])), small))
    story.append(Paragraph("Musterdaten – Beispielrechnung zu Demonstrationszwecken.", small))

    doc.build(story)
    return buf.getvalue()
