"""
Lending Club Raw Data Generator
Simulates the raw extraction from Core Loan Origination System (SRC_CORE_LOAN)
with authentic Lending Club schema, realistic distributions, and intentional edge cases
for automated BCBS 239 Data Quality testing.
"""

import numpy as np
import pandas as pd
from pathlib import Path

# Fix random seed for exact reproducibility across environments
np.random.seed(42)

NUM_LOANS = 1200

# 1. Generate realistic loan IDs
loan_ids = [f"LC_{100000 + i}" for i in range(NUM_LOANS)]

# 2. Loan amounts (Lending Club range: $1,000 to $40,000)
# Most unsecured loans cluster between $5,000 and $25,000
loan_amounts = np.random.choice(
    [3000, 5000, 7500, 10000, 12000, 15000, 20000, 25000, 30000, 35000, 40000],
    size=NUM_LOANS,
    p=[0.05, 0.10, 0.10, 0.15, 0.15, 0.15, 0.12, 0.08, 0.05, 0.03, 0.02]
).astype(float)

# 3. Loan Term: 36 months (70%) vs 60 months (30%)
terms = np.random.choice(["36 months", "60 months"], size=NUM_LOANS, p=[0.70, 0.30])

# 4. Lending Club Grades (A through G)
grades = np.random.choice(
    ["A", "B", "C", "D", "E", "F", "G"],
    size=NUM_LOANS,
    p=[0.18, 0.28, 0.25, 0.15, 0.08, 0.04, 0.02]
)

# 5. Base Interest Rates tied realistically to grades
grade_rate_map = {
    "A": (5.5, 8.5),
    "B": (8.6, 12.0),
    "C": (12.1, 15.5),
    "D": (15.6, 19.5),
    "E": (19.6, 24.0),
    "F": (24.1, 28.0),
    "G": (28.1, 31.0)
}
int_rates = [
    round(np.random.uniform(grade_rate_map[g][0], grade_rate_map[g][1]), 2)
    for g in grades
]

# 6. Borrower Employment Length
emp_lengths = np.random.choice(
    ["< 1 year", "1 year", "2 years", "3 years", "5 years", "10+ years"],
    size=NUM_LOANS,
    p=[0.10, 0.08, 0.12, 0.15, 0.20, 0.35]
)

# 7. Annual Income (Log-normal distribution around $65,000)
annual_incomes = np.round(np.random.lognormal(mean=11.0, sigma=0.45, size=NUM_LOANS), -2)

# 8. Loan Purpose
purposes = np.random.choice(
    ["debt_consolidation", "credit_card", "home_improvement", "major_purchase", "small_business"],
    size=NUM_LOANS,
    p=[0.55, 0.22, 0.10, 0.08, 0.05]
)

# 9. Loan Status
loan_statuses = np.random.choice(
    ["Current", "Fully Paid", "Charged Off", "Late (31-120 days)"],
    size=NUM_LOANS,
    p=[0.72, 0.18, 0.07, 0.03]
)

# Construct raw DataFrame
df = pd.DataFrame({
    "id": loan_ids,
    "loan_amnt": loan_amounts,
    "term": terms,
    "int_rate": int_rates,
    "grade": grades,
    "emp_length": emp_lengths,
    "annual_inc": annual_incomes,
    "purpose": purposes,
    "loan_status": loan_statuses,
    "issue_d": "2024-03-01"
})

# ==============================================================================
# Inject Realistic Data Quality Defects (For BCBS 239 DQ Validation Testing)
# ==============================================================================
# Inject a tiny percentage (~1.5%) of missing values in non-critical / critical fields
null_indices_inc = np.random.choice(df.index, size=15, replace=False)
df.loc[null_indices_inc, "annual_inc"] = np.nan

null_indices_rate = np.random.choice(df.index, size=10, replace=False)
df.loc[null_indices_rate, "int_rate"] = np.nan

# Ensure target folder exists
output_dir = Path("data/raw")
output_dir.mkdir(parents=True, exist_ok=True)

output_file = output_dir / "lending_club_sample.csv"
df.to_csv(output_file, index=False)

print(f" Successfully generated raw dataset: {output_file}")
print(f" Total records: {len(df):,}")
print(f" Total portfolio loan volume: ${df['loan_amnt'].sum():,.2f}")