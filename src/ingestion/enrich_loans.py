"""
Enterprise Risk Data Enrichment & Ingestion Engine
Framework Alignment:
  - BCBS 239 Principle 2: Data Architecture & Lineage
  - BCBS 239 Principle 4: Group-wide Risk Aggregation & Completeness

Function:
  Loads raw lending data, enriches each record with banking legal entities,
  business units, risk categories, and reference rating metrics,
  then records audit provenance.
"""

import os
import json
import yaml
import hashlib
from datetime import datetime
from pathlib import Path
import pandas as pd
import numpy as np


def load_config(config_path: str = "config.yaml") -> dict:
    """Load enterprise parameters from the central configuration."""
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def calculate_file_hash(file_path: str) -> str:
    """Generate SHA-256 hash for raw data tamper verification (Audit requirement)."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def enrich_and_ingest():
    config = load_config()

    raw_file = Path(config["paths"]["raw_data"])
    reference_dir = Path(config["paths"]["reference_dir"])
    processed_dir = Path(config["paths"]["processed_dir"])
    lineage_log_path = Path(config["paths"]["lineage_log"])

    processed_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 65)
    print(" [BCBS 239] INGESTION & RISK ENRICHMENT ENGINE STARTED")
    print("=" * 65)

    # 1. Ingest Raw Lending Club Data
    if not raw_file.exists():
        raise FileNotFoundError(f"Raw file not found at {raw_file}. Run raw generator first!")

    df_raw = pd.read_csv(raw_file)
    raw_hash = calculate_file_hash(str(raw_file))
    print(f" Loaded Raw Loans: {len(df_raw):,} records from {raw_file}")
    print(f" Raw File Integrity Hash (SHA-256): {raw_hash[:16]}...")

    # 2. Ingest Reference Data (Rating Grades & Capital Weights)
    grades_file = reference_dir / "rating_grades.csv"
    if not grades_file.exists():
        raise FileNotFoundError(f"Rating grades reference file not found at {grades_file}")
    
    df_grades = pd.read_csv(grades_file)
    print(f" Loaded Reference Data: {len(df_grades)} rating tiers from {grades_file}")

    # 3. Enterprise Dimension Assignment (Deterministic by loan ID)
    # Realistic distribution across the 3 legal entities
    entities = [e["code"] for e in config["legal_entities"]]
    entity_probs = [0.45, 0.35, 0.20]  # LE_01 receives highest volume to test limit breach

    business_units = config["business_units"]
    bu_probs = [0.60, 0.25, 0.15]

    np.random.seed(101)  # Fixed seed ensures deterministic audit reproducibility
    n_loans = len(df_raw)

    df_enriched = df_raw.copy()
    df_enriched["legal_entity"] = np.random.choice(entities, size=n_loans, p=entity_probs)
    df_enriched["business_unit"] = np.random.choice(business_units, size=n_loans, p=bu_probs)
    df_enriched["risk_category"] = "Credit Risk"
    df_enriched["source_system"] = "SRC_CORE_LOAN"
    df_enriched["ingested_at"] = datetime.utcnow().isoformat() + "Z"

    # Standardize column naming
    if "id" in df_enriched.columns:
        df_enriched.rename(columns={"id": "loan_id"}, inplace=True)

    # 4. Join Reference Data (BCBS 239 Principle 4: Enrichment with Capital Weights)
    df_enriched = df_enriched.merge(
        df_grades[["grade", "risk_tier", "credit_quality", "capital_weight_pct"]],
        on="grade",
        how="left"
    )

    # Calculate Risk-Weighted Exposure (RWA = loan_amount * capital_weight)
    df_enriched["capital_weight_pct"] = df_enriched["capital_weight_pct"].fillna(100.0)
    df_enriched["risk_weighted_exposure"] = (
        df_enriched["loan_amnt"] * (df_enriched["capital_weight_pct"] / 100.0)
    ).round(2)

    # 5. Save Enriched Dataset to processed/
    output_enriched_csv = processed_dir / "loans_enriched.csv"
    df_enriched.to_csv(output_enriched_csv, index=False)
    print(f" Enriched loans saved to: {output_enriched_csv}")

    # 6. Record Audit Lineage Metadata (BCBS 239 Principle 2)
    lineage_record = {
        "pipeline_stage": "INGESTION_AND_ENRICHMENT",
        "timestamp_utc": datetime.utcnow().isoformat() + "Z",
        "source_file": str(raw_file),
        "source_sha256": raw_hash,
        "records_read": len(df_raw),
        "records_written": len(df_enriched),
        "total_exposure_usd": float(df_enriched["loan_amnt"].sum()),
        "total_risk_weighted_exposure_usd": float(df_enriched["risk_weighted_exposure"].sum()),
        "output_file": str(output_enriched_csv),
        "status": "SUCCESS"
    }

    with open(lineage_log_path, "w") as f:
        json.dump([lineage_record], f, indent=2)

    print(f" Lineage audit record logged to: {lineage_log_path}")
    print("=" * 65)
    print(" SUMMARY OF ENRICHED PORTFOLIO:")
    print(df_enriched.groupby("legal_entity")["loan_amnt"].agg(["count", "sum"]).rename(columns={"count": "Loans", "sum": "Exposure ($)"}))
    print("=" * 65)


if __name__ == "__main__":
    enrich_and_ingest()