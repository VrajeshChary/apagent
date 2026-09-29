"""
Step 1: Data Ingestion via Hindsight retain()
=============================================
Loads all synthetic data and stores it in Hindsight memory.

Run this FIRST before anything else:
    python -m hindsight.ingest

This script:
  1. Generates all synthetic documents (vendors, contracts, emails, approvals)
  2. Calls retain() to store them in Hindsight
  3. Verifies storage by running a test recall()
"""
from __future__ import annotations

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import print as rprint

from data.synthetic.generator import (
    get_all_documents,
    vendors_to_documents,
    contracts_to_documents,
    negotiations_to_documents,
    approvals_to_documents,
    VENDORS,
    VENDOR_CONTRACTS,
    NEGOTIATION_EMAILS,
    APPROVAL_RECORDS,
)
from hindsight.client import get_hindsight_client

console = Console()


def ingest_all():
    """Ingest all synthetic data into Hindsight via retain()."""

    console.print(Panel.fit(
        "[bold cyan]📥 Hindsight Data Ingestion[/bold cyan]\n"
        "Loading synthetic data into memory via retain()",
        border_style="cyan",
    ))

    client = get_hindsight_client()
    console.print(f"  Backend: [green]{type(client).__name__}[/green]\n")

    # ── Vendor Profiles ────────────────────────────────────────────
    docs = vendors_to_documents()
    result = client.retain(docs)
    console.print(f"  ✅ Vendor Profiles:       {result['stored']:>3} documents retained")

    # ── Vendor Contracts ───────────────────────────────────────────
    docs = contracts_to_documents()
    result = client.retain(docs)
    console.print(f"  ✅ Vendor Contracts:      {result['stored']:>3} documents retained")

    # ── Negotiation Emails ─────────────────────────────────────────
    docs = negotiations_to_documents()
    result = client.retain(docs)
    console.print(f"  ✅ Negotiation Emails:    {result['stored']:>3} documents retained")

    # ── Approval Records ──────────────────────────────────────────
    docs = approvals_to_documents()
    result = client.retain(docs)
    console.print(f"  ✅ Approval Records:      {result['stored']:>3} documents retained")

    # ── Summary ────────────────────────────────────────────────────
    total = get_all_documents()
    console.print(f"\n  📊 [bold]Total documents in memory: {len(total)}[/bold]")

    if hasattr(client, "count"):
        console.print(f"  📊 [bold]ChromaDB collection count: {client.count}[/bold]")

    return client


def verify_recall(client):
    """Run test queries to verify data was stored correctly."""

    console.print(Panel.fit(
        "[bold yellow]🔍 Verification — Test recall() Queries[/bold yellow]",
        border_style="yellow",
    ))

    test_queries = [
        ("Dell shipping variance ", "Should find Dell shipping approvals & contract terms"),
        ("Acme Consulting hours over retainer", "Should find Acme negotiation & approval records"),
        ("Pinnacle Security unauthorized charge", "Should find Pinnacle dispute records"),
        ("tax discrepancy exemption", "Should find CloudScale AWS tax records"),
        ("Staples quantity mismatch", "Should find Staples short-ship records"),
    ]

    for query, expected in test_queries:
        console.print(f"\n  🔎 Query: [italic]\"{query}\"[/italic]")
        console.print(f"     Expected: {expected}")

        results = client.recall(query, n_results=3)

        table = Table(show_header=True, header_style="bold magenta", padding=(0, 1))
        table.add_column("Rank", style="dim", width=4)
        table.add_column("ID", width=10)
        table.add_column("Type", width=20)
        table.add_column("Vendor", width=22)
        table.add_column("Score", width=6)
        table.add_column("Snippet", width=50)

        for i, doc in enumerate(results, 1):
            snippet = doc["text"][:80].replace("\n", " ")
            table.add_row(
                str(i),
                doc["id"],
                doc["metadata"].get("type", "—"),
                doc["metadata"].get("vendor", "—"),
                f"{doc['score']:.2f}",
                snippet + "…",
            )

        console.print(table)


def main():
    console.print("\n" + "=" * 70)
    console.print("[bold white on blue] INVOICE EXCEPTION AGENT — DATA INGESTION [/bold white on blue]")
    console.print("=" * 70 + "\n")

    client = ingest_all()
    verify_recall(client)

    console.print(Panel.fit(
        "[bold green]✅ Data ingestion complete![/bold green]\n\n"
        "All synthetic data has been stored in Hindsight.\n"
        "You can now run:\n"
        "  • [cyan]python -m agents.exception_detector[/cyan]  — detect exceptions\n"
        "  • [cyan]python -m agents.resolver[/cyan]             — resolve with Groq\n"
        "  • [cyan]python -m hindsight.reflect_runner[/cyan]    — build vendor profiles",
        border_style="green",
    ))


if __name__ == "__main__":
    main()
