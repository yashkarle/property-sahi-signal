from app.core.bedrock import invoke_claude
from app.models.property import Property
from app.schemas.viewing import AgentQuestion, ChecklistItem, MissingDataFlag

SYSTEM_PROMPT = """You are a property viewing expert for the Dublin, Ireland market.
The buyer is mortgage-approved, chain-free, and needs a 2-bed/2-bath with ≥70sqm carpet area.
Be concise, practical, and prioritise questions that protect the buyer's timeline and AIP drawdown."""


def generate_checklist(prop: Property) -> list[ChecklistItem]:
    items: list[ChecklistItem] = []

    if prop.is_celtic_tiger_era and prop.property_type in ("apartment", "duplex"):
        items.append(ChecklistItem(
            category="Fire Safety",
            item="Obtain Architect's Certificate of Compliance for fire safety remediation",
            priority="critical",
            rationale="Celtic Tiger era (2000-2008) apartments may require costly fire safety works "
                      "which could add levies or delay mortgage drawdown.",
        ))

    if prop.property_type in ("apartment", "duplex"):
        items.append(ChecklistItem(
            category="Management",
            item="Confirm annual management fee, sinking fund balance, and any upcoming levies",
            priority="critical",
        ))
        items.append(ChecklistItem(
            category="Management",
            item="Ask for last 3 years of management company AGM minutes",
            priority="important",
        ))

    if prop.heating_type == "electric_storage":
        items.append(ChecklistItem(
            category="Heating",
            item="CRITICAL: Electric storage heating detected — check retrofit cost to gas/heat pump",
            priority="critical",
            rationale="Electric storage heating significantly increases running costs and reduces resale value.",
        ))

    if prop.carpet_area_sqm is None or (prop.missing_data_flags and "carpet_area_sqm" in prop.missing_data_flags):
        items.append(ChecklistItem(
            category="Dimensions",
            item="Measure or confirm carpet floor area (living room, each bedroom, bathrooms) — exclude hallways",
            priority="critical",
            rationale="Missing floor area is a red flag. Minimum requirement is 70sqm carpet area.",
        ))

    if prop.management_fee_eur and prop.management_fee_eur > 2000:
        items.append(ChecklistItem(
            category="Management",
            item=f"High management fee of €{prop.management_fee_eur:,}/yr — scrutinise sinking fund",
            priority="important",
        ))

    if prop.bathrooms == 1:
        items.append(ChecklistItem(
            category="Layout",
            item="Only 1 bathroom listed — check feasibility of adding en-suite in master bedroom",
            priority="critical",
        ))

    items.extend([
        ChecklistItem(category="Chain", item="Confirm seller is owner-occupier with no onward chain", priority="critical"),
        ChecklistItem(category="Parking", item="Identify allocated parking space number and EV charging provisions", priority="important"),
        ChecklistItem(category="Condition", item="Check windows, roof/balcony, damp spots, and floor condition", priority="important"),
        ChecklistItem(category="Direction", item="Note aspect — south/SE facing living rooms score bonus points", priority="nice_to_have"),
    ])

    return items


def generate_questions(prop: Property) -> list[AgentQuestion]:
    questions: list[AgentQuestion] = []

    if prop.is_celtic_tiger_era and prop.property_type in ("apartment", "duplex"):
        questions.append(AgentQuestion(
            category="Fire Safety",
            question="Has this building received a final Architect's Certificate of Compliance for fire safety, "
                     "or is there an active sinking fund levy covering remediation?",
            why_it_matters="Without a compliance cert, mortgage lenders may refuse drawdown.",
            red_flag_if="Agent is vague, says 'in progress', or mentions an open levy",
        ))

    if prop.property_type in ("apartment", "duplex"):
        questions.append(AgentQuestion(
            category="Management",
            question="What is the exact annual management fee breakdown, and what is the current sinking fund balance?",
            why_it_matters="Sinking fund covers unexpected repairs — a low balance means future levies.",
            red_flag_if="Fee > €2,500/yr or sinking fund < €500/unit",
        ))

    questions.append(AgentQuestion(
        category="Chain",
        question="Is the property currently owner-occupied? Are the title deeds already with the vendor's solicitor?",
        why_it_matters="Chain-free with deeds ready can shorten closing to 6-8 weeks.",
        red_flag_if="Vendor has not instructed a solicitor yet",
    ))

    if prop.carpet_area_sqm is None:
        questions.append(AgentQuestion(
            category="Dimensions",
            question="Can you confirm the exact carpet floor area in sqm, excluding hallways and storage?",
            why_it_matters="Missing floor area data is a common tactic to hide properties below our 70sqm minimum.",
            red_flag_if="Agent cannot confirm a floor plan or measurement",
        ))

    questions.append(AgentQuestion(
        category="Parking",
        question="Which specific parking space is allocated to this unit? Are there EV charging points or provisions?",
        why_it_matters="Unallocated parking in apartments is a common dispute source.",
    ))

    questions.append(AgentQuestion(
        category="Investment",
        question="If previously rented, what was the most recent registered RPZ rent?",
        why_it_matters="Sets the baseline for any future rental scenario and indicates investment yield.",
    ))

    return questions


def generate_missing_data_flags(prop: Property) -> list[MissingDataFlag]:
    flags: list[MissingDataFlag] = []
    missing = prop.missing_data_flags or []

    if prop.carpet_area_sqm is None or "carpet_area_sqm" in missing:
        flags.append(MissingDataFlag(
            field="carpet_area_sqm",
            description="Floor area not listed — critical for verifying ≥70sqm minimum",
            risk_level="critical",
        ))
    if prop.ber_rating is None:
        flags.append(MissingDataFlag(field="ber_rating", description="BER certificate missing", risk_level="moderate"))
    if prop.year_built is None:
        flags.append(MissingDataFlag(
            field="year_built",
            description="Year built unknown — cannot assess Celtic Tiger fire safety risk",
            risk_level="moderate",
        ))
    if prop.management_fee_eur is None and prop.property_type in ("apartment", "duplex"):
        flags.append(MissingDataFlag(field="management_fee_eur", description="Management fee not disclosed", risk_level="moderate"))

    return flags


def generate_email_draft(prop: Property, agent_name: str, visit_date: str, context: str = "") -> dict[str, str]:
    prompt = f"""Write a professional follow-up email to an estate agent after viewing a property.

Property: {prop.address or prop.title}
Agent name: {agent_name}
Visit date: {visit_date}
{f'Additional context: {context}' if context else ''}

The buyer is:
- Mortgage-approved (chain-free, AIP in place)
- Very interested but needs answers to: floor area (sqm carpet), management fee breakdown, fire safety cert status
- Can move quickly (6-8 week close)

Write a polite, professional email (subject line + body). Tone: enthusiastic but measured. Max 200 words body."""

    text = invoke_claude(prompt, system=SYSTEM_PROMPT)
    lines = text.strip().split("\n", 1)
    subject = lines[0].replace("Subject:", "").strip() if lines else "Following up on viewing"
    body = lines[1].strip() if len(lines) > 1 else text
    return {"subject": subject, "body": body}
