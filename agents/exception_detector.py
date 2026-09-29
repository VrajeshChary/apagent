"""
Exception Detection Engine
==========================
Scans invoices for discrepancies against expected values / contracts,
then uses Hindsight recall() to find similar past cases.
"""
from __future__ import annotations

import re
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from models.schemas import (
    Invoice, Exception_, ExceptionType, InvoiceStatus,
)
from data.synthetic.generator import VENDORS, VENDOR_CONTRACTS, SAMPLE_INVOICES


def _get_contract(vendor_name: str) -> dict | None:
    for c in VENDOR_CONTRACTS:
        if c["vendor"] == vendor_name:
            return c
    return None


def detect_exceptions(invoice: Invoice) -> list[Exception_]:
    """Apply rule-based detection to find invoice exceptions."""
    exceptions: list[Exception_] = []
    contract = _get_contract(invoice.vendor.name)

    # Rule 1: Shipping variance
    if invoice.shipping > 0 and contract:
        shipping_terms = contract.get("shipping_terms", "")
        if "free shipping" in shipping_terms.lower() and invoice.shipping > 0:
            exceptions.append(Exception_(
                invoice_id=invoice.invoice_id,
                vendor_name=invoice.vendor.name,
                exception_type=ExceptionType.SHIPPING_VARIANCE,
                description=f"Shipping charged ${invoice.shipping:.2f} but contract says free shipping.",
                expected_value=0.0,
                actual_value=invoice.shipping,
                variance_amount=invoice.shipping,
                variance_pct=100.0,
            ))
        elif "FOB" in shipping_terms and invoice.shipping > 0:
            exceptions.append(Exception_(
                invoice_id=invoice.invoice_id,
                vendor_name=invoice.vendor.name,
                exception_type=ExceptionType.SHIPPING_VARIANCE,
                description=(
                    f"Shipping charge of ${invoice.shipping:.2f} on FOB Destination shipment. "
                    f"Contract allows +/- $500 variance."
                ),
                expected_value=0.0,
                actual_value=invoice.shipping,
                variance_amount=invoice.shipping,
                variance_pct=100.0,
            ))

    # Rule 2: Price variance on line items
    for item in invoice.line_items:
        if "additional" in item.description.lower() or "unauthorized" in item.description.lower():
            exceptions.append(Exception_(
                invoice_id=invoice.invoice_id,
                vendor_name=invoice.vendor.name,
                exception_type=ExceptionType.PRICE_VARIANCE,
                description=(
                    f"Line item '{item.description}' for ${item.total:.2f} "
                    f"appears to be outside standard contract scope."
                ),
                expected_value=0.0,
                actual_value=item.total,
                variance_amount=item.total,
            ))

    # Rule 3: Retainer overage
    if contract and "retainer" in contract.get("price_protection", "").lower():
        price_prot = contract["price_protection"].replace('`', '')
        match = re.search(r'\$(\d[\d,]*)', price_prot)
        if match:
            retainer_amount = float(match.group(1).replace(",", ""))
            extra_lines = [li for li in invoice.line_items if "additional" in li.description.lower()]
            if extra_lines:
                overage = sum(li.total for li in extra_lines)
                exceptions.append(Exception_(
                    invoice_id=invoice.invoice_id,
                    vendor_name=invoice.vendor.name,
                    exception_type=ExceptionType.PRICE_VARIANCE,
                    description=(
                        f"Invoice exceeds retainer by ${overage:.2f}. "
                        f"Retainer is ${retainer_amount:.2f}/month. "
                        f"Additional hours require pre-approval."
                    ),
                    expected_value=retainer_amount,
                    actual_value=invoice.subtotal,
                    variance_amount=overage,
                    variance_pct=round(overage / retainer_amount * 100, 1),
                ))

    # Rule 4: Tax discrepancy
    if invoice.tax > 0 and contract:
        notes = contract.get("notes", "")
        if "tax exemption" in notes.lower() or "tax discrepanc" in notes.lower():
            exceptions.append(Exception_(
                invoice_id=invoice.invoice_id,
                vendor_name=invoice.vendor.name,
                exception_type=ExceptionType.TAX_DISCREPANCY,
                description=(
                    f"Tax charge of ${invoice.tax:.2f}. "
                    f"Vendor has tax exemption or special tax handling notes."
                ),
                expected_value=0.0,
                actual_value=invoice.tax,
                variance_amount=invoice.tax,
            ))

    # Rule 5: Payment terms check
    if contract:
        contract_terms = contract.get("payment_terms", "")
        vendor_terms = invoice.vendor.payment_terms
        if contract_terms and vendor_terms and contract_terms != vendor_terms:
            exceptions.append(Exception_(
                invoice_id=invoice.invoice_id,
                vendor_name=invoice.vendor.name,
                exception_type=ExceptionType.PAYMENT_TERMS_MISMATCH,
                description=(
                    f"Invoice vendor terms '{vendor_terms}' don't match "
                    f"contract terms '{contract_terms}'."
                ),
            ))

    return exceptions


def scan_all_invoices() -> dict[str, list[Exception_]]:
    """Scan all sample invoices and return exceptions grouped by invoice ID."""
    results = {}
    for inv in SAMPLE_INVOICES:
        exceptions = detect_exceptions(inv)
        if exceptions:
            results[inv.invoice_id] = exceptions
    return results


def main():
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel

    console = Console()
    console.print(Panel.fit(
        "[bold cyan]Invoice Exception Scanner[/bold cyan]",
        border_style="cyan",
    ))

    all_exceptions = scan_all_invoices()

    for inv_id, exceptions in all_exceptions.items():
        inv = next(i for i in SAMPLE_INVOICES if i.invoice_id == inv_id)
        console.print(f"\n  [bold]{inv_id}[/bold] - {inv.vendor.name} - ${inv.total:,.2f}")

        table = Table(show_header=True, header_style="bold red", padding=(0, 1))
        table.add_column("Type", width=22)
        table.add_column("Variance", width=12)
        table.add_column("Description", width=60)

        for exc in exceptions:
            table.add_row(
                exc.exception_type.value,
                f"${exc.variance_amount:,.2f}" if exc.variance_amount else "-",
                exc.description[:80],
            )

        console.print(table)

    total = sum(len(e) for e in all_exceptions.values())
    console.print(f"\n  Total: [bold]{total}[/bold] exceptions across "
                  f"[bold]{len(all_exceptions)}[/bold] invoices\n")


if __name__ == "__main__":
    main()