from pydantic import BaseModel, Field
from typing import Literal
from enum import Enum


class PropertyType(str, Enum):
    APARTMENT = "Appartement"
    HOUSE = "Maison / Villa"
    PENTHOUSE = "Penthouse / Duplex"
    CHALET = "Chalet"
    CASTLE = "Château / Propriété de prestige"
    LAND = "Terrain / Foncier"
    COMMERCIAL = "Bien commercial / Investissement"
    OTHER = "Autre"


class GeographicOrigin(str, Enum):
    LOCAL = "Local (même région)"
    NATIONAL = "National (autre région)"
    EUROPEAN = "Européen (UE)"
    INTERNATIONAL = "International (hors UE)"
    UNKNOWN = "Non précisé"


class PriorityLevel(str, Enum):
    HIGH = "HAUTE"
    MEDIUM = "MOYENNE"
    LOW = "FAIBLE"


class ProspectInput(BaseModel):
    name: str
    geographic_origin: GeographicOrigin
    declared_budget: float
    property_type: PropertyType
    initial_message: str
    properties_consulted: list[str] = Field(default_factory=list)
    portfolio: str = ""


class ScoreDimension(BaseModel):
    dimension: str
    score: int = Field(ge=0, le=10)
    rationale: str


class WeakSignal(BaseModel):
    signal_type: Literal[
        "relocation",
        "investment",
        "primary_residence",
        "fiscal_optimization",
        "inheritance",
        "divorce",
        "professional_project",
        "retirement",
        "other",
    ]
    detected: bool
    evidence: str = ""


class RecommendedAction(BaseModel):
    action: str
    timing: str
    priority: int = Field(ge=1, le=3)  # 1=urgent, 2=normal, 3=low


class ProspectScore(BaseModel):
    global_score: int = Field(ge=1, le=10)
    priority_level: PriorityLevel
    score_breakdown: list[ScoreDimension]
    positive_signals: list[str]
    attention_points: list[str]
    weak_signals: list[WeakSignal]
    budget_coherence: str
    project_maturity: Literal[
        "immediate", "short_term", "medium_term", "long_term", "undefined"
    ]
    recommended_actions: list[RecommendedAction]
    agent_talking_points: list[str]
    confidence_level: Literal["high", "medium", "low"]
