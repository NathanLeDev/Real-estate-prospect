import os
import json
from groq import Groq
from dotenv import load_dotenv
from models import ProspectInput, ProspectScore, PriorityLevel, ScoreDimension, WeakSignal, RecommendedAction

load_dotenv()

SYSTEM_PROMPT = """Tu es un expert en qualification de prospects pour une agence immobilière de luxe (Monaco, Côte d'Azur, Paris 8e/16e).

Ton rôle est d'analyser les informations d'un prospect entrant et de produire un scoring de qualité précis et actionnable pour l'agent immobilier.

## FRAMEWORK DE SCORING — 5 dimensions, chacune notée de 0 à 10

1. **SÉRIEUX** : Spécificité de la demande, marqueurs d'urgence, ton professionnel, profondeur des questions. Un message vague ou touristique score bas.

2. **CAPACITÉ FINANCIÈRE** : Cohérence entre le budget déclaré et les biens consultés. Un prospect déclarant 800k€ mais ne consultant que des biens à 2M€+ score bas. Des questions précises sur le financement score haut.

3. **MATURITÉ DU PROJET** : Signaux de délai concret (mutation en septembre, inscription scolaire), déclencheurs de vie (déménagement, divorce, héritage), critères de localisation précis vs "quelque chose de beau sur la côte".

4. **QUALITÉ D'ENGAGEMENT** : Biens consultés sur le site (quantité, cohérence avec la demande), longueur et personnalisation du message, questions spécifiques sur des biens précis.

5. **COHÉRENCE DU PROFIL** : Consistance entre l'origine géographique, le budget, le type de bien. Est-ce que tout s'aligne ?

**agent_intermediaire** : la demande vient d'un représentant, assistant, ou agent mandaté. Signal de sérieux élevé dans le luxe.

**Score global** = moyenne pondérée :
  Sérieux×0.25 + CapacitéFinancière×0.25 + MaturitéProjet×0.20 + QualitéEngagement×0.15 + CohérenceProfil×0.15

**Mapping priorité** :
  ≥ 8 → HIGH (contact dans les 2h)
  5–7 → MEDIUM (contact dans les 24h)
  ≤ 4 → LOW (séquence nurturing, pas d'appel immédiat)

## SIGNAUX FAIBLES À DÉTECTER SYSTÉMATIQUEMENT
- **relocation** : mutation professionnelle, déménagement international, expatriation
- **investment** : questions sur le rendement locatif, diversification de portefeuille, "pour mes enfants"
- **primary_residence** : école, quartier, vie locale, transport domicile-travail
- **fiscal_optimization** : LMNP, SCI, IFI, résidence Monaco, fiscalité non-résident, optimisation patrimoniale
- **inheritance** : "bien de famille", succession, liquidation de patrimoine
- **divorce** : urgence soudaine, décision solo dans un contexte de couple, "ma situation a changé"
- **professional_project** : usage commercial, local professionnel, signal entrepreneur visible
- **retirement** : "profiter de la vie", rythme de vie plus lent, projet de retraite

## RÈGLES CRITIQUES
- Ne jamais inventer d'informations absentes du dossier.
- Si une information est manquante, la signaler dans les points d'attention.
- L'analyse budget_coherence doit mentionner l'écart en euros si détectable.
- Les recommended_actions doivent être concrètes et immédiatement actionnables.
- Les agent_talking_points doivent être personnalisés à CE prospect spécifique.
- Sois factuel, direct, sans fioritures. L'agent lit ça en 10 secondes."""

QUALIFICATION_TOOL = {
    "type": "function",
    "function": {
    "name": "qualify_prospect",
    "description": "Qualifie un prospect immobilier luxe et retourne un scoring structuré avec recommandations actionnables",
    "parameters": {
        "type": "object",
        "properties": {
            "global_score": {
                "type": "integer",
                "description": "Score global de qualification de 1 à 10",
                "minimum": 1,
                "maximum": 10,
            },
            "priority_level": {
                "type": "string",
                "enum": ["HIGH", "MEDIUM", "LOW"],
                "description": "Niveau de priorité pour l'agent",
            },
            "score_breakdown": {
                "type": "array",
                "description": "Détail du scoring par dimension (exactement 5 dimensions)",
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
                "description": "Signaux positifs détectés — au moins 1",
                "items": {"type": "string"},
            },
            "attention_points": {
                "type": "array",
                "description": "Points d'attention, signaux négatifs ou informations manquantes — au moins 1",
                "items": {"type": "string"},
            },
            "weak_signals": {
                "type": "array",
                "description": "Analyse des 8 signaux faibles standardisés",
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
                            "description": "Citation ou paraphrase du message qui justifie la détection",
                        },
                    },
                    "required": ["signal_type", "detected", "evidence"],
                },
            },
            "budget_coherence": {
                "type": "string",
                "description": "Analyse de la cohérence entre budget déclaré et biens consultés, avec écart en euros si applicable",
            },
            "project_maturity": {
                "type": "string",
                "enum": ["immediate", "short_term", "medium_term", "long_term", "undefined"],
                "description": "immediate=<3 mois, short_term=3-12 mois, medium_term=1-3 ans, long_term=3+ ans",
            },
            "recommended_actions": {
                "type": "array",
                "description": "Actions concrètes et immédiates pour l'agent — au moins 1",
                "items": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string"},
                        "timing": {"type": "string"},
                        "priority": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 3,
                            "description": "1=urgent, 2=normal, 3=faible",
                        },
                    },
                    "required": ["action", "timing", "priority"],
                },
            },
            "agent_talking_points": {
                "type": "array",
                "description": "Points de conversation personnalisés à ce prospect — au moins 2",
                "items": {"type": "string"},
            },
            "confidence_level": {
                "type": "string",
                "enum": ["high", "medium", "low"],
                "description": "Niveau de confiance de l'analyse (low si données insuffisantes)",
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
        "=== DOSSIER PROSPECT ===",
        f"Nom : {prospect.name}",
        f"Origine géographique : {prospect.geographic_origin.value}",
        f"Budget déclaré : {prospect.declared_budget:,.0f} €",
        f"Type de bien recherché : {prospect.property_type.value}",
        "",
        "=== MESSAGE INITIAL (verbatim) ===",
        f'"""{prospect.initial_message}"""',
    ]

    if prospect.properties_consulted:
        parts += ["", "=== BIENS CONSULTÉS SUR LE SITE ==="]
        for p in prospect.properties_consulted:
            parts.append(f"  • {p}")
    else:
        parts += ["", "=== BIENS CONSULTÉS SUR LE SITE ===", "Aucun bien consulté enregistré."]

    if prospect.portfolio:
        parts += ["", "=== PORTEFEUILLE DISPONIBLE (fourni par l'agent) ===", prospect.portfolio]

    return "\n".join(parts)


GROQ_MODEL = "llama-3.3-70b-versatile"


def score_prospect(prospect: ProspectInput, api_key: str | None = None) -> ProspectScore:
    """
    Appelle Groq (llama-3.3-70b-versatile) via function calling pour obtenir un scoring structuré.
    Lève ValueError si l'API échoue ou si la réponse est invalide.
    """
    key = api_key or os.getenv("GROQ_API_KEY")
    if not key:
        raise ValueError("Clé API Groq manquante. Définissez GROQ_API_KEY dans .env ou saisissez-la dans l'interface.")

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
        raise ValueError("Groq n'a pas retourné de résultat structuré.")

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
