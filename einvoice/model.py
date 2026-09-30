"""Plain data model for an invoice.

This is deliberately independent of any e-invoice library. In a client project,
the only code you write per client is a function that fills these objects from
*their* database. Everything after that (XML, PDF, validation) stays the same.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

CENT = Decimal("0.01")


def money(value: Decimal) -> Decimal:
    """Round to cents the commercial way (0.005 -> 0.01)."""
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


@dataclass
class Address:
    street: str
    postcode: str
    city: str
    country: str  # ISO 3166-1 alpha-2, e.g. "DE"


@dataclass
class Party:
    name: str
    address: Address
    vat_id: Optional[str] = None      # USt-IdNr., e.g. DE123456789
    tax_number: Optional[str] = None  # Steuernummer (alternative to VAT ID for the seller)
    email: Optional[str] = None       # electronic address (BT-34 / BT-49)


@dataclass
class Line:
    description: str
    quantity: Decimal
    unit_code: str        # UN/ECE Rec 20: C62 = piece, HUR = hour, MON = month
    unit_price: Decimal   # net price per unit
    vat_rate: Decimal     # e.g. Decimal("19")
    vat_category: str = "S"  # S = standard, AE = reverse charge, Z = zero, E = exempt

    @property
    def net_amount(self) -> Decimal:
        return money(self.quantity * self.unit_price)


@dataclass
class Allowance:
    """Invoice-level discount (Nachlass)."""
    amount: Decimal
    reason: str
    vat_rate: Decimal
    vat_category: str = "S"


@dataclass
class Invoice:
    number: str
    issue_date: date
    delivery_date: date                 # Leistungsdatum
    due_date: date
    seller: Party
    buyer: Party
    lines: list[Line]
    iban: str
    currency: str = "EUR"
    type_code: str = "380"              # 380 = invoice, 381 = credit note / correction
    buyer_reference: Optional[str] = None   # BT-10, e.g. PO number or Leitweg-ID (B2G)
    allowances: list[Allowance] = field(default_factory=list)
    preceding_invoice: Optional[tuple[str, date]] = None  # BT-25/26 for corrections
    note: Optional[str] = None
    exemption_reason: Optional[str] = None  # text shown for AE / exempt lines

    # ---- totals (EN 16931 calculation rules BR-CO-10 ... BR-CO-16) ----
    @property
    def line_total(self) -> Decimal:
        return money(sum((l.net_amount for l in self.lines), Decimal("0")))

    @property
    def allowance_total(self) -> Decimal:
        return money(sum((a.amount for a in self.allowances), Decimal("0")))

    def vat_breakdown(self) -> list[dict]:
        """One entry per (category, rate): basis, tax."""
        groups: dict[tuple[str, Decimal], Decimal] = {}
        for l in self.lines:
            key = (l.vat_category, l.vat_rate)
            groups[key] = groups.get(key, Decimal("0")) + l.net_amount
        for a in self.allowances:
            key = (a.vat_category, a.vat_rate)
            groups[key] = groups.get(key, Decimal("0")) - a.amount
        out = []
        for (cat, rate), basis in groups.items():
            basis = money(basis)
            out.append({
                "category": cat,
                "rate": rate,
                "basis": basis,
                "tax": money(basis * rate / Decimal("100")),
            })
        return out

    @property
    def tax_basis_total(self) -> Decimal:
        return money(self.line_total - self.allowance_total)

    @property
    def tax_total(self) -> Decimal:
        return money(sum((g["tax"] for g in self.vat_breakdown()), Decimal("0")))

    @property
    def grand_total(self) -> Decimal:
        return money(self.tax_basis_total + self.tax_total)
