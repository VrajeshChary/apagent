"""In-process selftest for the Control Bridge.

Boots the HTTP server on a free port inside this process, exercises every
endpoint and the full pipeline (ingest -> scan -> resolve -> reflect),
then shuts down cleanly. Deterministic, no daemon required.

Run:  python -m ui.selftest
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from ui.server import Handler  # noqa: E402
from http.server import ThreadingHTTPServer  # noqa: E402

PORT = 8799
BASE = f"http://127.0.0.1:{PORT}"


def call(method: str, path: str, timeout: float = 120.0):
    req = urllib.request.Request(BASE + path, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(body)
        except json.JSONDecodeError:
            return e.code, {"raw": body}


def main() -> int:
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"[selftest] server up on {BASE}")

    failures = []

    def check(name, cond, extra=""):
        mark = "PASS" if cond else "FAIL"
        print(f"  [{mark}] {name} {extra}")
        if not cond:
            failures.append(name)

    # ── static page ───────────────────────────────────────
    t0 = time.time()
    req = urllib.request.Request(BASE + "/")
    with urllib.request.urlopen(req, timeout=30) as r:
        html = r.read().decode("utf-8")
    check("GET / serves console", "LEDGERWERK" in html, f"({len(html)} bytes, {time.time()-t0:.1f}s)")

    # ── health & settings ─────────────────────────────────
    st, health = call("GET", "/health")
    check("GET /health", st == 200 and health.get("ok") is True)

    st, settings = call("GET", "/settings")
    check("GET /settings", st == 200 and settings.get("vendors") and settings.get("contracts"))
    print(f"    engine={'groq' if settings['groq'] else 'rules'} model={settings['model']} "
          f"vendors={len(settings['vendors'])} docs={settings['catalog_docs']}")

    # ── pipeline ──────────────────────────────────────────
    t0 = time.time()
    st, ing = call("POST", "/ingest")
    check("POST /ingest", st == 200 and ing.get("ok"), f"({time.time()-t0:.1f}s)")
    print(f"    backend={ing.get('backend')} memory_count={ing.get('memory_count')}")

    t0 = time.time()
    st, scan = call("POST", "/scan")
    check("POST /scan", st == 200 and scan.get("ok"), f"({time.time()-t0:.1f}s)")
    excs = scan.get("exceptions", [])
    print(f"    {len(excs)} exceptions detected")
    for e in excs:
        print(f"      {e['exception_id']} {e['invoice_id']} {e['label']} ${e['variance']:.2f} ({e['vendor_name']})")
    check("scan found exceptions", len(excs) >= 3)

    t0 = time.time()
    st, res = call("POST", "/resolve_all")
    check("POST /resolve_all", st == 200 and res.get("ok"), f"({time.time()-t0:.1f}s)")
    resolved = res.get("state", {}).get("exceptions", [])
    n_res = sum(1 for e in resolved if e.get("resolution"))
    check("all exceptions resolved", n_res == len(resolved) and n_res > 0, f"({n_res}/{len(resolved)})")
    for e in resolved:
        r = e.get("resolution") or {}
        print(f"      {e['exception_id']} -> {r.get('action')} @ {r.get('confidence'):.2f} "
              f"engine={r.get('engine')} recall={len((r.get('recall') or []))}")
        rec = r.get("recall") or []
        if rec:
            top = rec[0]
            print(f"        top recall: {top['id']} Δ{top['score']} {top['type']}")

    t0 = time.time()
    st, ref = call("POST", "/reflect")
    check("POST /reflect", st == 200 and ref.get("ok"), f"({time.time()-t0:.1f}s)")
    print(f"    profiles={len(ref.get('profiles', []))}")

    # ── state + reset + guard rails ───────────────────────
    st, state = call("GET", "/state")
    check("GET /state", st == 200 and state.get("ingested") and state.get("memory_count", 0) > 0)

    st, r404 = call("GET", "/nope")
    check("404 on unknown route", st == 404)

    st, rreset = call("POST", "/reset")
    check("POST /reset", st == 200 and rreset.get("ok"))

    st, state2 = call("GET", "/state")
    check("reset clears state", state2.get("memory_count") == 0 and not state2.get("exceptions"))

    server.shutdown()
    print(f"\n[selftest] {'ALL PASS' if not failures else 'FAILURES: ' + ', '.join(failures)}")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
