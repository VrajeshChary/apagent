"""Control Bridge — stdlib HTTP API for the Invoice Exception Agent.

Serves ui/console.html and wraps the REAL backend:
  ingest -> detect -> recall -> resolve (Groq or rule fallback) -> reflect

Run:  python -m ui.server   (default port 8787, override with PORT env)
"""
from __future__ import annotations

import json
import os
import sys
import threading
import uuid
from datetime import datetime, timezone

# project root on sys.path
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Windows legacy consoles choke on emoji in rich output (cp1252);
# force UTF-8 before any backend module prints.
for _stream in (sys.stdout, sys.stderr):
    if _stream is not None and hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer  # noqa: E402

from config.settings import (  # noqa: E402
    GROQ_API_KEY, GROQ_MODEL,
    AUTO_APPROVE_THRESHOLD, ESCALATION_THRESHOLD, CONFIDENCE_THRESHOLD,
    VENDOR_RISK_TIERS,
)
from data.synthetic.generator import (  # noqa: E402
    SAMPLE_INVOICES, VENDORS, VENDOR_CONTRACTS,
    get_all_documents,
)
from models.schemas import Invoice, InvoiceLineItem  # noqa: E402
from agents.exception_detector import detect_exceptions  # noqa: E402
from agents.resolver import ExceptionResolver  # noqa: E402
from hindsight.client import get_hindsight_client  # noqa: E402
from hindsight.ingest import ingest_all  # noqa: E402
from hindsight.reflect_runner import generate_vendor_profiles  # noqa: E402

ACTIVE_INVOICES = list(SAMPLE_INVOICES)

STATE = {
    "ingested": False,
    "memory_count": 0,
    "session_id": None,
    "exceptions": [],       # enriched exception dicts
    "resolutions": {},      # exception_id -> resolution dict
    "scanned": False,
    "busy": False,
}
STATE_LOCK = threading.Lock()


def iso_now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def enrich_exception(exc, invoice) -> dict:
    contract = next((c for c in VENDOR_CONTRACTS if c["vendor"] == invoice.vendor.name), None)
    return {
        "exception_id": exc.exception_id,
        "invoice_id": exc.invoice_id,
        "vendor_name": exc.vendor_name,
        "vendor_tier": getattr(invoice.vendor, "risk_tier", "unknown"),
        "vendor_category": getattr(invoice.vendor, "category", "General"),
        "vendor_terms": getattr(invoice.vendor, "payment_terms", ""),
        "vendor_notes": getattr(invoice.vendor, "historical_notes", ""),
        "type": exc.exception_type.value,
        "label": exc.exception_type.value.replace("_", " ").upper(),
        "description": exc.description,
        "expected": exc.expected_value,
        "actual": exc.actual_value,
        "variance": exc.variance_amount,
        "variance_pct": exc.variance_pct,
        "invoice_total": invoice.total,
        "subtotal": invoice.subtotal,
        "tax": invoice.tax,
        "shipping": invoice.shipping,
        "invoice_date": str(invoice.invoice_date),
        "due_date": str(invoice.due_date),
        "po_number": invoice.po_number,
        "line_items": [
            {
                "description": li.description,
                "quantity": li.quantity,
                "unit_price": li.unit_price,
                "total": li.total,
                "po_line_ref": li.po_line_ref,
            }
            for li in invoice.line_items
        ],
        "contract": contract,
        "detected_at": iso_now(),
        "resolution": None,
    }


def do_ingest():
    client = ingest_all()
    count = client.count if hasattr(client, "count") else None
    return {"memory_count": count, "backend": type(client).__name__}


def do_scan():
    results = {}
    for inv in ACTIVE_INVOICES:
        for exc in detect_exceptions(inv):
            results[exc.exception_id] = enrich_exception(exc, inv)
    return list(results.values())


def do_resolve_one(exc_dict: dict):
    """Run the real resolver for one exception and attach the result."""
    target = next(
        (i for i in ACTIVE_INVOICES if i.invoice_id == exc_dict["invoice_id"]),
        None,
    )
    if target is None:
        target = next(
            (i for i in SAMPLE_INVOICES if i.invoice_id == exc_dict["invoice_id"]),
            None,
        )
    if target is None:
        return None
    exceptions = detect_exceptions(target)
    match = next(
        (e for e in exceptions
         if e.exception_type.value == exc_dict["type"]
         and abs(e.variance_amount - exc_dict["variance"]) < 0.01),
        None,
    )
    if match is None:
        return None

    resolver = ExceptionResolver()
    resolution = resolver.resolve(match, invoice=target)

    # Real recall for the memory feed
    recalled = resolver.recall_context(match, n_results=5)

    return {
        "action": resolution.action.value,
        "confidence": resolution.confidence,
        "reasoning": resolution.reasoning,
        "similar_cases_found": resolution.similar_cases_found,
        "approved_by": resolution.approved_by,
        "resolved_at": iso_now(),
        "engine": "groq" if GROQ_API_KEY else "rules",
        "recall": [
            {"id": d["id"], "score": round(float(d.get("score", 0)), 3),
             "type": d.get("metadata", {}).get("type", "unknown"),
             "vendor": d.get("metadata", {}).get("vendor", ""),
             "text": d["text"][:350]}
            for d in recalled
        ],
    }


