import os
from datetime import datetime
import streamlit as st
from dotenv import load_dotenv

from models import (
    GeographicOrigin,
    PriorityLevel,
    ProspectInput,
    PropertyType,
    ProspectScore,
)
from scorer import score_prospect

load_dotenv()

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Qualification Prospect — Immobilier Luxe",
    page_icon="🏛",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ─────────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    section[data-testid="stSidebar"] { padding-top: 1rem; }

    .score-card {
        padding: 1.5rem;
        border-radius: 10px;
        border-left: 5px solid;
        margin-bottom: 1.5rem;
    }
    .score-card h2 { margin: 0 0 0.25rem 0; }

    .badge {
        display: inline-block;
        padding: 4px 14px;
        border-radius: 20px;
        font-size: 0.78rem;
        font-weight: 700;
        letter-spacing: 0.05em;
        color: #fff;
        margin-top: 0.5rem;
    }

    .history-card {
        padding: 0.75rem 1rem;
        border-radius: 8px;
        border: 1px solid #E5E7EB;
        margin-bottom: 0.5rem;
        cursor: pointer;
    }
    .history-card-active {
        border-color: #6366F1;
        background: #EEF2FF;
    }

    .chip-on  { background: #D1FAE5; color: #065F46; padding: 3px 10px; border-radius: 12px; font-size: 0.8rem; margin: 2px; display: inline-block; }
    .chip-off { background: #F3F4F6; color: #9CA3AF; padding: 3px 10px; border-radius: 12px; font-size: 0.8rem; margin: 2px; display: inline-block; }

    .urg-1 { color: #DC2626; font-weight: 700; }
    .urg-2 { color: #D97706; font-weight: 600; }
    .urg-3 { color: #6B7280; font-weight: 500; }

    hr { margin: 1rem 0; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Constants ──────────────────────────────────────────────────────────────────
PRIORITY_CONF = {
    PriorityLevel.HIGH:   {"color": "#10B981", "bg": "#ECFDF5", "label": "PRIORITÉ HAUTE",   "score_color": "#10B981"},
    PriorityLevel.MEDIUM: {"color": "#F59E0B", "bg": "#FFFBEB", "label": "PRIORITÉ MOYENNE", "score_color": "#F59E0B"},
    PriorityLevel.LOW:    {"color": "#EF4444", "bg": "#FEF2F2", "label": "PRIORITÉ FAIBLE",  "score_color": "#EF4444"},
}

MATURITY_LABELS = {
    "immediate":   "⚡ Immédiat — moins de 3 mois",
    "short_term":  "📅 Court terme — 3 à 12 mois",
    "medium_term": "🗓️ Moyen terme — 1 à 3 ans",
    "long_term":   "🔭 Long terme — plus de 3 ans",
    "undefined":   "❓ Non défini",
}

CONFIDENCE_LABELS = {
    "high":   ("🟢", "Confiance haute"),
    "medium": ("🟡", "Confiance moyenne"),
    "low":    ("🔴", "Confiance faible"),
}

SIGNAL_LABELS = {
    "relocation":           "Relocation",
    "investment":           "Investissement",
    "primary_residence":    "Résidence principale",
    "fiscal_optimization":  "Optimisation fiscale",
    "inheritance":          "Héritage / Succession",
    "divorce":              "Séparation",
    "professional_project": "Projet professionnel",
    "retirement":           "Retraite",
    "other":                "Autre",
}

URGENCY_CLASS = {1: "urg-1", 2: "urg-2", 3: "urg-3"}
URGENCY_LABEL = {1: "URGENT", 2: "PRIORITAIRE", 3: "STANDARD"}

# ── Session state ──────────────────────────────────────────────────────────────
# history: list of dicts {"result": ProspectScore, "name": str, "origin": str, "at": str}
# selected_idx: which history entry is displayed in the detail view
if "history" not in st.session_state:
    st.session_state.history = []
if "selected_idx" not in st.session_state:
    st.session_state.selected_idx = 0


# ── Rendering helper ───────────────────────────────────────────────────────────
def render_analysis(result: ProspectScore, prospect_name: str, origin: str) -> None:
    """Render the full analysis detail for one prospect."""
    pconf = PRIORITY_CONF[result.priority_level]
    conf_icon, conf_label = CONFIDENCE_LABELS[result.confidence_level]

    # Score card
    st.markdown(
        f"""
        <div class="score-card" style="background:{pconf['bg']}; border-color:{pconf['color']};">
            <div style="display:flex; justify-content:space-between; align-items:flex-start; flex-wrap:wrap; gap:1rem;">
                <div>
                    <h2 style="color:#111827;">{prospect_name} — {origin}</h2>
                    <span class="badge" style="background:{pconf['color']};">{pconf['label']}</span>
                    &nbsp;
                    <span style="font-size:0.82rem; color:#6B7280;">{conf_icon} {conf_label}</span>
                </div>
                <div style="text-align:center;">
                    <div style="font-size:3.5rem; font-weight:800; color:{pconf['color']}; line-height:1;">
                        {result.global_score}<span style="font-size:1.5rem; color:#9CA3AF;">/10</span>
                    </div>
                    <div style="font-size:0.78rem; color:#6B7280; margin-top:4px;">SCORE DE QUALIFICATION</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Score breakdown
    with st.expander("Détail du scoring par dimension", expanded=True):
        for dim in result.score_breakdown:
            cols = st.columns([2, 4, 1])
            with cols[0]:
                st.markdown(f"**{dim.dimension}**")
            with cols[1]:
                st.progress(dim.score / 10)
            with cols[2]:
                st.markdown(f"**{dim.score}/10**")
            st.caption(dim.rationale)

    st.markdown("---")

    col_left, col_right = st.columns([3, 2], gap="large")

    with col_left:
        pos_col, att_col = st.columns(2)
        with pos_col:
            st.markdown("#### Points positifs")
            for signal in result.positive_signals:
                st.success(signal, icon="✅")
        with att_col:
            st.markdown("#### Points d'attention")
            if result.attention_points:
                for point in result.attention_points:
                    st.warning(point, icon="⚠️")
            else:
                st.markdown("*Aucun point d'attention majeur.*")

    with col_right:
        st.markdown("#### Signaux faibles")
        chips_html = ""
        for ws in result.weak_signals:
            label = SIGNAL_LABELS.get(ws.signal_type, ws.signal_type)
            if ws.detected:
                chips_html += f'<span class="chip-on">✓ {label}</span>'
                if ws.evidence:
                    chips_html += f'<br><small style="color:#065F46;margin-left:6px;font-style:italic;">"{ws.evidence}"</small><br>'
            else:
                chips_html += f'<span class="chip-off">{label}</span>'
        st.markdown(chips_html, unsafe_allow_html=True)

        st.markdown("#### Maturité du projet")
        st.info(MATURITY_LABELS[result.project_maturity])

        st.markdown("#### Cohérence budgétaire")
        st.markdown(result.budget_coherence)

    st.markdown("---")

    st.markdown("#### Actions recommandées")
    sorted_actions = sorted(result.recommended_actions, key=lambda a: a.priority)
    for action in sorted_actions:
        st.markdown(
            f'<span class="{URGENCY_CLASS[action.priority]}">▶ {URGENCY_LABEL[action.priority]}</span>'
            f' — {action.action}  \n'
            f'<span style="color:#6B7280; font-size:0.85rem;">⏰ {action.timing}</span>',
            unsafe_allow_html=True,
        )
        st.markdown("")

    st.markdown("---")

    st.markdown("#### Points de conversation pour l'agent")
    for tp in result.agent_talking_points:
        st.markdown(f"→ {tp}")

    st.markdown("---")

    # Export
    col_exp1, col_exp2, _ = st.columns([1, 1, 3])
    summary_lines = [
        f"Prospect : {prospect_name} — {origin}",
        f"Score : {result.global_score}/10 — {result.priority_level.value}",
        "",
        "Points positifs :",
        *[f"  ✓ {s}" for s in result.positive_signals],
        "",
        "Points d'attention :",
        *[f"  ⚠ {p}" for p in result.attention_points],
        "",
        "Actions recommandées :",
        *[f"  [{URGENCY_LABEL[a.priority]}] {a.action} ({a.timing})" for a in sorted_actions],
    ]
    with col_exp1:
        st.download_button(
            label="Exporter JSON",
            data=result.model_dump_json(indent=2),
            file_name=f"prospect_{prospect_name.replace(' ', '_')}.json",
            mime="application/json",
            use_container_width=True,
            key=f"dl_json_{prospect_name}",
        )
    with col_exp2:
        st.download_button(
            label="Exporter texte",
            data="\n".join(summary_lines),
            file_name=f"prospect_{prospect_name.replace(' ', '_')}.txt",
            mime="text/plain",
            use_container_width=True,
            key=f"dl_txt_{prospect_name}",
        )


# ── Sidebar — input form ───────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🏛 Qualification Prospect")
    st.caption("Agence Immobilière de Luxe — Usage interne")
    st.divider()

    api_key_env = os.getenv("GROQ_API_KEY", "")
    if not api_key_env:
        api_key_input = st.text_input(
            "Clé API Groq",
            type="password",
            placeholder="gsk_...",
            help="Ou définissez GROQ_API_KEY dans un fichier .env",
        )
    else:
        api_key_input = api_key_env
        st.caption("✅ Clé API chargée depuis .env")

    st.divider()

    with st.form("prospect_form", clear_on_submit=False):
        st.markdown("#### Dossier prospect")

        name = st.text_input("Nom complet *", placeholder="John Smith")
        geographic_origin = st.selectbox(
            "Origine géographique *",
            options=[e.value for e in GeographicOrigin],
            index=3,
        )
        declared_budget = st.number_input(
            "Budget déclaré (€) *",
            min_value=100_000,
            max_value=100_000_000,
            step=50_000,
            value=2_000_000,
            format="%d",
        )
        property_type = st.selectbox(
            "Type de bien recherché *",
            options=[e.value for e in PropertyType],
        )

        st.markdown("#### Message initial")
        initial_message = st.text_area(
            "Message verbatim *",
            height=180,
            placeholder="Collez ici le message exact du prospect, tel qu'il l'a écrit...",
        )

        st.markdown("#### Informations complémentaires")
        properties_raw = st.text_area(
            "Biens consultés sur le site",
            height=80,
            placeholder="REF-001 — Villa Cannes 3.2M€\nREF-007 — App. Monaco 2.8M€",
            help="Un bien par ligne",
        )
        portfolio = st.text_area(
            "Portefeuille disponible (optionnel)",
            height=80,
            placeholder="Villa Les Pins — 3.2M€ — 5ch — piscine — Mougins\nApp. Carré d'Or — 2.1M€ — vue mer — Monaco",
            help="Permet au modèle de suggérer des biens précis",
        )

        submitted = st.form_submit_button(
            "ANALYSER CE PROSPECT",
            type="primary",
            use_container_width=True,
        )

    if st.session_state.history:
        if st.button("Vider l'historique", use_container_width=True):
            st.session_state.history = []
            st.session_state.selected_idx = 0
            st.rerun()

    st.divider()
    st.caption("Modèle : llama-3.3-70b-versatile (Groq)")

# ── Form processing ────────────────────────────────────────────────────────────
if submitted:
    errors = []
    if not name.strip():
        errors.append("Le nom du prospect est requis.")
    if not initial_message.strip():
        errors.append("Le message initial est requis.")
    if not api_key_input:
        errors.append("La clé API Groq est requise.")

    if errors:
        for e in errors:
            st.sidebar.error(e)
    else:
        properties_list = [
            line.strip()
            for line in properties_raw.splitlines()
            if line.strip()
        ]

        prospect = ProspectInput(
            name=name.strip(),
            geographic_origin=GeographicOrigin(geographic_origin),
            declared_budget=declared_budget,
            property_type=PropertyType(property_type),
            initial_message=initial_message.strip(),
            properties_consulted=properties_list,
            portfolio=portfolio.strip(),
        )

        with st.spinner("Analyse en cours via Groq — llama-3.3-70b…"):
            try:
                result = score_prospect(prospect, api_key_input)
                st.session_state.history.insert(0, {
                    "result": result,
                    "name": name.strip(),
                    "origin": geographic_origin,
                    "at": datetime.now().strftime("%H:%M"),
                })
                st.session_state.selected_idx = 0
            except Exception as exc:
                st.error(f"Erreur lors de l'analyse : {exc}")

# ── Main area ──────────────────────────────────────────────────────────────────
if not st.session_state.history:
    st.markdown(
        """
        <div style="text-align:center; padding:80px 20px; color:#9CA3AF;">
            <div style="font-size:3.5rem; margin-bottom:16px;">🏛</div>
            <h3 style="color:#6B7280; font-weight:400;">Aucune analyse en cours</h3>
            <p style="max-width:400px; margin:0 auto;">
                Remplissez le formulaire dans la barre latérale et cliquez sur
                <strong>Analyser ce prospect</strong> pour obtenir un scoring en 10 secondes.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
else:
    history = st.session_state.history

    # ── History bar ────────────────────────────────────────────────────────────
    n = len(history)
    if n > 1:
        st.markdown(f"#### Historique de session — {n} prospect{'s' if n > 1 else ''} analysé{'s' if n > 1 else ''}")
        cols = st.columns(min(n, 6))
        for i, entry in enumerate(history[:6]):
            pconf = PRIORITY_CONF[entry["result"].priority_level]
            score = entry["result"].global_score
            is_selected = (i == st.session_state.selected_idx)
            border = f"2px solid {pconf['color']}" if is_selected else "1px solid #E5E7EB"
            bg = pconf["bg"] if is_selected else "#FAFAFA"
            with cols[i]:
                st.markdown(
                    f"""
                    <div style="padding:0.6rem 0.8rem; border-radius:8px; border:{border};
                                background:{bg}; text-align:center; margin-bottom:4px;">
                        <div style="font-weight:600; font-size:0.82rem; white-space:nowrap;
                                    overflow:hidden; text-overflow:ellipsis;">{entry['name']}</div>
                        <div style="font-size:1.4rem; font-weight:800; color:{pconf['color']};">{score}/10</div>
                        <div style="font-size:0.7rem; color:{pconf['color']};">{entry['result'].priority_level.value}</div>
                        <div style="font-size:0.68rem; color:#9CA3AF;">{entry['at']}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                if not is_selected:
                    if st.button("Voir", key=f"sel_{i}", use_container_width=True):
                        st.session_state.selected_idx = i
                        st.rerun()
        st.markdown("---")

    # ── Detail view of selected prospect ──────────────────────────────────────
    entry = history[st.session_state.selected_idx]
    render_analysis(entry["result"], entry["name"], entry["origin"])
