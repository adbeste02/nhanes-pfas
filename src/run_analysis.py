"""
End-to-end analysis: weighting comparison, then DAG comparison.

Run from the project root, after download_data.py and build_database.py:
    python src/run_analysis.py

Writes CSV tables to output/ that you can paste straight into slides.
"""

import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import ANALYTES, PRIMARY_ANALYTE  # noqa: E402
from dag_models import compare_dags, table_two_fallacy_demo  # noqa: E402
from survey_stats import compare_methods  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "nhanes.db"
OUT_DIR = ROOT / "output"


def load() -> pd.DataFrame:
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"{DB_PATH} not found. Run `python src/build_database.py` first."
        )
    with sqlite3.connect(DB_PATH) as conn:
        df = pd.read_sql("SELECT * FROM analysis", conn)
    print(f"Loaded {len(df):,} rows from {DB_PATH.name}")
    return df


def prepare(df: pd.DataFrame) -> pd.DataFrame:
    """Add the log outcome and report what the analytic sample looks like."""
    result_var = ANALYTES[PRIMARY_ANALYTE][0]
    if result_var not in df.columns:
        raise KeyError(
            f"{result_var} not in the data. Check PRIMARY_ANALYTE and the "
            "variable names in config.py against the codebook."
        )

    df = df.copy()
    df["pfos"] = df[result_var]
    df = df[df["pfos"] > 0]
    df["log_pfos"] = np.log(df["pfos"])

    print(f"\nAnalytic sample: {len(df):,} adults with a PFOS measurement")
    print(f"  PFOS median {df['pfos'].median():.2f} ng/mL, "
          f"range {df['pfos'].min():.2f}-{df['pfos'].max():.2f}")
    print(f"  missing income_poverty: {df['income_poverty'].isna().sum():,}")
    return df


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    df = prepare(load())

    print("\n" + "=" * 70)
    print("PART 1 -- Does the survey design change the estimate?")
    print("=" * 70)
    weighting = compare_methods(df, "pfos")
    print(weighting[
        ["method", "estimate", "se", "ci_low", "ci_high", "n", "df", "deff_vs_naive"]
    ].to_string(index=False))
    weighting.to_csv(OUT_DIR / "weighting_comparison.csv", index=False)

    print("\nValidation step: compare the weighted, design-based geometric mean")
    print("against CDC's National Exposure Report table for this cycle and")
    print("analyte. If they do not match closely, stop and debug before going on.")

    print("\n" + "=" * 70)
    print("PART 2 -- Does the causal structure change the conclusion?")
    print("=" * 70)
    dags = compare_dags(df)
    if not dags.empty:
        print(dags[
            ["dag", "adjusted_for", "n", "beta", "ci_low", "ci_high",
             "pct_change_per_unit", "excludes_zero"]
        ].to_string(index=False))
        dags.to_csv(OUT_DIR / "dag_comparison.csv", index=False)

    print("\n" + "-" * 70)
    print("Table 2 fallacy: every coefficient from DAG A's model")
    print("-" * 70)
    t2 = table_two_fallacy_demo(df)
    print(t2.to_string(index=False))
    t2.to_csv(OUT_DIR / "table_two_fallacy.csv", index=False)

    print(f"\nTables written to {OUT_DIR}")


if __name__ == "__main__":
    main()
