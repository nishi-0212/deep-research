import uuid
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


class Status(str, Enum):
    queued = "queued"
    planning = "planning"
    searching = "searching"
    collecting_evidence = "collecting_evidence"
    analyzing = "analyzing"
    generating_report = "generating_report"
    completed = "completed"
    failed = "failed"


class Evidence(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    source_type: str          # slack | documents | meetings
    reference: str            # channel / doc / meeting name
    date: str
    snippet: str
    url: str
    research_area: str
    score: float = 0.0


class Finding(BaseModel):
    kind: str                 # "evidence" or "inference"
    statement: str
    evidence_ids: list[str]
    confidence: float = 0.0


class Step(BaseModel):
    name: str
    status: str = "pending"   # pending | running | done
    detail: str = ""


class ResearchRequest(BaseModel):
    question: str
    sources: list[str] = ["slack", "documents", "meetings"]


class Research(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:10])
    user_id: str
    question: str
    sources: list[str]
    status: Status = Status.queued
    steps: list[Step] = []
    areas: list[str] = []
    queries: dict[str, list[str]] = {}
    evidence: list[Evidence] = []
    findings: list[Finding] = []
    report: dict | None = None
    error: str | None = None
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())