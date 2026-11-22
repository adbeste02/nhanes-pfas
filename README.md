# How much do analytic choices change PFAS exposure estimates?

A sensitivity analysis of serum PFOS concentrations in NHANES, asking how much
the estimated association between socioeconomic position and exposure depends
on two sets of choices: how the survey design is handled, and what causal
structure is assumed.

**Status:** in progress.

## Motivation

I spent two years as a laboratory technician in an exposure science lab at
Duke, where we compared PFAS concentrations in firefighters against NHANES
reference values. We used simple averages. NHANES is a stratified, multistage
cluster sample with deliberate oversampling, so a simple average is not an
estimate of the US population — and the reference value a study compares
against depends on choices that are often made without comment. This project
asks how much those choices matter.

## Questions

1. **Survey design.** How far apart are unweighted, weighted-naive, and
   design-based estimates, and what is the design effect?
2. **Causal structure.** How much does the estimated association between the
   income-to-poverty ratio and serum PFOS move across defensible DAGs?

## Data

[NHANES](https://wwwn.cdc.gov/nchs/nhanes/) (CDC / NCHS), demographics and
PFAS laboratory files. Data is not committed to this repository; the download
script fetches it from the CDC.

## Methods

- Survey-weighted geometric means with design-based variance by Taylor
  linearization, using the masked pseudo-strata and pseudo-PSU variables.
- The PFAS subsample weight, not the general examination weight.
- Weighted linear regression of log concentration on the income-to-poverty
  ratio, with standard errors clustered on PSU within stratum.
- Adjustment sets derived from DAGs in [dagitty](https://dagitty.net), with
  justifications in [`docs/dags.md`](docs/dags.md).

## Running it

```bash
pip install -r requirements.txt
python src/download_data.py        # fetch DEMO and PFAS from the CDC
python src/build_database.py       # merge on SEQN, load into SQLite
python src/run_analysis.py         # produce the comparison tables
```

## Layout

```
src/config.py          variable names, file URLs, adjustment sets
src/download_data.py   fetch raw .XPT files
src/build_database.py  merge and load into SQLite
src/survey_stats.py    weighted estimation and design-based variance
src/dag_models.py      regression under competing adjustment sets
src/run_analysis.py    end-to-end run
docs/dags.md           DAG specifications and reading notes
```

## Findings

_To be written._

## Limitations

- Drinking water is a dominant PFAS exposure route and is not measured in
  NHANES. No adjustment set identifies a clean causal effect when the main
  pathway is unobserved.
- Regression standard errors are clustered rather than fully linearized, which
  is slightly conservative because it does not take credit for stratification.
- Age conflates accumulation time with birth cohort, and PFOS production was
  phased out in the US beginning in the early 2000s.
- Cross-sectional data; serum concentration reflects cumulative past exposure,
  not current income.

## Validation

Weighted geometric means are checked against CDC's
[National Exposure Report](https://www.cdc.gov/environmental-exposure-report/)
summary tables for the same cycle and analyte.
