import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

DATA_PATH = Path(__file__).parent / "output" / "parsed_resumes.json"

REGIONS = ["US", "Europe", "Asia-Pacific", "Other"]
INVESTMENT_APPROACHES = ["Fundamental", "Systematic/Quantitative", "Both/Hybrid", "Unclear"]
SECTORS = [
    "Technology", "Healthcare", "Financial Services", "Energy",
    "Industrials", "Consumer", "Credit", "Macro", "Other",
]
SENIORITY_LEVELS = [
    "Intern/Undergraduate",
    "Analyst (0-2 yrs)",
    "Experienced Analyst (2-5 yrs)",
    "Associate+ (5+ yrs)",
]
LIST_COLUMNS = ["secondary_sectors", "certifications", "technical_skills", "languages"]

def lighten(hex_color: str, amount: float) -> str:
    """Blend a hex color toward white by `amount` (0 = unchanged, 1 = white)."""
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i : i + 2], 16) for i in (0, 2, 4))
    r, g, b = (round(c + (255 - c) * amount) for c in (r, g, b))
    return f"#{r:02x}{g:02x}{b:02x}"


# Each single-series chart gets its own lighter tone (blended toward white, not a
# separate hue picked by eye) instead of the same saturated accent color repeated
# everywhere. Base hues come from the same categorical palette used for the approach
# pie below, so the whole page still reads as one coordinated set.
REGION_COLOR = lighten("#2a78d6", 0.35)      # blue
SECTOR_COLOR = lighten("#1baf7a", 0.35)      # aqua
EXPERIENCE_COLOR = lighten("#eb6834", 0.35)  # orange

# Fixed categorical map for the approach pie chart, so a slice's color always means
# the same approach regardless of which subset is currently filtered in. Lightened
# less than the single-series charts above so the four slices stay distinguishable.
APPROACH_COLORS = {
    approach: lighten(base, 0.2)
    for approach, base in zip(
        INVESTMENT_APPROACHES, ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
    )
}

# Friendly labels for every field a user sees, so the UI never leaks a raw
# snake_case field name (e.g. "full_name" -> "Full Name").
COLUMN_LABELS = {
    "full_name": "Full Name",
    "region": "Region",
    "location_city": "City",
    "current_title": "Title",
    "current_employer": "Employer",
    "primary_sector": "Sector",
    "investment_approach": "Approach",
    "seniority_level": "Seniority",
    "years_experience": "Experience",
}

st.set_page_config(page_title="Candidate Search - BD Sourcing", layout="wide")


@st.cache_data
def load_candidates(path: Path) -> pd.DataFrame:
    with open(path, "r", encoding="utf-8") as f:
        records = json.load(f)
    df = pd.DataFrame(records)
    for col in LIST_COLUMNS:
        if col not in df.columns:
            df[col] = [[] for _ in range(len(df))]
        else:
            df[col] = df[col].apply(lambda v: v if isinstance(v, list) else [])
    if "education" not in df.columns:
        df["education"] = [[] for _ in range(len(df))]
    df["years_experience"] = pd.to_numeric(df.get("years_experience"), errors="coerce").fillna(0.0)
    search_source_cols = ["full_name", "current_title", "current_employer", "summary"]
    df["_search_text"] = df.apply(
        lambda row: " ".join(
            [str(row.get(c, "")) for c in search_source_cols]
            + row.get("technical_skills", [])
            + row.get("certifications", [])
        ).lower(),
        axis=1,
    )
    return df


if not DATA_PATH.exists():
    st.error(f"No parsed data found at {DATA_PATH}. Run the parsing pipeline in the notebook first.")
    st.stop()

df = load_candidates(DATA_PATH)

st.title("Candidate Resume Search")
st.caption("Business Development sourcing tool for filtering parsed candidate profiles by market, strategy, sector, and seniority.")

with st.sidebar:
    st.header("Filters")
    keyword = st.text_input("Keyword Search", placeholder="e.g. Python, private equity, Stanford")
    region_filter = st.multiselect("Region", REGIONS)
    approach_filter = st.multiselect("Investment Approach", INVESTMENT_APPROACHES)
    sector_filter = st.multiselect("Sector (Primary or Secondary)", SECTORS)
    seniority_filter = st.multiselect("Seniority Level", SENIORITY_LEVELS)

    max_exp = max(float(df["years_experience"].max()), 1.0)
    exp_range = st.slider("Years of Experience", min_value=0.0, max_value=max_exp, value=(0.0, max_exp))

    all_certs = sorted({c for certs in df["certifications"] for c in certs})
    cert_filter = st.multiselect("Certifications", all_certs)

