from __future__ import annotations
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

from hindsight.client import get_hindsight_client
from data.synthetic.generator import VENDORS


def generate_vendor_profiles():
    console = Console()
    console.print("[bold cyan]Step 4: Hindsight reflect()[/bold cyan] - Building Vendor Profiles")

    client = get_hindsight_client()

    for vendor in VENDORS[:3]:  # Test first 3 vendors
        topic = f"Historical payment disputes, exceptions, and approval patterns for {vendor.name}"
        console.print(f"\n[bold green]Reflecting on:[/bold green] {topic}")

        # reflect() synthesizes all past observations into a summary
        model = client.reflect(topic, n_source_docs=10)

        console.print(Panel(
            model,
            title=f"Mental Model: {vendor.name}",
            border_style="cyan"
        ))


if __name__ == "__main__":
    generate_vendor_profiles()
