# Synthea Setup for BIME Digital Twins

Synthea generates a synthetic patient population. This pipeline reads its CSV
output to create the digital twin dataset for the BIME demo app.

## Prerequisites

- Java 11+ (`java -version` to check)
- ~500 MB disk space for Synthea jar + output

## Step 1 — Download Synthea

```bash
cd bime/
mkdir -p synthea_output
curl -LO https://github.com/synthetichealth/synthea/releases/latest/download/synthea-with-dependencies.jar
```

## Step 2 — Run Synthea

Generate 500 female patients from Washington state. The anemia module is
included in Synthea's default modules, so iron deficiency anemia cases will
appear naturally.

```bash
java -jar synthea-with-dependencies.jar \
  -p 500 \
  --exporter.csv.export true \
  --exporter.fhir.export false \
  --exporter.ccda.export false \
  --exporter.baseDirectory bime/synthea_output \
  -s 42 \
  Washington \
  Seattle
```

| Flag | Meaning |
|------|---------|
| `-p 500` | Generate 500 patients |
| `--exporter.csv.export true` | Output CSV files (required) |
| `-s 42` | Reproducible random seed |
| `Washington Seattle` | State and city (affects demographics) |

Output lands in `bime/synthea_output/csv/`.

## Step 3 — Run curate_data.py

```bash
python bime/curate_data.py
```

This reads from `bime/synthea_output/csv/` and writes to `bime/data/`.

## What Synthea generates (relevant files)

| File | Contents relevant to this pipeline |
|------|-------------------------------------|
| `patients.csv` | UUID, BirthDate, Gender, Race, Ethnicity, DeathDate |
| `observations.csv` | Lab results — HB via LOINC **718-7** (g/dL), CBC panel |
| `conditions.csv` | Diagnoses as SNOMED-CT codes + descriptions |
| `encounters.csv` | Visit type (ambulatory/wellness/emergency etc.), linked org |
| `organizations.csv` | Provider organization names |

### What Synthea does NOT generate
- **Ferritin** — the anemia module tracks iron stores internally but does not
  emit a ferritin lab observation (LOINC 2276-4). `curate_data.py` simulates
  ferritin probabilistically using a log-normal model calibrated to the
  expected P(ferritin < 30) relationship with HB drop from setpoint.
- ICD-9 codes — Synthea uses SNOMED-CT. `curate_data.py` applies an embedded
  SNOMED→ICD-10 crosswalk; ICD-9 is left blank.

## Increasing anemia prevalence

By default ~5–10 % of Synthea patients develop anemia. To enrich for IDA cases:

**Option A** — generate more patients (`-p 2000`).

**Option B** — set a higher female age range by editing
`src/main/resources/geography/demographics.csv` before running.

**Option C** — pass the built-in anemia submodule explicitly (advanced):
```bash
java -jar synthea-with-dependencies.jar \
  -p 500 -s 42 \
  --exporter.csv.export true \
  --exporter.baseDirectory bime/synthea_output \
  -m anemia \
  Washington Seattle
```

## Minimum patient yield

`curate_data.py` requires each patient to have **≥ 3 hemoglobin measurements**
and an HB result ≤ 14.5 g/dL. With 500 Synthea patients you should expect
roughly 30–80 qualifying digital twins. Generate more patients (`-p 1000+`)
for a richer demo dataset.
