"""Generate ZUGFeRD e-invoices for all samples into ./output"""
from pathlib import Path

from einvoice import make_zugferd
from samples import ALL

OUT = Path(__file__).parent / "output"


def main() -> None:
    OUT.mkdir(exist_ok=True)
    for name, inv in ALL.items():
        pdf, xml = make_zugferd(inv)
        (OUT / f"{name}.pdf").write_bytes(pdf)
        (OUT / f"{name}.xml").write_bytes(xml)
        print(f"{name}: net {inv.tax_basis_total}  VAT {inv.tax_total}  gross {inv.grand_total}")


if __name__ == "__main__":
    main()
