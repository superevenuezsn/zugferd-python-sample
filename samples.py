"""Three fake invoices covering the cases real clients have.

All companies, VAT IDs and bank details are fictional example data.
"""
from datetime import date
from decimal import Decimal as D

from einvoice import Address, Allowance, Invoice, Line, Party

SELLER = Party(
    name="Musterfirma Software GmbH",
    address=Address("Beispielstraße 12", "10115", "Berlin", "DE"),
    vat_id="DE123456789",
    email="rechnung@musterfirma.example",
)
BUYER_DE = Party(
    name="Beispiel Handels GmbH",
    address=Address("Hauptstraße 5", "80331", "München", "DE"),
    vat_id="DE987654321",
    email="buchhaltung@beispiel-handel.example",
)
BUYER_AT = Party(
    name="Muster Trading GmbH",
    address=Address("Ringstraße 20", "1010", "Wien", "AT"),
    vat_id="ATU12345678",
    email="office@muster-trading.example",
)
IBAN = "DE89370400440532013000"  # widely used example IBAN


# 1) Standard invoice: 19 % VAT, two lines, invoice-level discount
invoice = Invoice(
    number="RE-2026-0001",
    issue_date=date(2026, 9, 30),
    delivery_date=date(2026, 9, 26),
    due_date=date(2026, 10, 14),
    seller=SELLER,
    buyer=BUYER_DE,
    buyer_reference="PO-4711",
    lines=[
        Line("Webentwicklung – Kundenportal (September)", D("12"), "HUR", D("95.00"), D("19")),
        Line("Hosting-Paket Business", D("1"), "MON", D("49.00"), D("19")),
    ],
    allowances=[Allowance(D("50.00"), "Treuerabatt", D("19"))],
    iban=IBAN,
)

# 2) Correction / credit note (type 381) referencing invoice 1
credit_note = Invoice(
    number="RK-2026-0001",
    issue_date=date(2026, 10, 2),
    delivery_date=date(2026, 9, 26),
    due_date=date(2026, 10, 16),
    seller=SELLER,
    buyer=BUYER_DE,
    buyer_reference="PO-4711",
    type_code="381",
    preceding_invoice=("RE-2026-0001", date(2026, 9, 30)),
    note="Korrektur: Hosting-Paket wurde im September nicht genutzt.",
    lines=[Line("Hosting-Paket Business (Korrektur)", D("1"), "MON", D("49.00"), D("19"))],
    iban=IBAN,
)

# 3) Cross-border B2B service to Austria: reverse charge, 0 % VAT (category AE)
reverse_charge = Invoice(
    number="RE-2026-0002",
    issue_date=date(2026, 9, 30),
    delivery_date=date(2026, 9, 29),
    due_date=date(2026, 10, 14),
    seller=SELLER,
    buyer=BUYER_AT,
    buyer_reference="Projekt Alpha",
    lines=[Line("IT-Beratung E-Rechnung", D("8"), "HUR", D("120.00"), D("0"), vat_category="AE")],
    exemption_reason="Steuerschuldnerschaft des Leistungsempfängers (Reverse Charge).",
    iban=IBAN,
)

ALL = {
    "01_invoice_19pct_discount": invoice,
    "02_credit_note_381": credit_note,
    "03_reverse_charge_AT": reverse_charge,
}
