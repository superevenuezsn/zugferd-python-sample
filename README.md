# ZUGFeRD / Factur-X e-invoices from Python

Turns plain invoice data into **valid German e-invoices** (ZUGFeRD 2.x, EN 16931 profile):
a normal-looking PDF with the machine-readable XML embedded inside, as required for
domestic B2B invoices in Germany from **1 January 2027** (turnover > €800k) and
**1 January 2028** (everyone).

All three sample files pass the Mustangproject validator with **0 errors**
(EN 16931 business rules + PDF/A-3 check). Reports are in [`reports/`](reports/).

| Sample | Case | Net | VAT | Gross | Validation |
|---|---|---:|---:|---:|---|
| `01_invoice_19pct_discount` | Standard invoice, 19 % VAT, two lines, invoice-level discount | 1.139,00 € | 216,41 € | 1.355,41 € | ✅ valid |
| `02_credit_note_381` | Correction (type 381) referencing the original invoice | 49,00 € | 9,31 € | 58,31 € | ✅ valid |
| `03_reverse_charge_AT` | B2B service to Austria, reverse charge (category AE, 0 %) | 960,00 € | 0,00 € | 960,00 € | ✅ valid |

## How it works

```
your system's invoice data
        │  (the only client-specific part: map DB fields → einvoice.Invoice)
        ▼
einvoice/model.py        plain dataclasses + EN 16931 total calculation (cent-exact)
einvoice/xml_builder.py  CII XML, profile urn:cen.eu:en16931:2017   (drafthorse)
einvoice/pdf_renderer.py visual invoice, embedded fonts              (reportlab)
einvoice/zugferd.py      sRGB output intent + embed XML → PDF/A-3    (pypdf, factur-x)
        ▼
output/*.pdf  (ZUGFeRD)   output/*.xml  (raw XML)
        ▼
validate.sh   Mustangproject: EN 16931 schematron + veraPDF
```

## Run it

```bash
pip install -r requirements.txt
python main.py                      # writes output/*.pdf and output/*.xml

# validation (needs Java 11+)
# download Mustang-CLI-*.jar from https://github.com/ZUGFeRD/mustangproject/releases
MUSTANG_JAR=path/to/Mustang-CLI.jar ./validate.sh
```

## Using it for a real system

1. Write one function that loads an invoice from the existing database and returns an
   `einvoice.Invoice` (seller, buyer, lines, VAT, IBAN, dates).
2. Call `make_zugferd(invoice)` where the old PDF was created, and send/store the result.
3. Run the validator in CI or before sending, so a broken invoice is never delivered.

Things that usually need attention in real data: missing buyer VAT IDs, rounding
differences between line and total amounts, credit notes, and mixed VAT rates.

## Notes

- Formats: ZUGFeRD 2.x = Factur-X (identical), EN 16931 profile. XRechnung (B2G) needs
  extra fields such as the Leitweg-ID in `buyer_reference`.
- All companies, VAT IDs and bank details are fictional example data.
- `einvoice/assets/DejaVuSans*.ttf` are the free DejaVu fonts (licence in `DejaVu-LICENSE.txt`), embedded as PDF/A requires.
- `einvoice/assets/sRGB.icc` is the standard sRGB colour profile (from the TeX Live
  `colorprofiles` package), used for the PDF/A output intent.
- This is a technical implementation, not tax advice.