def do_probe(query: str, n_results: int = 6):
    resolver = ExceptionResolver()
    recalled = resolver._hindsight.recall(query, n_results=n_results)
    return [
        {
            "id": d["id"],
            "score": round(float(d.get("score", 0)), 3),
            "type": d.get("metadata", {}).get("type", "unknown"),
            "vendor": d.get("metadata", {}).get("vendor", ""),
            "text": d["text"]
        }
        for d in recalled
    ]


def do_inject(preset_id: str):
    from datetime import date
    today = date.today()
    if preset_id == "DELL_AIR_FREIGHT":
        dell = next(v for v in VENDORS if v.name == "Dell Technologies")
        inv = Invoice(
            invoice_id=f"INV-D-EXP-{uuid.uuid4().hex[:4].upper()}",
            vendor=dell,
            invoice_date=today,
            due_date=today,
            po_number="PO-2025-RUSH-01",
            subtotal=8400.00,
            tax=714.00,
            shipping=1420.00,  # $1,420 freight vs $500 threshold
            total=10534.00,
            line_items=[InvoiceLineItem("PowerEdge R760 Server Rack", 2, 4200.00, 8400.00, "PO-R1")],
        )
    elif preset_id == "STAPLES_SURPRISE":
        staples = next(v for v in VENDORS if v.name == "Staples Inc.")
        inv = Invoice(
            invoice_id=f"INV-STP-{uuid.uuid4().hex[:4].upper()}",
            vendor=staples,
            invoice_date=today,
            due_date=today,
            po_number="PO-2025-OFF-88",
            subtotal=1850.00,
            tax=148.00,
            shipping=85.00,  # Contract says free shipping over $50
            total=2083.00,
            line_items=[InvoiceLineItem("Executive Ergonomic Mesh Chairs", 5, 370.00, 1850.00, "PO-OFF-1")],
        )
    elif preset_id == "ACME_UNAUTHORIZED":
        acme = next(v for v in VENDORS if v.name == "Acme Consulting")
        inv = Invoice(
            invoice_id=f"INV-ACM-{uuid.uuid4().hex[:4].upper()}",
            vendor=acme,
            invoice_date=today,
            due_date=today,
            po_number="PO-2025-RET-11",
            subtotal=21400.00,
            tax=0.00,
            shipping=0.00,
            total=21400.00,
            line_items=[
                InvoiceLineItem("Monthly retainer", 1, 15000.00, 15000.00, "RET-BASE"),
                InvoiceLineItem("Additional unauthorized weekend hours", 32, 200.00, 6400.00, "RET-EXTRA"),
            ],
        )
    elif preset_id == "PINNACLE_DRONE":
        pinnacle = next(v for v in VENDORS if v.name == "Pinnacle Security")
        inv = Invoice(
            invoice_id=f"INV-PIN-{uuid.uuid4().hex[:4].upper()}",
            vendor=pinnacle,
            invoice_date=today,
            due_date=today,
            po_number="PO-2025-SEC-09",
            subtotal=14500.00,
            tax=1232.50,
            shipping=0.00,
            total=15732.50,
            line_items=[
                InvoiceLineItem("Monthly perimeter security", 1, 10000.00, 10000.00, "SEC-BASE"),
                InvoiceLineItem("Autonomous night drone patrol (unauthorized)", 1, 4500.00, 4500.00, "SEC-ROBOT"),
            ],
        )
    else:
        return None

    ACTIVE_INVOICES.append(inv)
    new_excs = [enrich_exception(e, inv) for e in detect_exceptions(inv)]
    with STATE_LOCK:
        existing_ids = {e["exception_id"] for e in STATE["exceptions"]}
        for ne in new_excs:
            if ne["exception_id"] not in existing_ids:
                STATE["exceptions"].append(ne)
    return {"invoice_id": inv.invoice_id, "exceptions": new_excs, "total_active": len(ACTIVE_INVOICES)}


