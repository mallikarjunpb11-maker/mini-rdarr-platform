"""
BCBS 239 Principle 3: Data Integrity & Automated Data Quality Engine
Performs automated controls across 4 primary regulatory dimensions:
  1. Completeness: Missing values in Critical Data Elements (CDEs)
  2. Validity: Adherence to permitted domains (allowed grades, terms)
  3. Integrity: Numeric bounds check (loan amount caps and floors)
  4. Consistency: Unique identifier verification (no duplicate loans)
Outputs an auditable DQ summary report and updates lineage.
"""

import json
import yaml
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd


def load_config(config_path: str = "config.yaml") -> dict:
    """Load enterprise parameters and quality thresholds from central YAML."""
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def run_data_quality_checks():
    config = load_config()

    processed_dir = Path(config["paths"]["processed_dir"])
    enriched_file = processed_dir / "loans_enriched.csv"
    dq_report_path = Path(config["paths"]["quality_report"])
    lineage_log_path = Path(config["paths"]["lineage_log"])

    if not enriched_file.exists():
        raise FileNotFoundError(f"Enriched file not found at {enriched_file}. Run ingestion first!")

    df = pd.read_csv(enriched_file)
    total_records = len(df)

    print("=" * 65)
    print(" [BCBS 239] AUTOMATED DATA QUALITY ENGINE STARTED")
    print("=" * 65)
    print(f" Validating: {enriched_file} ({total_records:,} records)")

    dq_rules = config["data_quality"]
    cdes = dq_rules["critical_data_elements"]
    thresholds = dq_rules["thresholds"]

    results = []

    # --------------------------------------------------------------------------
    # Check 1: Completeness (Missing values on Critical Data Elements)
    # --------------------------------------------------------------------------
    for col in cdes:
        if col in df.columns:
            missing_count = int(df[col].isna().sum())
            missing_pct = round((missing_count / total_records) * 100, 2)
            passed = missing_pct <= thresholds["max_missing_pct"]
            results.append({
                "dimension": "Completeness",
                "check_name": f"Missingness: {col}",
                "metric_value": f"{missing_pct}% ({missing_count} rows)",
                "threshold": f"<= {thresholds['max_missing_pct']}%",
                "status": "PASSED" if passed else "FAILED"
            })
        else:
            results.append({
                "dimension": "Completeness",
                "check_name": f"Presence: {col}",
                "metric_value": "Column missing from dataset",
                "threshold": "Column must exist",
                "status": "FAILED"
            })

    # --------------------------------------------------------------------------
    # Check 2: Uniqueness / Record Integrity (Duplicate Loan IDs)
    # --------------------------------------------------------------------------
    dup_count = int(df["loan_id"].duplicated().sum()) if "loan_id" in df.columns else 0
    results.append({
        "dimension": "Uniqueness",
        "check_name": "Unique Loan Identifier",
        "metric_value": f"{dup_count} duplicates",
        "threshold": "0 duplicates",
        "status": "PASSED" if dup_count == 0 else "FAILED"
    })

    # --------------------------------------------------------------------------
    # Check 3: Domain Validity (Permitted Credit Grades)
    # --------------------------------------------------------------------------
    allowed_grades = thresholds["allowed_grades"]
    invalid_grades = int((~df["grade"].isin(allowed_grades)).sum())
    results.append({
        "dimension": "Validity",
        "check_name": "Permitted Credit Grades (A-G)",
        "metric_value": f"{invalid_grades} invalid grades",
        "threshold": "0 invalid",
        "status": "PASSED" if invalid_grades == 0 else "FAILED"
    })

    # --------------------------------------------------------------------------
    # Check 4: Range Integrity (Min & Max Loan Amount)
    # --------------------------------------------------------------------------
    min_cap = thresholds["min_loan_amount"]
    max_cap = thresholds["max_loan_amount"]
    out_of_bounds = int(((df["loan_amnt"] < min_cap) | (df["loan_amnt"] > max_cap)).sum())
    results.append({
        "dimension": "Integrity",
        "check_name": f"Loan Amount Boundaries (${min_cap:,.0f} - ${max_cap:,.0f})",
        "metric_value": f"{out_of_bounds} outliers",
        "threshold": "0 out of bounds",
        "status": "PASSED" if out_of_bounds == 0 else "FAILED"
    })

    # --------------------------------------------------------------------------
    # Scoring & Audit Summary
    # --------------------------------------------------------------------------
    total_checks = len(results)
    passed_checks = sum(1 for r in results if r["status"] == "PASSED")
    dq_health_score = round((passed_checks / total_checks) * 100, 1)

    dq_report = {
        "report_id": f"DQR_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "source_dataset": str(enriched_file),
        "total_records_evaluated": total_records,
        "total_rules_evaluated": total_checks,
        "rules_passed": passed_checks,
        "rules_failed": total_checks - passed_checks,
        "dq_health_score_pct": dq_health_score,
        "overall_status": "COMPLIANT" if dq_health_score >= 80.0 else "NON_COMPLIANT",
        "rule_details": results
    }

    # Save DQ report
    with open(dq_report_path, "w") as f:
        json.dump(dq_report, f, indent=2)

    print(f" Data Quality Report generated: {dq_report_path}")
    print(f" Overall DQ Health Score: {dq_health_score}% ({passed_checks}/{total_checks} passed)")

    # Print summary table to terminal
    print("-" * 65)
    print(f"{'Check Name':<35} | {'Metric':<15} | {'Status':<8}")
    print("-" * 65)
    for r in results:
        print(f"{r['check_name']:<35} | {r['metric_value']:<15} | {r['status']:<8}")
    print("-" * 65)

    # --------------------------------------------------------------------------
    # Update Audit Lineage (BCBS 239 Principle 2)
    # --------------------------------------------------------------------------
    lineage_record = {
        "pipeline_stage": "DATA_QUALITY_VERIFICATION",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "input_file": str(enriched_file),
        "dq_report": str(dq_report_path),
        "dq_health_score_pct": dq_health_score,
        "status": dq_report["overall_status"]
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

    print(f" Lineage log updated at: {lineage_log_path}")
    print("=" * 65)


if __name__ == "__main__":
    run_data_quality_checks()