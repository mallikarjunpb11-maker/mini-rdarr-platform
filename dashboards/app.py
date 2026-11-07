"""
Enterprise Risk Data Aggregation & Risk Reporting (RDARR) Platform
Framework: Basel Committee on Banking Supervision (BCBS 239)
Interactive Chief Risk Officer (CRO) & Regulatory Monitoring Portal
"""

import json
import yaml
from pathlib import Path
import pandas as pd
import plotly.express as px
import streamlit as st

# Configure page
st.set_page_config(
    page_title="Enterprise RDARR Platform",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_data
def load_data():
    with open("config.yaml", "r") as f:
        config = yaml.safe_load(f)

    parquet_path = Path(config["paths"]["aggregated_output"])
    dq_path = Path(config["paths"]["quality_report"])
    lineage_path = Path(config["paths"]["lineage_log"])
    entities_path = Path(config["paths"]["reference_dir"]) / "legal_entities.csv"

    df_agg = pd.read_parquet(parquet_path) if parquet_path.exists() else pd.DataFrame()
    df_entities = pd.read_csv(entities_path) if entities_path.exists() else pd.DataFrame()

    dq_report = {}
    if dq_path.exists():
        with open(dq_path, "r") as f:
            dq_report = json.load(f)

    lineage = []
    if lineage_path.exists():
        with open(lineage_path, "r") as f:
            lineage = json.load(f)

    return config, df_agg, df_entities, dq_report, lineage


config, df_agg, df_entities, dq_report, lineage = load_data()

# ==============================================================================
# Header & Navigation
# ==============================================================================
st.title("Enterprise RDARR Platform")
st.caption("Aligned with BCBS 239: Principles for Effective Risk Data Aggregation & Risk Reporting")
st.markdown("---")

# Sidebar Filters
st.sidebar.header("Filter Exposures")
selected_entities = st.sidebar.multiselect(
    "Legal Entity",
    options=df_agg["legal_entity"].unique(),
    default=df_agg["legal_entity"].unique(),
)

selected_bus = st.sidebar.multiselect(
    "Business Unit",
    options=df_agg["business_unit"].unique(),
    default=df_agg["business_unit"].unique(),
)

df_filtered = df_agg[
    (df_agg["legal_entity"].isin(selected_entities)) &
    (df_agg["business_unit"].isin(selected_bus))
]

# Tabs for BCBS 239 Pillars
tab1, tab2, tab3 = st.tabs([
    "Executive Risk Appetite (Principles 4 & 8)",
    "Data Quality Engine (Principle 3)",
    "Audit & Lineage Provenance (Principle 2)",
])

# ==============================================================================
# TAB 1: Risk Appetite & Exposure Monitoring
# ==============================================================================
with tab1:
    st.subheader("Group-Wide Exposure & Limit Monitoring")

    total_exposure = df_filtered["total_exposure_usd"].sum()
    total_rwa = df_filtered["total_rwa_usd"].sum()
    total_loans = df_filtered["total_loans"].sum()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Group Exposure", f"${total_exposure:,.0f}")
    col2.metric("Total RWA (Basel III)", f"${total_rwa:,.0f}")
    col3.metric("Total Active Loans", f"{total_loans:,}")

    warning_th = config["reporting"]["breach_warning_pct"]
    crit_th = config["reporting"]["breach_critical_pct"]

    entity_rollup = df_filtered.groupby(["legal_entity", "legal_name", "exposure_limit_usd"]).agg(
        exposure=("total_exposure_usd", "sum"),
        rwa=("total_rwa_usd", "sum"),
        loans=("total_loans", "sum"),
    ).reset_index()

    entity_rollup["utilization_pct"] = (entity_rollup["exposure"] / entity_rollup["exposure_limit_usd"]) * 100

    def get_status(pct):
        if pct >= crit_th:
            return "BREACH (RED)"
        if pct >= warning_th:
            return "WARNING (AMBER)"
        return "NORMAL (GREEN)"

    entity_rollup["status"] = entity_rollup["utilization_pct"].apply(get_status)

    breaches_count = int((entity_rollup["status"] == "BREACH (RED)").sum())
    col4.metric("Active Limit Breaches", f"{breaches_count} Entities")

    st.markdown("#### Legal Entity Risk Limits & Status")
    st.dataframe(
        entity_rollup[[
            "legal_entity", "legal_name", "exposure", "exposure_limit_usd", "utilization_pct", "status"
        ]].rename(columns={
            "legal_entity": "Entity ID",
            "legal_name": "Entity Name",
            "exposure": "Exposure (USD)",
            "exposure_limit_usd": "Appetite Limit (USD)",
            "utilization_pct": "Utilization (%)",
            "status": "Risk Status"
        }).style.format({
            "Exposure (USD)": "${:,.2f}",
            "Appetite Limit (USD)": "${:,.2f}",
            "Utilization (%)": "{:.2f}%"
        }),
        width="stretch"
    )

    ch_col1, ch_col2 = st.columns(2)
    with ch_col1:
        fig_bu = px.bar(
            df_filtered,
            x="business_unit",
            y="total_exposure_usd",
            color="risk_tier",
            title="Exposure by Business Unit & Credit Tier",
            labels={"total_exposure_usd": "Exposure ($)", "business_unit": "Business Unit"},
            barmode="stack",
        )
        st.plotly_chart(fig_bu, width="stretch")

    with ch_col2:
        fig_pie = px.pie(
            df_filtered,
            values="total_exposure_usd",
            names="legal_entity",
            title="Exposure Concentration by Legal Entity",
            hole=0.4,
        )
        st.plotly_chart(fig_pie, width="stretch")

# ==============================================================================
# TAB 2: Data Quality Engine (BCBS 239 Principle 3)
# ==============================================================================
with tab2:
    st.subheader("Automated Data Quality & Governance Controls")

    if dq_report:
        q1, q2, q3, q4 = st.columns(4)
        q1.metric("DQ Health Score", f"{dq_report.get('dq_health_score_pct', 0)}%")
        q2.metric("Rules Evaluated", dq_report.get("total_rules_evaluated", 0))
        q3.metric("Passed Checks", dq_report.get("rules_passed", 0))
        q4.metric("Status", dq_report.get("overall_status", "UNKNOWN"))

        st.markdown("#### Automated Validation Check Matrix")
        df_checks = pd.DataFrame(dq_report.get("rule_details", []))
        st.dataframe(df_checks, width="stretch")
    else:
        st.warning("No Data Quality report found. Run data_quality_checker.py first.")

# ==============================================================================
# TAB 3: Data Lineage & Audit Trail (BCBS 239 Principle 2)
# ==============================================================================
with tab3:
    st.subheader("Data Lineage & Provenance Log")
    st.info("Demonstrates field-level origin, processing steps, and tamper-detection hashes (BCBS 239 Principle 2).")

    if lineage:
        for entry in reversed(lineage):
            with st.expander(f"Stage: {entry.get('pipeline_stage', 'UNKNOWN')} — {entry.get('timestamp_utc', '')}"):
                st.json(entry)
    else:
        st.warning("No lineage records found. Run the ingestion pipeline first.")