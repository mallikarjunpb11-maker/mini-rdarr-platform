"""
BCBS 239 Principle 4 (Completeness) & Principle 8 (Comprehensiveness)
Risk Data Aggregation Engine

Function:
  - Uses DuckDB for in-memory analytical SQL processing.
  - Aggregates exposure across Legal Entities, Business Units, and Credit Tiers.
  - Computes limit utilization and flags:
      * GREEN (< 85% limit)
      * AMBER (85% - 99.9% limit - Warning)
      * RED (>= 100% limit - Breach Alert)
  - Exports aggregated exposures to Parquet and updates audit lineage.
"""

import json
import yaml
import duckdb
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd


def load_config(config_path: str = "config.yaml") -> dict:
    """Load configuration parameters."""
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def run_risk_aggregation():
    config = load_config()

    processed_dir = Path(config["paths"]["processed_dir"])
    reference_dir = Path(config["paths"]["reference_dir"])
    enriched_file = processed_dir / "loans_enriched.csv"
    entities_file = reference_dir / "legal_entities.csv"
    output_parquet = Path(config["paths"]["aggregated_output"])
    lineage_log_path = Path(config["paths"]["lineage_log"])

    if not enriched_file.exists():
        raise FileNotFoundError(f"Missing enriched dataset at {enriched_file}")
    if not entities_file.exists():
        raise FileNotFoundError(f"Missing legal entities reference at {entities_file}")

    print("=" * 70)
    print(" [BCBS 239] ENTERPRISE RISK DATA AGGREGATION ENGINE (DUCKDB)")
    print("=" * 70)

    # Initialize DuckDB in-process connection
    con = duckdb.connect(database=":memory:")

    # Register input files as analytical views
    con.execute(f"CREATE VIEW loans AS SELECT * FROM read_csv_auto('{enriched_file.as_posix()}');")
    con.execute(f"CREATE VIEW entities AS SELECT * FROM read_csv_auto('{entities_file.as_posix()}');")

    warning_threshold = config["reporting"]["breach_warning_pct"]
    critical_threshold = config["reporting"]["breach_critical_pct"]

    # Enterprise Aggregation Query across Legal Entity and Business Unit
    aggregation_sql = f"""
    SELECT 
        l.legal_entity,
        e.legal_name,
        e.jurisdiction,
        e.regulatory_regime,
        e.base_currency,
        e.exposure_limit_usd,
        l.business_unit,
        l.risk_tier,
        COUNT(l.loan_id) AS total_loans,
        ROUND(SUM(l.loan_amnt), 2) AS total_exposure_usd,
        ROUND(SUM(l.risk_weighted_exposure), 2) AS total_rwa_usd,
        ROUND(AVG(l.int_rate), 2) AS weighted_avg_rate_pct
    FROM loans l
    LEFT JOIN entities e ON l.legal_entity = e.entity_id
    GROUP BY 
        l.legal_entity,
        e.legal_name,
        e.jurisdiction,
        e.regulatory_regime,
        e.base_currency,
        e.exposure_limit_usd,
        l.business_unit,
        l.risk_tier
    ORDER BY l.legal_entity, l.business_unit, l.risk_tier;
    """

    df_aggregated = con.execute(aggregation_sql).df()

    # Rollup by Legal Entity to evaluate Board Risk Appetite Limits
    entity_rollup_sql = f"""
    SELECT 
        l.legal_entity,
        e.legal_name,
        e.jurisdiction,
        e.exposure_limit_usd,
        COUNT(l.loan_id) AS loan_count,
        ROUND(SUM(l.loan_amnt), 2) AS entity_exposure_usd,
        ROUND(SUM(l.risk_weighted_exposure), 2) AS entity_rwa_usd,
        ROUND((SUM(l.loan_amnt) / e.exposure_limit_usd) * 100, 2) AS limit_utilization_pct,
        CASE 
            WHEN (SUM(l.loan_amnt) / e.exposure_limit_usd) * 100 >= {critical_threshold} THEN 'BREACH (RED)'
            WHEN (SUM(l.loan_amnt) / e.exposure_limit_usd) * 100 >= {warning_threshold} THEN 'WARNING (AMBER)'
            ELSE 'NORMAL (GREEN)'
        END AS risk_status
    FROM loans l
    LEFT JOIN entities e ON l.legal_entity = e.entity_id
    GROUP BY l.legal_entity, e.legal_name, e.jurisdiction, e.exposure_limit_usd
    ORDER BY entity_exposure_usd DESC;
    """

    df_entity_summary = con.execute(entity_rollup_sql).df()

    # Save granular aggregated dataset to Parquet format
    output_parquet.parent.mkdir(parents=True, exist_ok=True)
    df_aggregated.to_parquet(output_parquet, index=False)
    print(f" Aggregated risk dataset exported to: {output_parquet}")

    # Display Executive Summary Table
    print("\n" + "=" * 70)
    print(" EXECUTIVE RISK APPETITE MONITORING REPORT (BCBS 239)")
    print("=" * 70)
    print(f"{'Entity':<8} | {'Exposure ($)':<14} | {'Limit ($)':<12} | {'Utilization':<11} | {'Status':<15}")
    print("-" * 70)
    for _, row in df_entity_summary.iterrows():
        print(
            f"{row['legal_entity']:<8} | "
            f"${row['entity_exposure_usd']:>12,.2f} | "
            f"${row['exposure_limit_usd']:>10,.2f} | "
            f"{row['limit_utilization_pct']:>9.2f}% | "
            f"{row['risk_status']:<15}"
        )
    print("=" * 70)

    # --------------------------------------------------------------------------
    # Update Audit Lineage (BCBS 239 Principle 2)
    # --------------------------------------------------------------------------
    lineage_record = {
        "pipeline_stage": "RISK_DATA_AGGREGATION",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "engine": "DuckDB (In-Memory SQL)",
        "input_dataset": str(enriched_file),
        "output_parquet": str(output_parquet),
        "total_aggregated_rows": len(df_aggregated),
        "entities_monitored": len(df_entity_summary),
        "breaches_detected": int((df_entity_summary["risk_status"] == "BREACH (RED)").sum()),
        "status": "SUCCESS"
    }

    existing_lineage = []
    if lineage_log_path.exists():
        with open(lineage_log_path, "r") as f:
            try:
                existing_lineage = json.load(f)
            except Exception:
                existing_lineage = []

    existing_lineage.append(lineage_record)
    with open(lineage_log_path, "w") as f:
        json.dump(existing_lineage, f, indent=2)

    print(f" Audit Lineage updated: {lineage_log_path}")


if __name__ == "__main__":
    run_risk_aggregation()