"""AWS Bedrock AgentCore Supervisor Orchestrator.

Routes user messages to the appropriate specialist sub-agent based on intent.
Uses Claude Sonnet 3.5 via Bedrock as the reasoning model.
"""
import json
from typing import Any

from app.config import settings
from app.core.bedrock import invoke_claude

ORCHESTRATOR_SYSTEM = """You are "Sahi Signal", a property buying assistant for Dublin, Ireland.
The buyer is mortgage-approved (AIP) with €325k budget (stretch €375k), chain-free.
Focus areas: D12 (Crumlin, Walkinstown, Perrystown) and D6W (Kimmage) borders.

CRITICAL flags always surface:
- Electric storage heating = strongly penalise
- Celtic Tiger era (2000-2008) apartments = flag fire safety risk
- Missing floor area = flag as critical viewing priority
- Management fees > €2,000/yr = flag high

Route requests to the right specialist:
- Property search/comparison → search_agent
- Pre-viewing prep/checklist → viewing_agent
- Bidding strategy/price model → bidding_agent
- Solicitors/surveyors → professionals_agent
- Financing/scenarios → financing_agent

Always be direct, practical and data-grounded. The buyer is analytical and wants numbers."""

ROUTE_SYSTEM = """Classify the user's request into one of these categories:
search | viewing | bidding | pricing | professionals | financing | general

Respond with ONLY the category name, nothing else."""


def route_message(message: str, property_id: str | None = None) -> str:
    """Determine which sub-agent should handle this message."""
    context = f"Property context: {property_id}" if property_id else ""
    prompt = f"{context}\n\nUser message: {message}"
    category = invoke_claude(prompt, system=ROUTE_SYSTEM, max_tokens=10, temperature=0.0).strip().lower()
    valid = {"search", "viewing", "bidding", "pricing", "professionals", "financing", "general"}
    return category if category in valid else "general"


def chat(message: str, session_context: dict[str, Any]) -> str:
    """Main orchestrator entry point — dispatches to sub-agent or handles directly."""
    property_id = session_context.get("property_id")
    route = route_message(message, property_id)

    context_str = ""
    if property_id:
        context_str = f"\n[Active property ID: {property_id}]"
    if session_context.get("active_bid_session"):
        context_str += f"\n[Active bid session: {session_context['active_bid_session']}]"

    prompt = f"{context_str}\n\nUser: {message}\n\nAssist as Sahi Signal ({route} context):"
    return invoke_claude(prompt, system=ORCHESTRATOR_SYSTEM, max_tokens=1024)


def stream_chat(message: str, session_context: dict[str, Any]):
    """Streaming version — yields SSE-compatible chunks."""
    from app.core.bedrock import invoke_claude_streaming

    property_id = session_context.get("property_id")
    context_str = f"\n[Property: {property_id}]" if property_id else ""
    prompt = f"{context_str}\n\nUser: {message}\n\nRespond as Sahi Signal:"

    response = invoke_claude_streaming(prompt, system=ORCHESTRATOR_SYSTEM)
    stream = response.get("body")
    if not stream:
        return

    for event in stream:
        chunk = event.get("chunk")
        if chunk:
            try:
                data = json.loads(chunk["bytes"].decode())
                if data.get("type") == "content_block_delta":
                    text = data.get("delta", {}).get("text", "")
                    if text:
                        yield text
            except Exception:
                continue
