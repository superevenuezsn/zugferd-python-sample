"""Combine the visual PDF and the XML into one ZUGFeRD / Factur-X PDF/A-3 file."""
from __future__ import annotations

import io
from pathlib import Path

from facturx import generate_from_binary
from pypdf import PdfReader, PdfWriter
from pypdf.generic import (
    ArrayObject,
    DecodedStreamObject,
    DictionaryObject,
    NameObject,
    NumberObject,
    TextStringObject,
)

from .model import Invoice
from .pdf_renderer import render_pdf
from .xml_builder import build_xml

SRGB_PROFILE = Path(__file__).parent / "assets" / "sRGB.icc"


def add_srgb_output_intent(pdf: bytes) -> bytes:
    """PDF/A requires an output intent when RGB colours are used."""
    writer = PdfWriter(clone_from=PdfReader(io.BytesIO(pdf)))
    icc = DecodedStreamObject()
    icc.set_data(SRGB_PROFILE.read_bytes())
    icc[NameObject("/N")] = NumberObject(3)
    intent = DictionaryObject({
        NameObject("/Type"): NameObject("/OutputIntent"),
        NameObject("/S"): NameObject("/GTS_PDFA1"),
        NameObject("/OutputConditionIdentifier"): TextStringObject("sRGB IEC61966-2.1"),
        NameObject("/Info"): TextStringObject("sRGB IEC61966-2.1"),
        NameObject("/DestOutputProfile"): writer._add_object(icc),
    })
    writer._root_object[NameObject("/OutputIntents")] = ArrayObject([writer._add_object(intent)])
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def make_zugferd(inv: Invoice) -> tuple[bytes, bytes]:
    """Return (zugferd_pdf_bytes, xml_bytes)."""
    xml = build_xml(inv)
    pdf = add_srgb_output_intent(render_pdf(inv))
    zugferd_pdf = generate_from_binary(
        pdf,
        xml,
        flavor="factur-x",
        level="en16931",
        check_xsd=True,  # refuse to produce a file whose XML breaks the schema
        lang="de-DE",
        pdf_metadata={
            "author": inv.seller.name,
            "keywords": "Factur-X, ZUGFeRD, E-Rechnung",
            "title": f"{inv.seller.name}: Rechnung {inv.number}",
            "subject": f"Rechnung {inv.number}",
        },
    )
    return zugferd_pdf, xml
