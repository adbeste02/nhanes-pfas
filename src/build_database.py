"""
Read the raw .XPT files, merge them on SEQN, and load the result into SQLite.

Run from the project root:
    python src/build_database.py

Produces data/nhanes.db with two tables:
    raw_demo, raw_pfas   -- one row per participant, as downloaded
    analysis             -- the merged analytic sample

Design philosophy: do the joins in SQL-friendly form and keep the raw tables
around, so you can always trace a number back to the file it came from.
"""

import sqlite3
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import (  # noqa: E402
    ANALYTES,
    COVARIATES,
    DESIGN,
    FILES,
    MIN_AGE,
    MISSING_CODES,
    WEIGHT_PFAS,
)

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
DB_PATH = ROOT / "data" / "nhanes.db"


def read_xpt(key: str) -> pd.DataFrame:
    """Read one NHANES SAS transport file into a DataFrame."""
    path = RAW_DIR / FILES[key]
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. Run `python src/download_data.py` first."
        )
    df = pd.read_sas(path, format="xport")
    # SEQN comes back as a float; make it an integer key.
    df["SEQN"] = df["SEQN"].astype("int64")
    print(f"  {FILES[key]}: {len(df):,} rows, {len(df.columns)} columns")
    return df


def check_columns(df: pd.DataFrame, needed: dict, label: str) -> None:
    """Warn loudly about variable names that don't exist in this cycle."""
    missing = {k: v for k, v in needed.items() if v not in df.columns}
    if missing:
        print(f"\n  !! {label}: these config variables are not in the file:")
        for name, var in missing.items():
            print(f"       {name} -> {var}")
        print("     Check the codebook for this cycle; names change between cycles.")
        print(f"     Available columns: {sorted(df.columns)}\n")


def build_analysis_table(demo: pd.DataFrame, pfas: pd.DataFrame) -> pd.DataFrame:
    """Merge demographics and PFAS, rename to readable names, filter to adults."""
    # Keep only the columns we need, so the analysis table stays legible.
    demo_vars = ["SEQN"] + list(DESIGN.values()) + list(COVARIATES.values())
    demo_vars = [v for v in demo_vars if v in demo.columns]

    pfas_vars = ["SEQN"]
    if WEIGHT_PFAS in pfas.columns:
        pfas_vars.append(WEIGHT_PFAS)
    for result_var, comment_var in ANALYTES.values():
        pfas_vars += [v for v in (result_var, comment_var) if v in pfas.columns]

    # Inner join: the PFAS subsample is a fraction of the full sample, and an
    # analysis of PFAS can only use people who have a PFAS measurement.
    merged = demo[demo_vars].merge(pfas[pfas_vars], on="SEQN", how="inner")
    print(f"  merged on SEQN: {len(merged):,} rows (PFAS subsample)")

    # Readable names for the covariates; analyte columns keep NHANES names so
    # they stay traceable to the codebook.
    rename = {var: name for name, var in COVARIATES.items() if var in merged.columns}
    rename.update({var: name for name, var in DESIGN.items() if var in merged.columns})
    if WEIGHT_PFAS in merged.columns:
        rename[WEIGHT_PFAS] = "weight_pfas"
    merged = merged.rename(columns=rename)

    # Replace refused/don't-know codes with missing.
    for var, codes in MISSING_CODES.items():
        name = rename.get(var, var)
        if name in merged.columns:
            n_before = merged[name].isna().sum()
            merged[name] = merged[name].replace(codes, pd.NA)
            print(
                f"  {name}: set {merged[name].isna().sum() - n_before:,} "
                f"refused/unknown values to missing"
            )

    # Restrict to adults. Education is only collected for ages 20+.
    if "age" in merged.columns:
        before = len(merged)
        merged = merged[merged["age"] >= MIN_AGE]
        print(f"  age >= {MIN_AGE}: {before:,} -> {len(merged):,} rows")

    return merged.reset_index(drop=True)


def report_detection_rates(df: pd.DataFrame) -> pd.DataFrame:
    """
    Detection rates per analyte. This decides whether the limit-of-detection
    comparison is worth doing: an analyte detected in 99% of samples will not
    show interesting sensitivity to substitution rules.
    """
    rows = []
    for name, (result_var, comment_var) in ANALYTES.items():
        if result_var not in df.columns:
            continue
        n_measured = df[result_var].notna().sum()
        row = {"analyte": name, "variable": result_var, "n_measured": int(n_measured)}
        if comment_var in df.columns:
            # Comment code 1 conventionally means "below LOD" -- verify this.
            below = (df[comment_var] == 1).sum()
            row["n_below_lod"] = int(below)
            row["pct_below_lod"] = round(100 * below / n_measured, 1) if n_measured else None
        rows.append(row)
    return pd.DataFrame(rows)


def main() -> None:
    print("Reading raw files:")
    demo = read_xpt("demo")
    pfas = read_xpt("pfas")

    check_columns(demo, {**DESIGN, **COVARIATES}, "DEMO")
    check_columns(pfas, {"weight_pfas": WEIGHT_PFAS}, "PFAS")

    print("\nBuilding analysis table:")
    analysis = build_analysis_table(demo, pfas)

    print("\nDetection rates:")
    detection = report_detection_rates(analysis)
    print(detection.to_string(index=False))

    print(f"\nWriting {DB_PATH}")
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        demo.to_sql("raw_demo", conn, if_exists="replace", index=False)
        pfas.to_sql("raw_pfas", conn, if_exists="replace", index=False)
        analysis.to_sql("analysis", conn, if_exists="replace", index=False)
        detection.to_sql("detection_rates", conn, if_exists="replace", index=False)
    print(f"  wrote {len(analysis):,} rows to table `analysis`")
    print("\nDone. Open with: sqlite3 data/nhanes.db")


if __name__ == "__main__":
    main()
