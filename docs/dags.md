# Causal structures

Exposure: family income-to-poverty ratio (`INDFMPIR`)
Outcome: serum PFOS concentration, log-transformed

Each DAG below is a different belief about how these variables relate. Paste
the code block into [dagitty.net/dags.html](https://dagitty.net/dags.html) to
draw it and read off the minimal sufficient adjustment set, then copy that set
into `ADJUSTMENT_SETS` in `src/config.py`.

Fill in the justification column as you read papers. Each arrow needs a reason
you can defend in Q&A, and "it seemed plausible" is not one.

---

## DAG A — socioeconomic position as a proximal cause

Income affects exposure through where you live, what you drink, what you eat,
and what products you use. Age, sex and race/ethnicity are common causes of
both income and exposure. Water source and diet lie *on* the causal pathway,
so they are mediators and must not be adjusted for.

```
dag {
  Income [exposure]
  PFOS [outcome]
  Age -> Income
  Age -> PFOS
  Sex -> PFOS
  Sex -> Income
  Race -> Income
  Race -> PFOS
  Income -> WaterSource
  Income -> Diet
  WaterSource -> PFOS
  Diet -> PFOS
  WaterSource [unobserved]
}
```

Expected minimal adjustment set: Age, Sex, Race

---

## DAG B — race as upstream of socioeconomic position

Structural factors shape residential and occupational exposure and also shape
income and education. Here race is not a parallel confounder but a cause of
socioeconomic position. The income coefficient answers a different question,
and the race coefficient from DAG A's model is not interpretable as a causal
effect (see the Table 2 fallacy demo in `dag_models.py`).

```
dag {
  Income [exposure]
  PFOS [outcome]
  Race -> Income
  Race -> Education
  Race -> Residence
  Education -> Income
  Residence -> WaterSource
  Residence -> PFOS
  Income -> WaterSource
  WaterSource -> PFOS
  Age -> Income
  Age -> PFOS
  Sex -> PFOS
  WaterSource [unobserved]
  Residence [unobserved]
}
```

Expected minimal adjustment set: differs from A — read it off dagitty rather
than guessing.

---

## DAG C — kidney function included

PFAS are cleared renally, so reduced kidney function raises serum
concentrations. But PFAS may also damage the kidney. If eGFR is a mediator or
a collider rather than a confounder, adjusting for it introduces bias instead
of removing it. This is a live disagreement in the PFAS literature and the
sharpest illustration of collider bias in the set.

```
dag {
  Income [exposure]
  PFOS [outcome]
  Age -> Income
  Age -> PFOS
  Age -> eGFR
  Sex -> PFOS
  Race -> Income
  Race -> PFOS
  Income -> PFOS
  PFOS -> eGFR
  eGFR -> PFOS
}
```

Note: the last two arrows form a cycle, which a DAG cannot contain. That is
itself the point — resolving it forces you to commit to a direction, or to
separate serum PFOS at time of measurement from cumulative exposure. Decide
which and say so.

---

## Reading notes

One row per paper. The disagreements between these rows are your DAGs.

| Paper | Exposure | Outcome | Adjusted for | Stated justification | Notes |
|---|---|---|---|---|---|
| | | | | | |
| | | | | | |
| | | | | | |

---

## The unmeasured-mediator problem

Drinking water is a dominant PFAS exposure route and NHANES does not measure
it. No adjustment set recovers a clean causal effect when the main pathway is
unobserved. Say this plainly in the conclusion: it is a stronger finding than a
confident number would be, and it comes from field experience rather than a
textbook.
