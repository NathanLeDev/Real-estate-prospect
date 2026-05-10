import os
import json
from groq import Groq
from dotenv import load_dotenv
from models import ProspectInput, ProspectScore, PriorityLevel, ScoreDimension, WeakSignal, RecommendedAction

load_dotenv()

SYSTEM_PROMPT = """You are an expert in prospect qualification for a luxury real estate agency (Monaco, Côte d'Azur, Paris 8th/16th arrondissement).

Your role is to analyze incoming prospect information and produce a precise, actionable quality score for the real estate agent.

## SCORING FRAMEWORK — 5 dimensions, each scored from 0 to 10

1. **SERIOUSNESS**: Specificity of the request, urgency markers, professional tone, depth of questions. A vague or tourist-like message scores low.

2. **FINANCIAL CAPACITY**: Coherence between the declared budget and the properties viewed. A prospect declaring €800k but only viewing €2M+ properties scores low. Precise questions about financing score high.

3. **PROJECT MATURITY**: Concrete timeline signals (job transfer in September, school enrollment), life triggers (relocation, divorce, inheritance), precise location criteria vs. "something nice on the coast".

4. **ENGAGEMENT QUALITY**: Properties viewed on the site (quantity, consistency with the request), length and personalization of the message, specific questions about particular properties.

5. **PROFILE COHERENCE**: Consistency between geographic origin, budget, and property type. Does everything align?

**agent_intermediaire**: the request comes from a representative, assistant, or mandated agent. High seriousness signal in luxury real estate.

**Global score** = weighted average:
  Seriousness×0.25 + FinancialCapacity×0.25 + ProjectMaturity×0.20 + EngagementQuality×0.15 + ProfileCoherence×0.15

**Priority mapping**:
  ≥ 8 → HIGH (contact within 2 hours)
  5–7 → MEDIUM (contact within 24 hours)
  ≤ 4 → LOW (nurturing sequence, no immediate call)

## WEAK SIGNALS TO SYSTEMATICALLY DETECT
- **relocation**: job transfer, international relocation, expatriation
- **investment**: questions about rental yield, portfolio diversification, "for my children"
- **primary_residence**: school, neighborhood, local lifestyle, home-to-work commute
- **fiscal_optimization**: LMNP, SCI, IFI, Monaco residency, non-resident taxation, wealth optimization
- **inheritance**: "family property", succession, asset liquidation
- **divorce**: sudden urgency, solo decision in a couple's context, "my situation has changed"
- **professional_project**: commercial use, professional premises, visible entrepreneur signal
- **retirement**: "enjoying life", slower lifestyle, retirement project

## CRITICAL RULES
- Never invent information absent from the file.
- If information is missing, flag it in the attention points.
- The budget_coherence analysis must mention the gap in euros if detectable.
- recommended_actions must be concrete and immediately actionable.
- agent_talking_points must be personalized to THIS specific prospect.
- Be factual, direct, no fluff. The agent reads this in 10 seconds."""

