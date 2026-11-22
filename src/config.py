"""
Central configuration for the NHANES PFAS project.

IMPORTANT: Every variable name below must be verified against the official
codebook before you trust it. NHANES renames variables between cycles --
notably, PFOA and PFOS were split into linear/branched isomers starting in
2013-2014, so a name that works for one cycle may not exist in another.

Codebooks:
  Demographics: https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/DEMO_J.htm
  PFAS:         https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/PFAS_J.htm
"""

# ---------------------------------------------------------------------------
# Cycle and files
# ---------------------------------------------------------------------------

CYCLE = "2017-2018"
CYCLE_SUFFIX = "J"

# The CDC changed its URL layout in November 2024. The folder is the FIRST
# year of the cycle (2017 for 2017-2018). The old /Nchs/Nhanes/2017-2018/
# form returns a "Page Not Found" HTML page with a 200 status code.
CYCLE_START_YEAR = CYCLE.split("-")[0]
BASE_URL = f"https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/{CYCLE_START_YEAR}/DataFiles"

FILES = {
    "demo": f"DEMO_{CYCLE_SUFFIX}.xpt",
    "pfas": f"PFAS_{CYCLE_SUFFIX}.xpt",
    # Optional, only if a DAG needs them:
    "bmx": f"BMX_{CYCLE_SUFFIX}.xpt",    # body measures -> BMI
    "biopro": f"BIOPRO_{CYCLE_SUFFIX}.xpt",  # standard biochem -> creatinine for eGFR
    "rhq": f"RHQ_{CYCLE_SUFFIX}.xpt",    # reproductive health -> parity, breastfeeding
}

# ---------------------------------------------------------------------------
# Survey design variables (from DEMO)
# ---------------------------------------------------------------------------

DESIGN = {
    "strata": "SDMVSTRA",   # masked variance pseudo-stratum
    "psu": "SDMVPSU",       # masked variance pseudo-PSU
    "weight_interview": "WTINT2YR",
    "weight_mec": "WTMEC2YR",
}

# The PFAS subsample has its OWN weight. Using WTMEC2YR instead is a common
# error -- verify the exact name in the PFAS codebook for your cycle.
WEIGHT_PFAS = "WTSB2YR"

# ---------------------------------------------------------------------------
# PFAS analytes
# ---------------------------------------------------------------------------
# Each entry: (result variable, comment-code variable)
# The comment code flags values below the limit of detection.
# Convention in recent cycles: 0 = at or above LOD, 1 = below LOD.
# VERIFY this coding in the codebook -- do not assume.

ANALYTES = {
    "PFOS_linear": ("LBXNFOS", "LBDNFOSL"),
    "PFOS_branched": ("LBXMFOS", "LBDMFOSL"),
    "PFOA_linear": ("LBXNFOA", "LBDNFOAL"),
    "PFOA_branched": ("LBXBFOA", "LBDBFOAL"),
    "PFHxS": ("LBXPFHS", "LBDPFHSL"),
    "PFNA": ("LBXPFNA", "LBDPFNAL"),
    "PFDA": ("LBXPFDE", "LBDPFDEL"),
}

# Primary outcome for the main analysis.
PRIMARY_ANALYTE = "PFOS_linear"

# ---------------------------------------------------------------------------
# Demographic / covariate variables
# ---------------------------------------------------------------------------

COVARIATES = {
    "age": "RIDAGEYR",        # years; 80 is top-coded
    "sex": "RIAGENDR",        # 1 male, 2 female
    "race_eth": "RIDRETH3",   # 6 categories incl. non-Hispanic Asian
    "income_poverty": "INDFMPIR",  # family income-to-poverty ratio, 0-5 (capped)
    "education": "DMDEDUC2",  # adults 20+; 7 and 9 are refused/don't know
}

# Values that mean "missing" rather than a real answer. Always check the
# codebook: 7/77/777 = refused, 9/99/999 = don't know, in most questionnaires.
MISSING_CODES = {
    "DMDEDUC2": [7, 9],
}

# ---------------------------------------------------------------------------
# Analytic sample
# ---------------------------------------------------------------------------

MIN_AGE = 20  # adults only; education variable is only collected for 20+

# ---------------------------------------------------------------------------
# DAG-implied adjustment sets
# ---------------------------------------------------------------------------
# Exposure of interest: income_poverty
# Outcome: log(PFOS)
#
# Fill these in AFTER drawing each DAG in dagitty and reading off the minimal
# sufficient adjustment set. The point of the project is that these differ.

ADJUSTMENT_SETS = {
    "A_ses_proximal": ["age", "sex", "race_eth"],
    "B_race_upstream": ["age", "sex"],
    "C_kidney_included": ["age", "sex", "race_eth", "egfr"],
    "naive_everything": ["age", "sex", "race_eth", "education", "bmi", "egfr"],
}