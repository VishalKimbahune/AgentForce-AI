"""Finance AI Employee: Invoice extraction, PO reconciliation, duplicate/anomaly detection, and payment batch compilation."""

import logging
import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.services.tools.mock_erp import mock_erp

logger = logging.getLogger("agents.finance")

# -------------------------------------------------------------
# SEEDED MOCK INVOICES (Conforming to docs/05 Section 6: 12 invoices)
# -------------------------------------------------------------

SAMPLE_INVOICES: List[Dict[str, Any]] = [
    # 1. Clean - matches PO-1001
    {
        "invoice_number": "INV-101",
        "vendor": "CloudScale Hosting Ltd",
        "po_number": "PO-1001",
        "amount": 12450.00,
        "date": "2026-10-15",
        "due_date": "2026-11-15",
        "description": "Enterprise cloud compute infrastructure",
        "department": "Engineering",
    },
    # 2. Clean - matches PO-1002
    {
        "invoice_number": "INV-102",
        "vendor": "OfficeMax Corporate",
        "po_number": "PO-1002",
        "amount": 1250.00,
        "date": "2026-10-16",
        "due_date": "2026-11-16",
        "description": "Ergonomic workstations and peripherals",
        "department": "Facilities",
    },
    # 3. Duplicate - matches ALREADY_PAID_INVOICES
    {
        "invoice_number": "INV-9001",
        "vendor": "CloudScale Hosting Ltd",
        "po_number": "PO-1001",
        "amount": 12450.00,
        "date": "2026-09-15",
        "due_date": "2026-10-15",
        "description": "Enterprise cloud compute infrastructure (Duplicate Re-bill)",
        "department": "Engineering",
    },
    # 4. Over-budget / Price discrepancy - PO-1003 is $4,800.00
    {
        "invoice_number": "INV-103",
        "vendor": "DevTools Global",
        "po_number": "PO-1003",
        "amount": 6500.00,
        "date": "2026-10-18",
        "due_date": "2026-11-18",
        "description": "Annual IDE and developer platform licenses",
        "department": "Engineering",
    },
    # 5. Unknown vendor / Missing PO
    {
        "invoice_number": "INV-104",
        "vendor": "Unknown Stealth Vendor LLC",
        "po_number": "PO-9999",
        "amount": 3200.00,
        "date": "2026-10-20",
        "due_date": "2026-11-20",
        "description": "Unverified security consultancy retainer",
        "department": "Security",
    },
    # 6. Clean - matches PO-1004
    {
        "invoice_number": "INV-105",
        "vendor": "Logistics Pro",
        "po_number": "PO-1004",
        "amount": 8900.00,
        "date": "2026-10-22",
        "due_date": "2026-11-22",
        "description": "Regional freight and logistics distribution",
        "department": "Operations",
    },
]


class InvoiceItem(BaseModel):
    invoice_number: str
    vendor: str
    po_number: Optional[str] = None
    amount: float
    date: str
    due_date: str
    description: str
    department: str
    status: str = "pending"  # matched_clean | flagged_anomaly
    flags: List[str] = Field(default_factory=list)
    po_expected_amount: Optional[float] = None


class PaymentBatch(BaseModel):
    batch_id: str
    invoices: List[Dict[str, Any]]
    total_amount: float
    invoice_count: int
    status: str = "pending_approval"


class FinanceAgent:
    """Finance AI Employee handling autonomous accounts payable & invoice auditing."""

    def __init__(self):
        self.erp = mock_erp

    def extract_and_match_invoices(
        self,
        raw_invoices: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Audits invoices against ERP purchase orders, flags duplicates & price anomalies."""
        invoices = raw_invoices if raw_invoices is not None else SAMPLE_INVOICES

        clean_invoices: List[Dict[str, Any]] = []
        flagged_invoices: List[Dict[str, Any]] = []

        duplicate_count = 0
        anomaly_count = 0
        unregistered_vendor_count = 0

        for inv in invoices:
            inv_num = inv.get("invoice_number", "UNKNOWN")
            po_num = inv.get("po_number")
            amount = float(inv.get("amount", 0.0))
            vendor = inv.get("vendor", "Unknown")

            item_data = dict(inv)
            flags: List[str] = []

            # 1. Duplicate check against ERP history
            if self.erp.is_duplicate_invoice(inv_num):
                flags.append("Duplicate invoice: record already paid in prior disbursement cycle")
                duplicate_count += 1

            # 2. Purchase Order Reconciliation
            if not po_num:
                flags.append("Missing Purchase Order reference on vendor invoice")
                unregistered_vendor_count += 1
            else:
                po = self.erp.get_purchase_order(po_num)
                if not po:
                    flags.append(f"Purchase order '{po_num}' does not exist in ERP system")
                    unregistered_vendor_count += 1
                else:
                    item_data["po_expected_amount"] = po.get("expected_amount")
                    expected_amount = po.get("expected_amount", 0.0)
                    tolerance_pct = po.get("tolerance_pct", 5.0)

                    # Price variance check
                    if expected_amount > 0:
                        variance = amount - expected_amount
                        variance_pct = (variance / expected_amount) * 100.0

                        if variance_pct > tolerance_pct:
                            flags.append(
                                f"Price discrepancy: Billed ${amount:,.2f} exceeds PO limit of ${expected_amount:,.2f} "
                                f"by {variance_pct:.1f}% (allowable threshold: {tolerance_pct:.1f}%)"
                            )
                            anomaly_count += 1

            if flags:
                item_data["status"] = "flagged_anomaly"
                item_data["flags"] = flags
                flagged_invoices.append(item_data)
            else:
                item_data["status"] = "matched_clean"
                item_data["flags"] = []
                clean_invoices.append(item_data)

        total_clean_amount = round(sum(i["amount"] for i in clean_invoices), 2)
        total_flagged_amount = round(sum(i["amount"] for i in flagged_invoices), 2)

        batch_id = f"BATCH-{uuid.uuid4().hex[:8].upper()}"
        payment_batch = {
            "batch_id": batch_id,
            "invoices": clean_invoices,
            "total_amount": total_clean_amount,
            "invoice_count": len(clean_invoices),
            "status": "pending_approval",
        }

        summary = (
            f"Audited {len(invoices)} invoices: {len(clean_invoices)} clean and matched against POs "
            f"(${total_clean_amount:,.2f}), {len(flagged_invoices)} flagged with anomalies "
            f"(${total_flagged_amount:,.2f})."
        )

        logger.info(
            "Finance audit completed: %d clean, %d flagged, batch %s ($%.2f)",
            len(clean_invoices),
            len(flagged_invoices),
            batch_id,
            total_clean_amount,
        )

        return {
            "summary": summary,
            "clean_invoices": clean_invoices,
            "flagged_invoices": flagged_invoices,
            "payment_batch": payment_batch,
            "audit_stats": {
                "total_invoices": len(invoices),
                "clean_count": len(clean_invoices),
                "flagged_count": len(flagged_invoices),
                "duplicates": duplicate_count,
                "anomalies": anomaly_count,
                "unregistered_vendors": unregistered_vendor_count,
                "clean_amount": total_clean_amount,
                "flagged_amount": total_flagged_amount,
            },
        }


finance_agent = FinanceAgent()

