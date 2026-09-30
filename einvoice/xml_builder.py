"""Build the structured invoice data (CII XML, EN 16931 profile) with drafthorse."""
from __future__ import annotations

from decimal import Decimal

from drafthorse.models.accounting import (
    ApplicableTradeTax,
    CategoryTradeTax,
    TradeAllowanceCharge,
)
from drafthorse.models.document import Document
from drafthorse.models.note import IncludedNote
from drafthorse.models.party import TaxRegistration
from drafthorse.models.payment import PaymentMeans, PaymentTerms
from drafthorse.models.tradelines import LineItem

from .model import Invoice, Party

EN16931_GUIDELINE = "urn:cen.eu:en16931:2017"
PAYMENT_SEPA_TRANSFER = "58"
VATEX_REVERSE_CHARGE = "VATEX-EU-AE"


def _fill_party(target, party: Party) -> None:
    target.name = party.name
    target.address.line_one = party.address.street
    target.address.postcode = party.address.postcode
    target.address.city_name = party.address.city
    target.address.country_id = party.address.country
    if party.email:
        target.electronic_address.uri_ID = ("EM", party.email)
    if party.vat_id:
        target.tax_registrations.add(TaxRegistration(id=("VA", party.vat_id)))
    if party.tax_number:
        target.tax_registrations.add(TaxRegistration(id=("FC", party.tax_number)))


def build_xml(inv: Invoice) -> bytes:
    doc = Document()
    doc.context.guideline_parameter.id = EN16931_GUIDELINE

    # --- header ---
    doc.header.id = inv.number
    doc.header.type_code = inv.type_code
    doc.header.issue_date_time = inv.issue_date
    if inv.note:
        note = IncludedNote()
        note.content = inv.note
        doc.header.notes.add(note)

    # --- parties ---
    agreement = doc.trade.agreement
    if inv.buyer_reference:
        agreement.buyer_reference = inv.buyer_reference
    _fill_party(agreement.seller, inv.seller)
    _fill_party(agreement.buyer, inv.buyer)

    # --- delivery date (Leistungsdatum, BT-72) ---
    doc.trade.delivery.event.occurrence = inv.delivery_date

    # --- lines ---
    for i, l in enumerate(inv.lines, start=1):
        li = LineItem()
        li.document.line_id = str(i)
        li.product.name = l.description
        li.agreement.net.amount = l.unit_price
        li.delivery.billed_quantity = (l.quantity, l.unit_code)
        li.settlement.trade_tax.type_code = "VAT"
        li.settlement.trade_tax.category_code = l.vat_category
        li.settlement.trade_tax.rate_applicable_percent = l.vat_rate
        li.settlement.monetary_summation.total_amount = l.net_amount
        doc.trade.items.add(li)

    # --- settlement ---
    s = doc.trade.settlement
    s.currency_code = inv.currency

    pm = PaymentMeans()
    pm.type_code = PAYMENT_SEPA_TRANSFER
    pm.payee_account.iban = inv.iban
    s.payment_means.add(pm)

    if inv.preceding_invoice:
        number, issued = inv.preceding_invoice
        s.invoice_referenced_document.issuer_assigned_id = number
        s.invoice_referenced_document.issue_date_time = issued

    for a in inv.allowances:
        ac = TradeAllowanceCharge()
        ac.indicator = False  # False = allowance (discount), True = charge
        ac.actual_amount = a.amount
        ac.reason = a.reason
        ac.trade_tax.add(
            CategoryTradeTax(type_code="VAT", category_code=a.vat_category,
                             rate_applicable_percent=a.vat_rate)
        )
        s.allowance_charge.add(ac)

    for g in inv.vat_breakdown():
        t = ApplicableTradeTax()
        t.calculated_amount = g["tax"]
        t.basis_amount = g["basis"]
        t.type_code = "VAT"
        t.category_code = g["category"]
        t.rate_applicable_percent = g["rate"]
        if g["category"] == "AE":
            t.exemption_reason = inv.exemption_reason or "Reverse charge"
            t.exemption_reason_code = VATEX_REVERSE_CHARGE
        s.trade_tax.add(t)

    terms = PaymentTerms()
    terms.description = f"Zahlbar bis {inv.due_date:%d.%m.%Y} ohne Abzug."
    terms.due = inv.due_date
    s.terms.add(terms)

    m = s.monetary_summation
    m.line_total = inv.line_total
    m.charge_total = Decimal("0.00")
    m.allowance_total = inv.allowance_total
    m.tax_basis_total = inv.tax_basis_total
    m.tax_total = (inv.tax_total, inv.currency)
    m.grand_total = inv.grand_total
    m.due_amount = inv.grand_total

    return doc.serialize(schema="FACTUR-X_EN16931")
