"""
Survey-weighted estimation with design-based standard errors.

NHANES is a stratified, multistage cluster sample, so two things go wrong if
you treat it as a simple random sample:

  1. Point estimates are biased, because some groups are oversampled on
     purpose. Weights fix this.
  2. Standard errors are too small, because people in the same cluster (PSU)
     resemble each other, so you have less independent information than your
     sample size suggests. Only accounting for strata and PSUs fixes this.

This module computes both the naive and the design-based versions so the two
can be compared -- which is the point of the first half of the project.

Variance is computed by Taylor-series linearization, which is the method CDC
uses in its own published analyses.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats


@dataclass
class Estimate:
    """One estimate with its uncertainty, plus how it was computed."""

    value: float
    se: float
    ci_low: float
    ci_high: float
    method: str
    n: int
    df: int | None = None

    def __str__(self) -> str:
        return (
            f"{self.value:.4g} (SE {self.se:.4g}, "
            f"95% CI {self.ci_low:.4g}-{self.ci_high:.4g}) "
            f"[{self.method}, n={self.n}]"
        )

    def as_dict(self) -> dict:
        return {
            "estimate": self.value,
            "se": self.se,
            "ci_low": self.ci_low,
            "ci_high": self.ci_high,
            "method": self.method,
            "n": self.n,
            "df": self.df,
        }


def _clean(
    df: pd.DataFrame, value: str, weight: str, strata: str | None, psu: str | None
) -> pd.DataFrame:
    """Drop rows missing anything the estimator needs, and zero-weight rows."""
    cols = [value, weight] + [c for c in (strata, psu) if c is not None]
    out = df[cols].dropna()
    out = out[out[weight] > 0]
    return out


def naive_mean(df: pd.DataFrame, value: str) -> Estimate:
    """Unweighted mean, treating the sample as if it were simple random."""
    y = df[value].dropna().to_numpy(dtype=float)
    n = len(y)
    mean = y.mean()
    se = y.std(ddof=1) / np.sqrt(n)
    crit = stats.t.ppf(0.975, n - 1)
    return Estimate(
        value=mean,
        se=se,
        ci_low=mean - crit * se,
        ci_high=mean + crit * se,
        method="unweighted, naive SE",
        n=n,
        df=n - 1,
    )


def weighted_mean_naive_se(df: pd.DataFrame, value: str, weight: str) -> Estimate:
    """
    Weighted mean with a standard error that ignores the clustered design.

    This is the middle case: the point estimate is correct for the population,
    but the uncertainty is understated. Included so the project can separate
    the effect of weighting from the effect of clustering.
    """
    sub = df[[value, weight]].dropna()
    sub = sub[sub[weight] > 0]
    y = sub[value].to_numpy(dtype=float)
    w = sub[weight].to_numpy(dtype=float)
    n = len(y)

    mean = np.sum(w * y) / np.sum(w)
    # Weighted variance of the mean, ignoring design structure.
    var = np.sum(w**2 * (y - mean) ** 2) / np.sum(w) ** 2
    se = np.sqrt(var)
    crit = stats.t.ppf(0.975, n - 1)
    return Estimate(
        value=mean,
        se=se,
        ci_low=mean - crit * se,
        ci_high=mean + crit * se,
        method="weighted, naive SE",
        n=n,
        df=n - 1,
    )


def design_based_mean(
    df: pd.DataFrame,
    value: str,
    weight: str,
    strata: str = "strata",
    psu: str = "psu",
) -> Estimate:
    """
    Weighted mean with a design-based standard error (Taylor linearization).

    The mean is a ratio of two estimated totals, so its variance comes from
    linearizing that ratio and then applying the usual stratified-cluster
    variance formula to the linearized residuals:

        z_i = w_i * (y_i - mean) / sum(w)

        V = sum over strata h of
              n_h / (n_h - 1) * sum over PSUs i of (z_hi - mean_h(z))^2

    Degrees of freedom = (number of PSUs) - (number of strata), which for
    NHANES is typically small, so t critical values matter.
    """
    sub = _clean(df, value, weight, strata, psu)
    y = sub[value].to_numpy(dtype=float)
    w = sub[weight].to_numpy(dtype=float)
    n = len(y)

    w_total = w.sum()
    mean = np.sum(w * y) / w_total

    # Linearized residual for each person.
    sub = sub.assign(_z=w * (y - mean) / w_total)

    # Collapse to PSU totals within strata.
    psu_totals = sub.groupby([strata, psu], observed=True)["_z"].sum().reset_index()

    variance = 0.0
    n_psu = 0
    n_strata = 0
    for _, group in psu_totals.groupby(strata, observed=True):
        n_h = len(group)
        n_psu += n_h
        n_strata += 1
        if n_h < 2:
            # A stratum with a single PSU contributes no variance estimate.
            # NHANES's masked pseudo-strata normally have two, so this
            # usually means the analytic subset dropped one.
            continue
        totals = group["_z"].to_numpy(dtype=float)
        variance += n_h / (n_h - 1) * np.sum((totals - totals.mean()) ** 2)

    se = float(np.sqrt(variance))
    dof = max(n_psu - n_strata, 1)
    crit = stats.t.ppf(0.975, dof)
    return Estimate(
        value=float(mean),
        se=se,
        ci_low=float(mean - crit * se),
        ci_high=float(mean + crit * se),
        method="weighted, design-based SE",
        n=n,
        df=dof,
    )


def design_effect(design: Estimate, naive: Estimate) -> float:
    """
    Ratio of design-based to naive variance.

    A DEFF of 2 means the clustered sample carries about as much information
    as a simple random sample half its size. Reporting this is a compact way
    to show how much the design matters.
    """
    return (design.se / naive.se) ** 2


def geometric_mean(
    df: pd.DataFrame,
    value: str,
    weight: str | None = None,
    strata: str = "strata",
    psu: str = "psu",
    design_based: bool = True,
) -> Estimate:
    """
    Geometric mean, the conventional summary for biomonitoring data.

    Serum concentrations are right-skewed and roughly log-normal, so the
    arithmetic mean is pulled upward by a few high values. The geometric mean
    is computed as exp(mean(log(x))), and its confidence interval is formed on
    the log scale and then exponentiated -- which is why the result is
    asymmetric around the point estimate.
    """
    sub = df.copy()
    sub = sub[sub[value] > 0]  # log is undefined at zero
    sub["_log"] = np.log(sub[value].astype(float))

    if weight is None:
        est = naive_mean(sub, "_log")
    elif design_based:
        est = design_based_mean(sub, "_log", weight, strata, psu)
    else:
        est = weighted_mean_naive_se(sub, "_log", weight)

    return Estimate(
        value=float(np.exp(est.value)),
        se=est.se,  # SE stays on the log scale; note this when reporting
        ci_low=float(np.exp(est.ci_low)),
        ci_high=float(np.exp(est.ci_high)),
        method=f"geometric mean, {est.method}",
        n=est.n,
        df=est.df,
    )


def compare_methods(
    df: pd.DataFrame,
    value: str,
    weight: str = "weight_pfas",
    strata: str = "strata",
    psu: str = "psu",
    log_scale: bool = True,
) -> pd.DataFrame:
    """
    Run every estimator on the same variable and return a tidy comparison.

    This table is the deliverable for the weighting half of the project: it
    separates the effect of weighting (rows 1 vs 2) from the effect of the
    clustered design (rows 2 vs 3).
    """
    fn = geometric_mean if log_scale else None

    if log_scale:
        rows = [
            fn(df, value, weight=None),
            fn(df, value, weight=weight, design_based=False, strata=strata, psu=psu),
            fn(df, value, weight=weight, design_based=True, strata=strata, psu=psu),
        ]
    else:
        rows = [
            naive_mean(df, value),
            weighted_mean_naive_se(df, value, weight),
            design_based_mean(df, value, weight, strata, psu),
        ]

    out = pd.DataFrame([r.as_dict() for r in rows])
    out["ci_width"] = out["ci_high"] - out["ci_low"]
    # Design effect relative to the weighted-naive row.
    out["deff_vs_naive"] = (out["se"] / out.loc[1, "se"]) ** 2
    return out
