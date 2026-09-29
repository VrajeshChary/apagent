"""
Data models for invoices, vendors, exceptions, and resolutions.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, date
from enum import Enum
from typing import Optional


class ExceptionType(str, Enum):
    PRICE_VARIANCE = "price_variance"
    QUANTITY_MISMATCH = "quantity_mismatch"
    SHIPPING_VARIANCE = "shipping_variance"
    TAX_DISCREPANCY = "tax_discrepancy"
    DUPLICATE_INVOICE = "duplicate_invoice"
    MISSING_PO = "missing_purchase_order"
    PAYMENT_TERMS_MISMATCH = "payment_terms_mismatch"
    UNAPPROVED_VENDOR = "unapproved_vendor"


class ResolutionAction(str, Enum):
    AUTO_APPROVED = "auto_approved"
    APPROVED_WITH_ADJUSTMENT = "approved_with_adjustment"
    ESCALATED_TO_HUMAN = "escalated_to_human"
    REJECTED = "rejected"
    PENDING_REVIEW = "pending_review"


class InvoiceStatus(str, Enum):
    RECEIVED = "received"
    PROCESSING = "processing"
    EXCEPTION = "exception"
    RESOLVED = "resolved"
    PAID = "paid"
    REJECTED = "rejected"


@dataclass
class Vendor:
    vendor_id: str
    name: str
    payment_terms: str  # e.g. "Net-30", "Net-45"
    risk_tier: str      # "low", "medium", "high"
    category: str       # "IT Hardware", "Office Supplies", etc.
    contact_email: str = ""
    historical_notes: str = ""


@dataclass
class InvoiceLineItem:
    description: str
    quantity: int
    unit_price: float
    total: float
    po_line_ref: str = ""


@dataclass
class Invoice:
    invoice_id: str
    vendor: Vendor
    invoice_date: date
    due_date: date
    po_number: str
    subtotal: float
    tax: float
    shipping: float
    total: float
    line_items: list[InvoiceLineItem] = field(default_factory=list)
    status: InvoiceStatus = InvoiceStatus.RECEIVED
    currency: str = "USD"


@dataclass
class Exception_:
    """An exception/discrepancy detected on an invoice."""
    exception_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    invoice_id: str = ""
    vendor_name: str = ""
    exception_type: ExceptionType = ExceptionType.PRICE_VARIANCE
    description: str = ""
    expected_value: float = 0.0
    actual_value: float = 0.0
    variance_amount: float = 0.0
    variance_pct: float = 0.0
    detected_at: datetime = field(default_factory=datetime.now)


@dataclass
class Resolution:
    """Resolution decision for an exception."""
    resolution_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    exception_id: str = ""
    action: ResolutionAction = ResolutionAction.PENDING_REVIEW
    confidence: float = 0.0
    reasoning: str = ""
    similar_cases_found: int = 0
    similar_cases_summary: str = ""
    approved_by: str = "agent"  # "agent" or human name
    resolved_at: datetime = field(default_factory=datetime.now)


@dataclass
class NegotiationRecord:
    """A past negotiation email/event."""
    record_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    vendor_name: str = ""
    date: date = field(default_factory=date.today)
    subject: str = ""
    body: str = ""
    outcome: str = ""
    negotiated_terms: str = ""


@dataclass
class ApprovalRecord:
    """A past human approval decision."""
    record_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    vendor_name: str = ""
    date: date = field(default_factory=date.today)
    exception_type: str = ""
    variance_amount: float = 0.0
    decision: str = ""   # "approved", "rejected", "adjusted"
    approver: str = ""
    notes: str = ""
