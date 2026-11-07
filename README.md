# Mini-RDARR Platform (BCBS 239 Risk Aggregation Engine)

An enterprise-aligned Credit Risk Aggregation and Data Governance platform built to implement core regulatory tenets of the **Basel Committee on Banking Supervision standard BCBS 239** (*Principles for Effective Risk Data Aggregation and Risk Reporting*).

---

## 🏛️ Regulatory Principles Implemented

| BCBS 239 Principle | Regulatory Requirement | Platform Implementation |
| :--- | :--- | :--- |
| **Principle 1: Governance** | Integrated risk appetite framework and limits | Centralized governance declared in `config.yaml` specifying board-level Risk Appetite Limits by legal entity. |
| **Principle 2: Data Architecture & Lineage** | Traceable provenance and source identification | Automated SHA-256 raw file hashing and end-to-end stage logging in `lineage_log.json`. |
| **Principle 3: Accuracy & Integrity** | Automated controls across critical data elements (CDEs) | Rule engine measuring Completeness, Domain Validity, and Numeric Range Integrity with an auditable DQ Health Score. |
| **Principle 4: Completeness** | Group-wide risk aggregation across entities and business lines | In-memory analytical SQL processing using **DuckDB** aggregating loans across legal entities, business units, and credit tiers. |
| **Principle 8: Comprehensiveness** | Forward-looking limit monitoring and breach escalation | Automated exposure threshold monitoring flagging **NORMAL (Green)**, **WARNING (Amber)**, and **BREACH (Red)** statuses. |

---

## 🛠️ Architecture & Tech Stack

```text
mini-rdarr-platform/
├── config.yaml                   # Central risk appetite, thresholds, and paths
├── data/
│   ├── raw/                      # Landing zone for loan extracts
│   ├── reference/                # Master legal entities and rating tier tables
│   └── processed/                # Enriched datasets, parquet aggregates, audit logs
├── src/
│   ├── ingestion/                # Ingestion, SHA-256 hashing, enterprise enrichment
│   ├── quality/                  # Automated BCBS 239 data quality validation engine
│   └── aggregation/              # In-memory DuckDB analytical SQL engine
├── dashboards/
│   └── app.py                    # Interactive Streamlit executive risk portal
└── tests/
    └── test_pipeline.py          # Automated reconciliation and governance tests