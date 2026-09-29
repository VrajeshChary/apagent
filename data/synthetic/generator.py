"""
Synthetic data generator for the Invoice Exception Resolution Agent.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from models.schemas import (
    Vendor, Invoice, InvoiceLineItem, InvoiceStatus,
    Exception_, ExceptionType, Resolution, ResolutionAction,
    NegotiationRecord, ApprovalRecord,
)

VENDORS = [
    Vendor("V001", "Dell Technologies",  "Net-45", "low",    "IT Hardware",
           "ap@dell.com", "Long-standing vendor. Typically ships with standard UPS ground. Shipping variances of ~$500 are common and historically approved."),
    Vendor("V002", "Staples Inc.",       "Net-30", "low",    "Office Supplies",
           "invoices@staples.com", "High-volume, low-value orders. Occasional quantity mismatches on bulk items."),
    Vendor("V003", "Acme Consulting",    "Net-60", "medium", "Professional Services",
           "billing@acmeconsulting.com", "Monthly retainer. Disputes usually around hours billed vs. contracted."),
    Vendor("V004", "CloudScale AWS",     "Net-30", "low",    "Cloud Services",
           "aws-billing@cloudscale.io", "Usage-based billing. Tax discrepancies due to multi-state operations."),
    Vendor("V005", "FreshOffice Catering","Net-15", "medium","Facilities",
           "orders@freshoffice.com", "Event-based ordering. Frequent price variance on seasonal items."),
    Vendor("V006", "Pinnacle Security",  "Net-45", "high",   "Security Services",
           "accounts@pinnaclesec.com", "Strict contract terms. Any variance should be escalated."),
    Vendor("V007", "GlobalFreight Logistics","Net-30","medium","Logistics",
           "billing@globalfreight.com", "Shipping cost variances are common due to fuel surcharges."),
]

VENDOR_CONTRACTS = [
    {
        "vendor": "Dell Technologies",
        "contract_id": "CTR-2024-001",
        "payment_terms": "Net-45",
        "shipping_terms": "FOB Destination. Standard UPS ground. Freight charges may vary by +/- $500 per shipment.",
        "price_protection": "Locked pricing. Price increases capped at 5% annually.",
        "notes": "Dell is an approved vendor. No PO required for orders under $1,000.",
    },
    {
        "vendor": "Staples Inc.",
        "contract_id": "CTR-2024-002",
        "payment_terms": "Net-30",
        "shipping_terms": "Free shipping on orders over $50.",
        "price_protection": "Price variance tolerance: 2%.",
        "notes": "Auto-approval for orders under $500.",
    },
    {
        "vendor": "Acme Consulting",
        "contract_id": "CTR-2023-009",
        "payment_terms": "Net-60",
        "shipping_terms": "N/A - Professional services",
        "price_protection": "Fixed monthly retainer of $15,000. Additional hours billed at $200/hr.",
        "notes": "Hours over 80 require pre-approval from VP Engineering.",
    },
    {
        "vendor": "CloudScale AWS",
        "contract_id": "CTR-2024-005",
        "payment_terms": "Net-30",
        "shipping_terms": "N/A - Cloud services",
        "price_protection": "Usage-based.",
        "notes": "Tax varies by region. Multi-state tax discrepancies <$200 can be auto-approved.",
    },
    {
        "vendor": "Pinnacle Security",
        "contract_id": "CTR-2024-010",
        "payment_terms": "Net-45",
        "shipping_terms": "On-site service.",
        "price_protection": "Fixed annual contract $120,000.",
        "notes": "HIGH RISK: All variances must be escalated to Security Director. No auto-approvals.",
    }
]

NEGOTIATION_EMAILS = [
    NegotiationRecord(
        record_id="NEG001", vendor_name="Dell Technologies",
        date=date(2025, 3, 15),
        subject="Re: Shipping charge discrepancy on PO-2025-0342",
        body="We noticed a $487 shipping variance. We've agreed to absorb this one-time variance.",
        outcome="Variance approved as one-time exception",
        negotiated_terms="Standard shipping variance tolerance remains +/- $500.",
    ),
    NegotiationRecord(
        record_id="NEG002", vendor_name="Dell Technologies",
        date=date(2025, 7, 22),
        subject="Re: Invoice INV-D-1087 - $520 shipping overage",
        body="Invoice shows $520 in shipping. Since this is $20 over, we're approving it this time but requesting a credit memo.",
        outcome="Approved with $20 credit memo issued",
        negotiated_terms="Dell agreed to issue CM-2025-0044 for $20. Threshold remains $500.",
    ),
    NegotiationRecord(
        record_id="NEG004", vendor_name="Acme Consulting",
        date=date(2025, 4, 2),
        subject="April invoice - 12 hours over retainer",
        body="Your April invoice shows 92 hours billed. Our retainer covers 80 hours. The additional 12 hours were verbally requested. We'll approve but need written approval going forward.",
        outcome="Approved with reminder for written pre-approval on overages",
        negotiated_terms="All hours exceeding retainer must have email approval from VP Engineering.",
    ),
    NegotiationRecord(
        record_id="NEG006", vendor_name="Pinnacle Security",
        date=date(2025, 8, 5),
        subject="Unauthorized change order on security install",
        body="Invoice includes $3,200 for additional camera installation that was not in our contract. We are disputing this charge.",
        outcome="Charge disputed. Escalated to Security Director.",
        negotiated_terms="All change orders MUST be in writing.",
    ),
]

APPROVAL_RECORDS = [
    ApprovalRecord("APR001", "Dell Technologies", date(2025, 1, 20), "shipping_variance", 350.0, "approved", "Sarah Chen", "Within $500 threshold."),
    ApprovalRecord("APR002", "Dell Technologies", date(2025, 3, 15), "shipping_variance", 487.0, "approved", "Sarah Chen", "One-time exception."),
    ApprovalRecord("APR003", "Dell Technologies", date(2025, 5, 8), "shipping_variance", 500.0, "approved", "Sarah Chen", "At threshold limit."),
    ApprovalRecord("APR006", "Staples Inc.", date(2025, 3, 5), "quantity_mismatch", 45.0, "approved", "Sarah Chen", "Short-shipped 20 units."),
    ApprovalRecord("APR008", "Acme Consulting", date(2025, 4, 2), "price_variance", 2400.0, "approved", "VP Engineering", "12 hours over retainer. VP confirmed."),
    ApprovalRecord("APR009", "Acme Consulting", date(2025, 6, 30), "price_variance", 800.0, "rejected", "VP Engineering", "4 hours over retainer. No pre-approval. Rejected."),
    ApprovalRecord("APR012", "Pinnacle Security", date(2025, 8, 5), "price_variance", 3200.0, "escalated_to_human", "Security Director", "Unauthorized change order."),
]

def _vendor(name: str) -> Vendor:
    return next(v for v in VENDORS if v.name == name)

SAMPLE_INVOICES = [
    Invoice(
        invoice_id="INV-2025-1001",
        vendor=_vendor("Dell Technologies"),
        invoice_date=date(2025, 9, 25),
        due_date=date(2025, 11, 9),
        po_number="PO-2025-0567",
        subtotal=12500.00,
        tax=1062.50,
        shipping=500.00,
        total=14062.50,
        line_items=[InvoiceLineItem("Dell Latitude Laptop", 5, 2500.00, 12500.00, "PO-1")],
    ),
    Invoice(
        invoice_id="INV-2025-1003",
        vendor=_vendor("Acme Consulting"),
        invoice_date=date(2025, 9, 30),
        due_date=date(2025, 11, 29),
        po_number="PO-2025-RET-09",
        subtotal=17400.00,
        tax=0.00,
        shipping=0.00,
        total=17400.00,
        line_items=[
            InvoiceLineItem("Monthly retainer", 1, 15000.00, 15000.00, "RET-L1"),
            InvoiceLineItem("Additional hours", 12, 200.00, 2400.00, "RET-L2"),
        ],
    ),
    Invoice(
        invoice_id="INV-2025-1005",
        vendor=_vendor("Pinnacle Security"),
        invoice_date=date(2025, 9, 15),
        due_date=date(2025, 10, 30),
        po_number="PO-2025-SEC-04",
        subtotal=13200.00,
        tax=1122.00,
        shipping=0.00,
        total=14322.00,
        line_items=[
            InvoiceLineItem("Monthly security service", 1, 10000.00, 10000.00, "SEC-L1"),
            InvoiceLineItem("Additional camera install (unauthorized)", 1, 3200.00, 3200.00, "SEC-L2"),
        ],
    ),
]

def contracts_to_documents() -> list[dict]:
    docs = []
    for c in VENDOR_CONTRACTS:
        docs.append({
            "id": c["contract_id"],
            "text": str(c),
            "metadata": {"type": "vendor_contract", "vendor": c["vendor"]},
        })
    return docs

def negotiations_to_documents() -> list[dict]:
    docs = []
    for n in NEGOTIATION_EMAILS:
        docs.append({
            "id": n.record_id,
            "text": f"Subject: {n.subject}\nBody: {n.body}\nOutcome: {n.outcome}",
            "metadata": {"type": "negotiation_email", "vendor": n.vendor_name},
        })
    return docs

def approvals_to_documents() -> list[dict]:
    docs = []
    for a in APPROVAL_RECORDS:
        docs.append({
            "id": a.record_id,
            "text": f"Exception: {a.exception_type}, Variance: ${a.variance_amount}, Decision: {a.decision} ({a.notes})",
            "metadata": {"type": "approval_record", "vendor": a.vendor_name, "decision": a.decision},
        })
    return docs

def vendors_to_documents() -> list[dict]:
    docs = []
    for v in VENDORS:
        docs.append({
            "id": v.vendor_id,
            "text": f"Vendor: {v.name}\nTier: {v.risk_tier}\nNotes: {v.historical_notes}",
            "metadata": {"type": "vendor_profile", "vendor": v.name},
        })
    return docs

def get_all_documents() -> list[dict]:
    return vendors_to_documents() + contracts_to_documents() + negotiations_to_documents() + approvals_to_documents()