def do_reflect():
    generate_vendor_profiles()
    from data.synthetic.generator import VENDORS as V
    profiles = []
    for v in V:
        profiles.append({
            "vendor_id": v.vendor_id, "name": v.name,
            "tier": v.risk_tier, "category": v.category,
            "payment_terms": v.payment_terms,
            "notes": v.historical_notes,
        })
    return {"profiles": profiles}


def snapshot() -> dict:
    with STATE_LOCK:
        return {
            "session_id": STATE["session_id"],
            "ingested": STATE["ingested"],
            "scanned": STATE["scanned"],
            "memory_count": STATE["memory_count"],
            "exceptions": STATE["exceptions"],
            "resolutions": STATE["resolutions"],
            "busy": STATE["busy"],
            "active_invoices_count": len(ACTIVE_INVOICES),
        }


def settings_snapshot() -> dict:
    docs = get_all_documents()
    return {
        "groq": bool(GROQ_API_KEY),
        "model": GROQ_MODEL,
        "auto_approve_threshold": AUTO_APPROVE_THRESHOLD,
        "escalation_threshold": ESCALATION_THRESHOLD,
        "confidence_threshold": CONFIDENCE_THRESHOLD,
        "risk_tiers": VENDOR_RISK_TIERS,
        "vendors": [
            {"id": v.vendor_id, "name": v.name, "tier": v.risk_tier,
             "category": v.category, "terms": v.payment_terms,
             "email": v.contact_email, "notes": v.historical_notes}
            for v in VENDORS
        ],
        "contracts": VENDOR_CONTRACTS,
        "catalog_docs": len(docs),
        "raw_docs": [
            {
                "id": d["id"],
                "type": d["metadata"].get("type", "unknown"),
                "vendor": d["metadata"].get("vendor", ""),
                "preview": d["text"][:220]
            }
            for d in docs
        ]
    }


def set_state(**kw):
    with STATE_LOCK:
        STATE.update(kw)


