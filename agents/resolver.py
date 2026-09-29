from __future__ import annotations
import json
import sys
import os
import textwrap

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from groq import Groq

from config.settings import (
    GROQ_API_KEY,
    GROQ_MODEL,
    AUTO_APPROVE_THRESHOLD,
    ESCALATION_THRESHOLD,
    CONFIDENCE_THRESHOLD,
    VENDOR_RISK_TIERS,
)
from models.schemas import (
    Exception_,
    Resolution,
    ResolutionAction,
    Invoice,
)
from hindsight.client import get_hindsight_client, HindsightBase
from agents.exception_detector import detect_exceptions, scan_all_invoices
from data.synthetic.generator import SAMPLE_INVOICES, VENDORS

SYSTEM_PROMPT = textwrap.dedent("""\
You are an Accounts Payable Exception Resolution Agent.
Your job is to analyze invoice exceptions and recommend a resolution action based on historical context.

You MUST respond with valid JSON exactly like this:
{
    "action": "auto_approved" | "approved_with_adjustment" | "escalated_to_human" | "rejected",
    "confidence": 0.85,
    "reasoning": "Explanation here..."
}
""")

class ExceptionResolver:
    def __init__(self, hindsight: HindsightBase | None = None):
        self._hindsight = hindsight or get_hindsight_client()
        self._groq = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None
        self._model = GROQ_MODEL

    def _build_recall_query(self, exc: Exception_) -> str:
        parts = [exc.vendor_name, exc.exception_type.value.replace("_", " ")]
        if exc.variance_amount:
            parts.append(f"${exc.variance_amount:.0f} variance")
        parts.append(exc.description[:120])
        return " ".join(parts)

    def recall_context(self, exc: Exception_, n_results: int = 8) -> list[dict]:
        query = self._build_recall_query(exc)
        return self._hindsight.recall(query, n_results=n_results)

    def _format_context_for_llm(self, exc: Exception_, invoice: Invoice | None, recalled_docs: list[dict]) -> str:
        lines = [
            "EXCEPTION DETAILS",
            f"Vendor: {exc.vendor_name}",
            f"Type: {exc.exception_type.value}",
            f"Description: {exc.description}",
            f"Variance: ${exc.variance_amount:,.2f}"
        ]

        lines.append("\nHISTORICAL CONTEXT:")
        for i, doc in enumerate(recalled_docs, 1):
            lines.append(f"\n--- Record {i} ---")
            lines.append(doc["text"])

        return "\n".join(lines)

    def _fallback_resolution(self, prompt: str) -> dict:
        prompt_lower = prompt.lower()

        # Simple rule-based fallback
        approved_count = prompt_lower.count("decision: approved")

        if "high risk" in prompt_lower:
            return {"action": "escalated_to_human", "confidence": 0.9, "reasoning": "High-risk vendor."}

        if approved_count >= 2:
            return {"action": "auto_approved", "confidence": 0.8, "reasoning": f"Found {approved_count} historical approvals."}

        return {"action": "escalated_to_human", "confidence": 0.5, "reasoning": "Insufficient historical precedent via fallback."}

    def _call_groq(self, user_prompt: str) -> dict:
        if not self._groq:
            return self._fallback_resolution(user_prompt)

        try:
            response = self._groq.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,
                max_tokens=1024,
                response_format={"type": "json_object"},
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            print(f"  [WARNING] Groq API error: {e}")
            return self._fallback_resolution(user_prompt)

    def resolve(self, exc: Exception_, invoice: Invoice | None = None) -> Resolution:
        recalled_docs = self.recall_context(exc)
        prompt = self._format_context_for_llm(exc, invoice, recalled_docs)
        llm_result = self._call_groq(prompt)

        action_map = {
            "auto_approved": ResolutionAction.AUTO_APPROVED,
            "approved_with_adjustment": ResolutionAction.APPROVED_WITH_ADJUSTMENT,
            "escalated_to_human": ResolutionAction.ESCALATED_TO_HUMAN,
            "rejected": ResolutionAction.REJECTED,
        }

        action_str = llm_result.get("action", "escalated_to_human")
        action = action_map.get(action_str, ResolutionAction.ESCALATED_TO_HUMAN)
        confidence = float(llm_result.get("confidence", 0.0))

        if confidence < CONFIDENCE_THRESHOLD and action != ResolutionAction.ESCALATED_TO_HUMAN:
            action = ResolutionAction.ESCALATED_TO_HUMAN
            llm_result["reasoning"] += " [OVERRIDE: Low confidence]"

        return Resolution(
            exception_id=exc.exception_id,
            action=action,
            confidence=confidence,
            reasoning=llm_result.get("reasoning", ""),
            similar_cases_found=len(recalled_docs),
            similar_cases_summary=f"{len(recalled_docs)} cases recalled",
            approved_by="agent"
        )

    def resolve_all(self, invoices: list[Invoice] | None = None) -> list[tuple[Exception_, Resolution]]:
        results = []
        target = invoices or SAMPLE_INVOICES
        for inv in target:
            exceptions = detect_exceptions(inv)
            for exc in exceptions:
                resolution = self.resolve(exc, invoice=inv)
                results.append((exc, resolution))
        return results

def main():
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich import print as rprint

    console = Console()
    console.print(Panel.fit(
        "[bold cyan]🤖 Groq Agent Loop — Exception Resolution[/bold cyan]\n"
        "Resolving exceptions with recalled historical context",
        border_style="cyan",
    ))

    resolver = ExceptionResolver()

    if not GROQ_API_KEY:
        console.print("  [yellow]⚠️  No GROQ_API_KEY found. Using rule-based fallback mode.[/yellow]\n")
    else:
        console.print(f"  ✅ Using Groq model: [green]{GROQ_MODEL}[/green]\n")

    results = resolver.resolve_all()

    for exc, resolution in results:
        console.print(f"\n[bold]Exception {exc.exception_id}[/bold] — {exc.vendor_name}")
        console.print(f"  Type: {exc.exception_type.value}")
        console.print(f"  Variance: ${exc.variance_amount:,.2f}")
        console.print(f"  Description: {exc.description[:80]}...")

        action_colors = {
            ResolutionAction.AUTO_APPROVED: "green",
            ResolutionAction.APPROVED_WITH_ADJUSTMENT: "yellow",
            ResolutionAction.ESCALATED_TO_HUMAN: "red",
            ResolutionAction.REJECTED: "red",
        }
        color = action_colors.get(resolution.action, "white")

        console.print(f"  [bold {color}]→ {resolution.action.value.upper()}[/bold {color}] (confidence: {resolution.confidence:.2f})")
        console.print(f"  Reasoning: {resolution.reasoning}")
        console.print(f"  Similar cases recalled: {resolution.similar_cases_found}")

    console.print(Panel.fit(
        f"[bold green]✅ Resolved {len(results)} exceptions[/bold green]",
        border_style="green",
    ))

if __name__ == "__main__":
    main()
