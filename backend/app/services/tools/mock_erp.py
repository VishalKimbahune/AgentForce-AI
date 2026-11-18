"""Mock ERP and payment adapter providing purchase orders, vendor records, operational metrics, and payment gateway."""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("tools.mock_erp")

# -------------------------------------------------------------
# SEEDED MOCK ERP DATA
# -------------------------------------------------------------

MOCK_PURCHASE_ORDERS = {
    "PO-1001": {
        "po_number": "PO-1001",
        "vendor": "CloudScale Hosting Ltd",
        "description": "Enterprise cloud compute infrastructure",
        "expected_amount": 12450.00,
        "tolerance_pct": 5.0,
        "department": "Engineering",
        "status": "open",
    },
    "PO-1002": {
        "po_number": "PO-1002",
        "vendor": "OfficeMax Corporate",
        "description": "Ergonomic workstations and peripherals",
        "expected_amount": 1250.00,
        "tolerance_pct": 5.0,
        "department": "Facilities",
        "status": "open",
    },
    "PO-1003": {
        "po_number": "PO-1003",
        "vendor": "DevTools Global",
        "description": "Annual IDE and developer platform licenses",
        "expected_amount": 4800.00,
        "tolerance_pct": 5.0,
        "department": "Engineering",
        "status": "open",
    },
    "PO-1004": {
        "po_number": "PO-1004",
        "vendor": "Logistics Pro",
        "description": "Regional freight and logistics distribution",
        "expected_amount": 8900.00,
        "tolerance_pct": 5.0,
        "department": "Operations",
        "status": "open",
    },
}

ALREADY_PAID_INVOICES = {"INV-9001", "INV-8999"}

MOCK_OPERATIONS_METRICS = {
    "period": "October 2026",
    "gross_revenue": 428500.00,
    "total_expenses": 212300.00,
    "net_income": 216200.00,
    "operating_margin_pct": 50.45,
    "workforce_hours_saved": 1420,
    "automated_tasks_count": 8950,
    "sla_uptime_pct": 99.94,
    "active_ai_employees": 3,
    "department_breakdown": {
        "Engineering": {"budget": 120000, "spent": 114500, "projects_on_track": 14},
        "HR & Recruiting": {"budget": 45000, "spent": 38200, "candidates_screened": 182},
        "Finance & Operations": {"budget": 65000, "spent": 59600, "invoices_processed": 420},
    },
}

MOCK_PAYMENT_TRANSACTIONS: List[Dict[str, Any]] = []


class MockERPService:
    """Mock Enterprise Resource Planning (ERP) database and service adapter."""

    def get_purchase_order(self, po_number: str) -> Optional[Dict[str, Any]]:
        return MOCK_PURCHASE_ORDERS.get(po_number.upper().strip())

    def is_duplicate_invoice(self, invoice_number: str) -> bool:
        return invoice_number.upper().strip() in ALREADY_PAID_INVOICES

    def get_operations_metrics(self, period: Optional[str] = None) -> Dict[str, Any]:
        return MOCK_OPERATIONS_METRICS

    def execute_payment_batch(
        self,
        batch_id: str,
        invoices: List[Dict[str, Any]],
        total_amount: float,
    ) -> Dict[str, Any]:
        """Simulates payment gateway batch transfer."""
        tx_id = f"TX-{uuid.uuid4().hex[:10].upper()}"
        record = {
            "transaction_id": tx_id,
            "batch_id": batch_id,
            "total_amount": total_amount,
            "invoice_count": len(invoices),
            "status": "completed",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "invoices": [inv.get("invoice_number") for inv in invoices],
        }
        MOCK_PAYMENT_TRANSACTIONS.append(record)
        # Mark these invoices as paid to prevent duplicate payment
        for inv in invoices:
            ALREADY_PAID_INVOICES.add(inv.get("invoice_number", "").upper())

        logger.info("Payment batch %s executed successfully. TX ID: %s, Amount: $%.2f", batch_id, tx_id, total_amount)
        return record


mock_erp = MockERPService()

