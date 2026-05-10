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
    page_title="Prospect Qualification — Luxury Real Estate",
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
    PriorityLevel.HIGH:   {"color": "#10B981", "bg": "#ECFDF5", "label": "HIGH PRIORITY"},
    PriorityLevel.MEDIUM: {"color": "#F59E0B", "bg": "#FFFBEB", "label": "MEDIUM PRIORITY"},
    PriorityLevel.LOW:    {"color": "#EF4444", "bg": "#FEF2F2", "label": "LOW PRIORITY"},
}

MATURITY_LABELS = {
    "immediate":   "⚡ Immediate — under 3 months",
    "short_term":  "📅 Short term — 3 to 12 months",
    "medium_term": "🗓️ Medium term — 1 to 3 years",
    "long_term":   "🔭 Long term — over 3 years",
    "undefined":   "❓ Undefined",
}

CONFIDENCE_LABELS = {
    "high":   ("🟢", "High confidence — sufficient data"),
    "medium": ("🟡", "Medium confidence — some data missing"),
    "low":    ("🔴", "Low confidence — message too short or ambiguous"),
}

SIGNAL_LABELS = {
    "relocation":           "Relocation",
    "investment":           "Investment",
    "primary_residence":    "Primary residence",
    "fiscal_optimization":  "Tax optimization",
    "inheritance":          "Inheritance",
    "divorce":              "Separation / Divorce",
    "professional_project": "Professional project",
    "retirement":           "Retirement",
    "other":                "Other",
}

URGENCY_CLASS = {1: "urg-1", 2: "urg-2", 3: "urg-3"}
URGENCY_LABEL = {1: "URGENT", 2: "PRIORITY", 3: "STANDARD"}

# ── Session state ──────────────────────────────────────────────────────────────
if "history" not in st.session_state:
    st.session_state.history = []
if "selected_idx" not in st.session_state:
    st.session_state.selected_idx = 0


# ── Rendering helper ───────────────────────────────────────────────────────────
def render_analysis(result: ProspectScore, prospect_name: str, origin: str) -> None:
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
                    <div style="font-size:0.78rem; color:#6B7280; margin-top:4px;">QUALIFICATION SCORE</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Score breakdown
    with st.expander("Score breakdown by dimension", expanded=True):
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
            st.markdown("#### Positive signals")
            for signal in result.positive_signals:
                st.success(signal, icon="✅")
        with att_col:
            st.markdown("#### Attention points")
            if result.attention_points:
                for point in result.attention_points:
                    st.warning(point, icon="⚠️")
            else:
                st.markdown("*No major attention points.*")

    with col_right:
        st.markdown("#### Weak signals")
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

        st.markdown("#### Project maturity")
        st.info(MATURITY_LABELS[result.project_maturity])

        st.markdown("#### Budget coherence")
        st.markdown(result.budget_coherence)

    st.markdown("---")

    st.markdown("#### Recommended actions")
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

    st.markdown("#### Agent talking points")
    for tp in result.agent_talking_points:
        st.markdown(f"→ {tp}")

    st.markdown("---")

    # Export
    col_exp1, col_exp2, _ = st.columns([1, 1, 3])
    sorted_actions_export = sorted(result.recommended_actions, key=lambda a: a.priority)
    summary_lines = [
        f"Prospect: {prospect_name} — {origin}",
        f"Score: {result.global_score}/10 — {result.priority_level.value}",
        "",
        "Positive signals:",
        *[f"  ✓ {s}" for s in result.positive_signals],
        "",
        "Attention points:",
        *[f"  ⚠ {p}" for p in result.attention_points],
        "",
        "Recommended actions:",
        *[f"  [{URGENCY_LABEL[a.priority]}] {a.action} ({a.timing})" for a in sorted_actions_export],
    ]
    with col_exp1:
        st.download_button(
            label="Export JSON",
            data=result.model_dump_json(indent=2),
            file_name=f"prospect_{prospect_name.replace(' ', '_')}.json",
            mime="application/json",
            use_container_width=True,
            key=f"dl_json_{prospect_name}",
        )
    with col_exp2:
        st.download_button(
            label="Export text",
            data="\n".join(summary_lines),
            file_name=f"prospect_{prospect_name.replace(' ', '_')}.txt",
            mime="text/plain",
            use_container_width=True,
            key=f"dl_txt_{prospect_name}",
        )