class Handler(BaseHTTPRequestHandler):
    server_version = "ControlBridge/2.0"

    # ── helpers ──────────────────────────────────────────────
    def _read_json(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            if length > 0:
                raw = self.rfile.read(length).decode("utf-8")
                return json.loads(raw)
        except Exception:
            pass
        return {}

    def _json(self, payload, status=200):
        body = json.dumps(payload, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def _file(self, path, ctype):
        try:
            with open(path, "rb") as f:
                body = f.read()
            self.send_response(200)
            self.send_header("Content-Type", f"{ctype}; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except FileNotFoundError:
            self._json({"error": f"missing asset {path}"}, 404)

    def log_message(self, fmt, *args):
        sys.stderr.write("[bridge] %s - %s\n" % (self.address_string(), fmt % args))

    # ── routing ──────────────────────────────────────────────
    def do_GET(self):
        path = self.path.split("?")[0].rstrip("/") or "/"
        if path == "/" or path == "/console":
            self._file(os.path.join(ROOT, "ui", "console.html"), "text/html")
        elif path == "/state":
            self._json(snapshot())
        elif path == "/settings":
            self._json(settings_snapshot())
        elif path == "/health":
            self._json({"ok": True, "time": iso_now()})
        else:
            self._json({"error": "unknown route", "path": path}, 404)

    def do_POST(self):
        path = self.path.split("?")[0].rstrip("/")
        if path == "/ingest":
            self._act_ingest()
        elif path == "/scan":
            self._act_scan()
        elif path == "/resolve_all":
            self._act_resolve_all()
        elif path == "/resolve_one":
            self._act_resolve_one()
        elif path == "/override":
            self._act_override()
        elif path == "/probe":
            self._act_probe()
        elif path == "/inject":
            self._act_inject()
        elif path == "/reflect":
            self._act_reflect()
        elif path == "/reset":
            self._act_reset()
        else:
            self._json({"error": "unknown route", "path": path}, 404)

    # ── actions ──────────────────────────────────────────────
    def _act_ingest(self):
        if STATE["busy"]:
            self._json({"error": "busy"}, 409)
            return
        set_state(busy=True, session_id=uuid.uuid4().hex[:8].upper())
        try:
            r = do_ingest()
            set_state(busy=False, ingested=True, memory_count=r["memory_count"])
            self._json({"ok": True, **r, "session_id": STATE["session_id"]})
        except Exception as e:
            import traceback
            traceback.print_exc()
            set_state(busy=False)
            self._json({"ok": False, "error": str(e), "trace": traceback.format_exc()}, 500)

    def _act_scan(self):
        if STATE["busy"]:
            self._json({"error": "busy"}, 409)
            return
        set_state(busy=True)
        try:
            excs = do_scan()
            set_state(busy=False, exceptions=excs, scanned=True)
            self._json({"ok": True, "exceptions": excs})
        except Exception as e:
            import traceback
            traceback.print_exc()
            set_state(busy=False)
            self._json({"ok": False, "error": str(e), "trace": traceback.format_exc()}, 500)

    def _act_resolve_all(self):
        if STATE["busy"]:
            self._json({"error": "busy"}, 409)
            return
        if not STATE["ingested"]:
            self._json({"ok": False, "error": "ingest first"}, 409)
            return
        set_state(busy=True)
        try:
            for exc in STATE["exceptions"]:
                if exc["resolution"]:
                    continue
                res = do_resolve_one(exc)
                if res is None:
                    continue
                exc["resolution"] = res
                with STATE_LOCK:
                    STATE["resolutions"][exc["exception_id"]] = res
            set_state(busy=False)
            self._json({"ok": True, "state": snapshot()})
        except Exception as e:
            import traceback
            traceback.print_exc()
            set_state(busy=False)
            self._json({"ok": False, "error": str(e), "trace": traceback.format_exc()}, 500)

    def _act_resolve_one(self):
        if STATE["busy"]:
            self._json({"error": "busy"}, 409)
            return
        data = self._read_json()
        exc_id = data.get("exception_id")
        target = next((e for e in STATE["exceptions"] if e["exception_id"] == exc_id), None)
        if not target:
            self._json({"ok": False, "error": f"exception {exc_id} not found"}, 404)
            return
        set_state(busy=True)
        try:
            res = do_resolve_one(target)
            if res:
                target["resolution"] = res
                with STATE_LOCK:
                    STATE["resolutions"][target["exception_id"]] = res
            set_state(busy=False)
            self._json({"ok": True, "resolution": res, "exception": target})
        except Exception as e:
            import traceback
            traceback.print_exc()
            set_state(busy=False)
            self._json({"ok": False, "error": str(e)}, 500)

    def _act_override(self):
        data = self._read_json()
        exc_id = data.get("exception_id")
        action = data.get("action")
        approver = data.get("approver", "Human Controller")
        notes = data.get("reasoning", "")
        with STATE_LOCK:
            target = next((e for e in STATE["exceptions"] if e["exception_id"] == exc_id), None)
            if not target:
                self._json({"ok": False, "error": f"exception {exc_id} not found"}, 404)
                return
            res = {
                "action": action,
                "confidence": 1.0,
                "reasoning": notes or f"Manual override signed by {approver}.",
                "similar_cases_found": target["resolution"]["similar_cases_found"] if target.get("resolution") else 0,
                "approved_by": f"{approver} (Human Override)",
                "resolved_at": iso_now(),
                "engine": "human_override",
                "recall": target["resolution"]["recall"] if target.get("resolution") else [],
            }
            target["resolution"] = res
            STATE["resolutions"][exc_id] = res
        self._json({"ok": True, "resolution": res, "exception": target})

    def _act_probe(self):
        data = self._read_json()
        query = data.get("query", "").strip()
        if not query:
            self._json({"ok": False, "error": "query required"}, 400)
            return
        try:
            hits = do_probe(query, n_results=int(data.get("n_results", 6)))
            self._json({"ok": True, "query": query, "hits": hits})
        except Exception as e:
            self._json({"ok": False, "error": str(e)}, 500)

    def _act_inject(self):
        data = self._read_json()
        preset = data.get("preset")
        res = do_inject(preset)
        if not res:
            self._json({"ok": False, "error": "unknown preset"}, 400)
            return
        self._json({"ok": True, **res, "state": snapshot()})

    def _act_reflect(self):
        if STATE["busy"]:
            self._json({"error": "busy"}, 409)
            return
        set_state(busy=True)
        try:
            r = do_reflect()
            set_state(busy=False)
            self._json({"ok": True, **r})
        except Exception as e:
            import traceback
            traceback.print_exc()
            set_state(busy=False)
            self._json({"ok": False, "error": str(e), "trace": traceback.format_exc()}, 500)

    def _act_reset(self):
        global ACTIVE_INVOICES
        ACTIVE_INVOICES = list(SAMPLE_INVOICES)
        set_state(session_id=None, ingested=False, scanned=False,
                  memory_count=0, exceptions=[], resolutions={})
        self._json({"ok": True})


def main():
    port = int(os.environ.get("PORT", "8787"))
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"[bridge] Control Bridge online -> http://127.0.0.1:{port}")
    print(f"[bridge] engine: {'groq:' + GROQ_MODEL if GROQ_API_KEY else 'rules (no GROQ_API_KEY)'}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[bridge] shutting down")
        server.shutdown()


if __name__ == "__main__":
    main()