QUALIFICATION_TOOL = {
    "type": "function",
    "function": {
    "name": "qualify_prospect",
    "description": "Qualifies a luxury real estate prospect and returns a structured score with actionable recommendations",
    "parameters": {
        "type": "object",
        "properties": {
            "global_score": {
                "type": "integer",
                "description": "Overall qualification score from 1 to 10",
                "minimum": 1,
                "maximum": 10,
            },
            "priority_level": {
                "type": "string",
                "enum": ["HIGH", "MEDIUM", "LOW"],
                "description": "Priority level for the agent",
            },
            "score_breakdown": {
                "type": "array",
                "description": "Score breakdown by dimension (exactly 5 dimensions)",
                "items": {
                    "type": "object",
                    "properties": {
                        "dimension": {"type": "string"},
                        "score": {"type": "integer", "minimum": 0, "maximum": 10},
                        "rationale": {"type": "string"},
                    },
                    "required": ["dimension", "score", "rationale"],
                },
            },
            "positive_signals": {
                "type": "array",
                "description": "Detected positive signals — at least 1",
                "items": {"type": "string"},
            },
            "attention_points": {
                "type": "array",
                "description": "Attention points, negative signals or missing information — at least 1",
                "items": {"type": "string"},
            },
            "weak_signals": {
                "type": "array",
                "description": "Analysis of the 8 standardized weak signals",
                "items": {
                    "type": "object",
                    "properties": {
                        "signal_type": {
                            "type": "string",
                            "enum": [
                                "relocation",
                                "investment",
                                "primary_residence",
                                "fiscal_optimization",
                                "inheritance",
                                "divorce",
                                "professional_project",
                                "retirement",
                                "other",
                            ],
                        },
                        "detected": {"type": "boolean"},
                        "evidence": {
                            "type": "string",
                            "description": "Quote or paraphrase from the message that justifies the detection",
                        },
                    },
                    "required": ["signal_type", "detected", "evidence"],
                },
            },
            "budget_coherence": {
                "type": "string",
                "description": "Analysis of the coherence between declared budget and properties viewed, with gap in euros if applicable",
            },
            "project_maturity": {
                "type": "string",
                "enum": ["immediate", "short_term", "medium_term", "long_term", "undefined"],
                "description": "immediate=<3 months, short_term=3-12 months, medium_term=1-3 years, long_term=3+ years",
            },
            "recommended_actions": {
                "type": "array",
                "description": "Concrete and immediate actions for the agent — at least 1",
                "items": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string"},
                        "timing": {"type": "string"},
                        "priority": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 3,
                            "description": "1=urgent, 2=normal, 3=low",
                        },
                    },
                    "required": ["action", "timing", "priority"],
                },
            },
            "agent_talking_points": {
                "type": "array",
                "description": "Talking points personalized to this prospect — at least 2",
                "items": {"type": "string"},
            },
            "confidence_level": {
                "type": "string",
                "enum": ["high", "medium", "low"],
                "description": "Confidence level of the analysis (low if data is insufficient)",
            },
        },
        "required": [
            "global_score",
            "priority_level",
            "score_breakdown",
            "positive_signals",
            "attention_points",
            "weak_signals",
            "budget_coherence",
            "project_maturity",
            "recommended_actions",
            "agent_talking_points",
            "confidence_level",
        ],
    },
    },
}


def _build_user_prompt(prospect: ProspectInput) -> str:
    parts = [
        "=== PROSPECT FILE ===",
        f"Name: {prospect.name}",
        f"Geographic origin: {prospect.geographic_origin.value}",
        f"Declared budget: {prospect.declared_budget:,.0f} €",
        f"Property type sought: {prospect.property_type.value}",
        "",
        "=== INITIAL MESSAGE (verbatim) ===",
        f'"""{prospect.initial_message}"""',
    ]

    if prospect.properties_consulted:
        parts += ["", "=== PROPERTIES VIEWED ON THE SITE ==="]
        for p in prospect.properties_consulted:
            parts.append(f"  • {p}")
    else:
        parts += ["", "=== PROPERTIES VIEWED ON THE SITE ===", "No properties viewed recorded."]

    if prospect.portfolio:
        parts += ["", "=== AVAILABLE PORTFOLIO (provided by agent) ===", prospect.portfolio]

    return "\n".join(parts)


GROQ_MODEL = "llama-3.3-70b-versatile"


def score_prospect(prospect: ProspectInput, api_key: str | None = None) -> ProspectScore:
    """
    Calls Groq (llama-3.3-70b-versatile) via function calling to obtain a structured score.
    Raises ValueError if the API fails or the response is invalid.
    """
    key = api_key or os.getenv("GROQ_API_KEY")
    if not key:
        raise ValueError("Groq API key missing. Set GROQ_API_KEY in .env or enter it in the interface.")

    client = Groq(api_key=key)

    response = client.chat.completions.create(
        model=GROQ_MODEL,
        max_tokens=2048,
        tools=[QUALIFICATION_TOOL],
        tool_choice={"type": "function", "function": {"name": "qualify_prospect"}},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_prompt(prospect)},
        ],
    )

    tool_calls = response.choices[0].message.tool_calls
    if not tool_calls:
        raise ValueError("Groq did not return a structured result.")

    data = json.loads(tool_calls[0].function.arguments)

    return ProspectScore(
        global_score=data["global_score"],
        priority_level=PriorityLevel(data["priority_level"]),
        score_breakdown=[
            ScoreDimension(**d) for d in data["score_breakdown"]
        ],
        positive_signals=data["positive_signals"],
        attention_points=data["attention_points"],
        weak_signals=[WeakSignal(**s) for s in data["weak_signals"]],
        budget_coherence=data["budget_coherence"],
        project_maturity=data["project_maturity"],
        recommended_actions=[RecommendedAction(**a) for a in data["recommended_actions"]],
        agent_talking_points=data["agent_talking_points"],
        confidence_level=data["confidence_level"],
    )
