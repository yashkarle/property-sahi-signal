from pydantic import BaseModel


class ChecklistItem(BaseModel):
    category: str
    item: str
    priority: str  # "critical" | "important" | "nice_to_have"
    rationale: str | None = None


class AgentQuestion(BaseModel):
    category: str
    question: str
    why_it_matters: str
    red_flag_if: str | None = None


class MissingDataFlag(BaseModel):
    field: str
    description: str
    risk_level: str  # "critical" | "moderate" | "low"


class ViewingChecklistResponse(BaseModel):
    property_id: str
    items: list[ChecklistItem]
    ai_narrative: str | None = None


class ViewingQuestionsResponse(BaseModel):
    property_id: str
    questions: list[AgentQuestion]


class MissingDataResponse(BaseModel):
    property_id: str
    missing_fields: list[MissingDataFlag]
    risk_flags: list[str]


class EmailDraftRequest(BaseModel):
    agent_name: str
    visit_date: str
    additional_context: str | None = None


class EmailDraftResponse(BaseModel):
    subject: str
    body: str
