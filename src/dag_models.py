"""
Fit the same regression under competing DAG-implied adjustment sets.

This is the second half of the project. The question is not "which model fits
best" -- a DAG is not chosen by fit statistics. Each adjustment set follows
from a different belief about what causes what, and the point is to show how
much the estimated effect moves when that belief changes.

Important: comparing R-squared across these models would be a category error.
A model that adjusts for a mediator will often fit better while estimating
something you did not want. Fit is not evidence about causal structure.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import ADJUSTMENT_SETS  # noqa: E402

# Variables that should enter the model as categories rather than numbers.
CATEGORICAL = {"sex", "race_eth", "education"}


def build_formula(outcome: str, exposure: str, adjust: list[str]) -> str:
    """Write a patsy formula, wrapping categorical covariates in C()."""
    terms = [exposure if exposure not in CATEGORICAL else f"C({exposure})"]
    for var in adjust:
        if var == exposure:
            continue
        terms.append(f"C({var})" if var in CATEGORICAL else var)
    return f"{outcome} ~ " + " + ".join(terms)


def fit_one(
    df: pd.DataFrame,
    outcome: str,
    exposure: str,
    adjust: list[str],
    weight: str = "weight_pfas",
    strata: str = "strata",
    psu: str = "psu",
    design_based: bool = True,
):
    """
    Fit one weighted regression.

    Point estimates use the survey weights. Standard errors are clustered on
    PSU within stratum, which accounts for the within-cluster correlation that
    makes naive SEs too small. This is slightly conservative compared with full
    Taylor linearization because it does not take credit for stratification --
    state that limitation rather than hiding it.
    """
    needed = [outcome, exposure, weight, strata, psu] + list(adjust)
    needed = [c for c in dict.fromkeys(needed) if c in df.columns]
    sub = df[needed].dropna()
    sub = sub[sub[weight] > 0]

    missing = [c for c in adjust if c not in df.columns]
    if missing:
        raise KeyError(
            f"Adjustment set names columns that are not in the data: {missing}. "
            "Either merge the file that supplies them or drop them from the set."
        )

    formula = build_formula(outcome, exposure, adjust)

    if design_based:
        cluster = (
            sub[strata].astype(str) + "_" + sub[psu].astype(str)
        ).to_numpy()
        model = smf.wls(formula, data=sub, weights=sub[weight])
        result = model.fit(cov_type="cluster", cov_kwds={"groups": cluster})
    else:
        model = smf.wls(formula, data=sub, weights=sub[weight])
        result = model.fit()

    return result, sub, formula


def compare_dags(
    df: pd.DataFrame,
    outcome: str = "log_pfos",
    exposure: str = "income_poverty",
    adjustment_sets: dict[str, list[str]] | None = None,
    weight: str = "weight_pfas",
    **kwargs,
) -> pd.DataFrame:
    """
    Fit every adjustment set and tabulate the exposure coefficient.

    Returns one row per DAG with the estimate, interval, and a flag for
    whether the interval excludes zero -- which is the thing that may or may
    not flip across structures.

    Because the outcome is log-transformed, the coefficient is a difference in
    log concentration per unit of exposure. Exponentiating gives the
    multiplicative change, which is easier to talk about: exp(b) = 0.95 means
    each one-unit increase in the income-to-poverty ratio is associated with a
    5% lower geometric mean concentration.
    """
    sets = adjustment_sets or ADJUSTMENT_SETS
    rows = []

    for name, adjust in sets.items():
        try:
            result, sub, formula = fit_one(
                df, outcome, exposure, adjust, weight=weight, **kwargs
            )
        except KeyError as exc:
            print(f"  skipping {name}: {exc}")
            continue

        key = exposure if exposure not in CATEGORICAL else None
        if key is None or key not in result.params.index:
            print(f"  skipping {name}: no single coefficient for {exposure}")
            continue

        beta = result.params[key]
        se = result.bse[key]
        low, high = result.conf_int().loc[key]

        rows.append(
            {
                "dag": name,
                "adjusted_for": ", ".join(adjust) if adjust else "(nothing)",
                "n": int(result.nobs),
                "beta": beta,
                "se": se,
                "ci_low": low,
                "ci_high": high,
                "pct_change_per_unit": 100 * (np.exp(beta) - 1),
                "excludes_zero": bool(low > 0 or high < 0),
                "formula": formula,
            }
        )

    out = pd.DataFrame(rows)
    if len(out) > 1:
        # How far apart are the extremes? This number is the headline.
        spread = out["beta"].max() - out["beta"].min()
        print(
            f"\n  Spread across structures: {spread:.4f} on the log scale "
            f"({100 * (np.exp(spread) - 1):.1f}% difference in the "
            f"multiplicative effect)"
        )
        if out["excludes_zero"].nunique() > 1:
            print(
                "  NOTE: statistical significance is NOT consistent across "
                "structures -- this is your key result."
            )
    return out


def table_two_fallacy_demo(
    df: pd.DataFrame,
    outcome: str = "log_pfos",
    exposure: str = "income_poverty",
    adjust: list[str] | None = None,
    weight: str = "weight_pfas",
    **kwargs,
) -> pd.DataFrame:
    """
    Show every coefficient from one model, which is what papers print.

    The adjustment set here was chosen to estimate the effect of the exposure.
    It is generally the wrong set for interpreting any other coefficient in the
    same model, because each covariate has its own confounding structure. That
    mistake is common enough to have a name: the Table 2 fallacy.

    Print this alongside the exposure estimate and point out that only one row
    of the table is interpretable as the thing you set out to measure.
    """
    adjust = adjust or ADJUSTMENT_SETS["A_ses_proximal"]
    result, sub, formula = fit_one(
        df, outcome, exposure, adjust, weight=weight, **kwargs
    )
    out = pd.DataFrame(
        {
            "term": result.params.index,
            "beta": result.params.to_numpy(),
            "se": result.bse.to_numpy(),
            "ci_low": result.conf_int()[0].to_numpy(),
            "ci_high": result.conf_int()[1].to_numpy(),
        }
    )
    out["interpretable_as_causal"] = out["term"] == exposure
    return out