filtered = df

if keyword:
    filtered = filtered[filtered["_search_text"].str.contains(keyword.lower(), na=False)]
if region_filter:
    filtered = filtered[filtered["region"].isin(region_filter)]
if approach_filter:
    filtered = filtered[filtered["investment_approach"].isin(approach_filter)]
if sector_filter:
    filtered = filtered[
        filtered["primary_sector"].isin(sector_filter)
        | filtered["secondary_sectors"].apply(lambda secs: any(s in sector_filter for s in secs))
    ]
if seniority_filter:
    filtered = filtered[filtered["seniority_level"].isin(seniority_filter)]
filtered = filtered[filtered["years_experience"].between(exp_range[0], exp_range[1])]
if cert_filter:
    filtered = filtered[filtered["certifications"].apply(lambda certs: any(c in cert_filter for c in certs))]

st.subheader(f"{len(filtered)} of {len(df)} candidates match")

display_cols = [c for c in COLUMN_LABELS if c in filtered.columns]
column_config = {
    col: st.column_config.NumberColumn(label, format="%.1f yrs")
    if col == "years_experience"
    else st.column_config.Column(label)
    for col, label in COLUMN_LABELS.items()
}
st.dataframe(
    filtered[display_cols].reset_index(drop=True),
    hide_index=True,
    column_config=column_config,
)

st.markdown("#### Candidate Detail")
if len(filtered):
    selected_name = st.selectbox("Select a Candidate", filtered["full_name"].tolist())
    candidate = filtered[filtered["full_name"] == selected_name].iloc[0]
    st.markdown(f"**{candidate['full_name']}** — {candidate.get('current_title') or 'N/A'} at {candidate.get('current_employer') or 'N/A'}")
    st.write(candidate.get("summary", ""))

    m1, m2, m3 = st.columns(3)
    m1.metric("Region", candidate.get("region", "N/A"))
    m2.metric("Approach", candidate.get("investment_approach", "N/A"))
    m3.metric("Experience", f"{candidate.get('years_experience', 0):.1f} yrs")

    if candidate.get("technical_skills"):
        st.markdown("**Skills:** " + ", ".join(candidate["technical_skills"]))
    if candidate.get("certifications"):
        st.markdown("**Certifications:** " + ", ".join(candidate["certifications"]))
    if candidate.get("education"):
        st.markdown("**Education:**")
        for edu in candidate["education"]:
            st.write(f"- {edu.get('degree', '')}, {edu.get('institution', '')} ({edu.get('graduation_year', '')})")
else:
    st.info("No candidates match the current filters.")

st.markdown("#### Candidate Distribution")
if len(filtered):
    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:
        region_counts = filtered["region"].value_counts().reset_index()
        region_counts.columns = ["Region", "Count"]
        fig_region = px.bar(region_counts, x="Region", y="Count", title="Candidates by Region")
        fig_region.update_traces(marker_color=REGION_COLOR)
        fig_region.update_layout(bargap=0.3, margin=dict(t=40, l=10, r=10, b=10))
        st.plotly_chart(fig_region)

        approach_counts = filtered["investment_approach"].value_counts().reset_index()
        approach_counts.columns = ["Approach", "Count"]
        fig_approach = px.pie(
            approach_counts, names="Approach", values="Count", title="Investment Approach Mix",
            color="Approach", color_discrete_map=APPROACH_COLORS,
        )
        fig_approach.update_traces(textfont_color="#0b0b0b")
        fig_approach.update_layout(margin=dict(t=40, l=10, r=10, b=10))
        st.plotly_chart(fig_approach)

    with chart_col2:
        sector_counts = filtered["primary_sector"].value_counts().reset_index()
        sector_counts.columns = ["Sector", "Count"]
        sector_counts = sector_counts.sort_values("Count")  # largest ends up on top
        fig_sector = px.bar(sector_counts, x="Count", y="Sector", orientation="h", title="Candidates by Primary Sector")
        fig_sector.update_traces(marker_color=SECTOR_COLOR)
        fig_sector.update_layout(bargap=0.3, margin=dict(t=40, l=10, r=10, b=10))
        st.plotly_chart(fig_sector)

        fig_exp = px.histogram(
            filtered, x="years_experience", nbins=10, title="Experience Distribution (Years)",
            labels={"years_experience": "Years of Experience"},
        )
        fig_exp.update_traces(marker_color=EXPERIENCE_COLOR)
        fig_exp.update_layout(bargap=0.1, margin=dict(t=40, l=10, r=10, b=10))
        st.plotly_chart(fig_exp)
else:
    st.info("No data to visualize.")