# ── Sidebar — input form ───────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🏛 Prospect Qualification")
    st.caption("Luxury Real Estate — Internal use only")
    st.divider()

    api_key_env = os.getenv("GROQ_API_KEY", "")
    if not api_key_env:
        api_key_input = st.text_input(
            "Groq API Key",
            type="password",
            placeholder="gsk_...",
            help="Or set GROQ_API_KEY in a .env file",
        )
    else:
        api_key_input = api_key_env

    with st.form("prospect_form", clear_on_submit=False):
        st.markdown("#### Prospect file")

        name = st.text_input("Full name *", placeholder="John Smith")
        geographic_origin = st.selectbox(
            "Geographic origin *",
            options=list(GeographicOrigin),
            index=3,
            format_func=lambda x: x.value,
        )
        declared_budget = st.number_input(
            "Declared budget (€) *",
            min_value=100_000,
            max_value=100_000_000,
            step=50_000,
            value=2_000_000,
            format="%d",
        )
        property_type = st.selectbox(
            "Property type *",
            options=list(PropertyType),
            format_func=lambda x: x.value,
        )

        st.markdown("#### Initial message")
        initial_message = st.text_area(
            "Verbatim message *",
            height=180,
            placeholder="Paste the prospect's exact message here...",
        )

        st.markdown("#### Additional information")
        properties_raw = st.text_area(
            "Properties viewed on site",
            height=80,
            placeholder="REF-001 — Villa Cannes €3.2M\nREF-007 — Apt. Monaco €2.8M",
            help="One property per line",
        )
        portfolio = st.text_area(
            "Available portfolio (optional)",
            height=80,
            placeholder="Villa Les Pins — €3.2M — 5br — pool — Mougins\nApt. Carré d'Or — €2.1M — sea view — Monaco",
            help="Allows the model to suggest specific properties",
        )

        submitted = st.form_submit_button(
            "ANALYSE PROSPECT",
            type="primary",
            use_container_width=True,
        )

    if st.session_state.history:
        if st.button("Clear history", use_container_width=True):
            st.session_state.history = []
            st.session_state.selected_idx = 0
            st.rerun()

# ── Form processing ────────────────────────────────────────────────────────────
if submitted:
    errors = []
    if not name.strip():
        errors.append("Prospect name is required.")
    if not initial_message.strip():
        errors.append("Initial message is required.")
    if not api_key_input:
        errors.append("Groq API key is required.")

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
            geographic_origin=geographic_origin,
            declared_budget=declared_budget,
            property_type=property_type,
            initial_message=initial_message.strip(),
            properties_consulted=properties_list,
            portfolio=portfolio.strip(),
        )

        with st.spinner("Analysing…"):
            try:
                result = score_prospect(prospect, api_key_input)
                st.session_state.history.insert(0, {
                    "result": result,
                    "name": name.strip(),
                    "origin": geographic_origin.value,
                    "at": datetime.now().strftime("%H:%M"),
                })
                st.session_state.selected_idx = 0
            except Exception as exc:
                st.error(f"Analysis error: {exc}")

# ── Main area ──────────────────────────────────────────────────────────────────
if not st.session_state.history:
    st.markdown(
        """
        <div style="text-align:center; padding:80px 20px; color:#9CA3AF;">
            <div style="font-size:3.5rem; margin-bottom:16px;">🏛</div>
            <h3 style="color:#6B7280; font-weight:400;">No analysis yet</h3>
            <p style="max-width:400px; margin:0 auto;">
                Fill in the form in the sidebar and click
                <strong>Analyse Prospect</strong> to get a score in 10 seconds.
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
        st.markdown(f"#### Session history — {n} prospect{'s' if n > 1 else ''} analysed")
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
                    if st.button("View", key=f"sel_{i}", use_container_width=True):
                        st.session_state.selected_idx = i
                        st.rerun()
        st.markdown("---")

    # ── Detail view ────────────────────────────────────────────────────────────
    entry = history[st.session_state.selected_idx]
    render_analysis(entry["result"], entry["name"], entry["origin"])
