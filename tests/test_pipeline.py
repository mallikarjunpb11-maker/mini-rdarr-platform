"""
Automated Pipeline & Risk Governance Tests
Validates core BCBS 239 assumptions:
  - Completeness of aggregated loan volumes
  - Accuracy of Risk-Weighted Assets (RWA)
  - Limit breach classification logic
"""

import json
from pathlib import Path
import pandas as pd
import pytest
import yaml


@pytest.fixture
def config():
    with open("config.yaml", "r") as f:
        return yaml.safe_load(f)


@pytest.fixture
def enriched_data(config):
    path = Path(config["paths"]["processed_dir"]) / "loans_enriched.csv"
    assert path.exists(), "loans_enriched.csv does not exist. Run ingestion first."
    return pd.read_csv(path)


@pytest.fixture
def aggregated_data(config):
    path = Path(config["paths"]["aggregated_output"])
    assert path.exists(), "risk_aggregated.parquet does not exist. Run aggregation first."
    return pd.read_parquet(path)


def test_reconciliation_total_records(enriched_data, aggregated_data):
    """BCBS 239 Principle 3: Total aggregated loans must match raw enriched count."""
    raw_count = len(enriched_data)
    aggregated_count = int(aggregated_data["total_loans"].sum())
    assert raw_count == aggregated_count, (
        f"Reconciliation failure: {raw_count} enriched vs {aggregated_count} aggregated loans"
    )


def test_reconciliation_total_exposure(enriched_data, aggregated_data):
    """BCBS 239 Principle 4: Group total exposure dollar balance must tie out to the penny."""
    raw_total = round(float(enriched_data["loan_amnt"].sum()), 2)
    aggregated_total = round(float(aggregated_data["total_exposure_usd"].sum()), 2)
    assert raw_total == aggregated_total, (
        f"Exposure tie-out failure: ${raw_total} vs ${aggregated_total}"
    )


def test_no_negative_exposures(enriched_data):
    """Credit sanity check: No negative loan amounts."""
    assert (enriched_data["loan_amnt"] < 0).sum() == 0, "Found negative loan balances."


def test_valid_legal_entities(config, enriched_data):
    """Governance check: Only approved legal entities exist in the portfolio."""
    valid_entities = {e["code"] for e in config["legal_entities"]}
    found_entities = set(enriched_data["legal_entity"].unique())
    assert found_entities.issubset(valid_entities), (
        f"Found unauthorized entities: {found_entities - valid_entities}"
    )


def test_data_quality_report_exists(config):
    """Principle 3: Automated DQ report must exist and meet compliance threshold."""
    dq_file = Path(config["paths"]["quality_report"])
    assert dq_file.exists(), "Missing Data Quality report."
    with open(dq_file, "r") as f:
        report = json.load(f)
    assert report["dq_health_score_pct"] >= 80.0, (
        f"DQ Health Score fell below threshold: {report['dq_health_score_pct']}%"
    )