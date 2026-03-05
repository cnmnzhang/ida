"""
src/synth/parse_conditions.py

Parses Synthea conditions.csv to identify anemia and IDA diagnoses.

What Synthea actually generates (Washington, seed=1, n=1000):
  - 271737000  "Anemia (disorder)"          — the generic anemia module code
  - 87522002   "Iron deficiency anemia"     — IDA-specific (rare, module-dependent)
  - 234347009  "Anemia due to iron deficiency" — IDA variant

Matching strategy:
  - IDA   : SNOMED 87522002 | 234347009  OR  description ∋ "iron deficiency"
  - Anemia: IDA codes above  OR  SNOMED 271737000  OR  description ∋ "anemia"
"""

from pathlib import Path
from typing import Optional

import pandas as pd

# ── SNOMED code sets ──────────────────────────────────────────────────────────

# Specific IDA codes
IDA_SNOMED = {"87522002", "234347009"}

# Generic anemia codes (includes IDA as a subset)
ANEMIA_SNOMED = IDA_SNOMED | {
    "271737000",   # Anemia (disorder) — most common in Synthea
    "713048008",   # Normocytic anemia
    "448235001",   # Macrocytic anemia
    "14759004",    # Megaloblastic anemia
}


def load_conditions(csv_dir: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_dir / "conditions.csv", low_memory=False)
    df["CODE"] = df["CODE"].astype(str).str.strip()
    df["DESCRIPTION"] = df["DESCRIPTION"].fillna("").str.strip()
    return df


def parse_conditions(csv_dir: Path, patient_ids: Optional[set] = None) -> dict:
    """
    Returns a dict with:
      anemia_patient_ids  — set of patient UUIDs with any anemia diagnosis
      ida_patient_ids     — set with IDA-specific diagnosis
      observed_codes      — DataFrame of (CODE, DESCRIPTION, patient_count) for anemia codes

    patient_ids: if provided, restrict analysis to this set of patient UUIDs.
    """
    df = load_conditions(csv_dir)
    if patient_ids is not None:
        df = df[df["PATIENT"].isin(patient_ids)]

    # ── IDA match ─────────────────────────────────────────────────────────────
    ida_code  = df["CODE"].isin(IDA_SNOMED)
    ida_desc  = df["DESCRIPTION"].str.contains("iron deficiency", case=False)
    ida_rows  = df[ida_code | ida_desc]

    # ── Anemia match (superset) ───────────────────────────────────────────────
    anemia_code = df["CODE"].isin(ANEMIA_SNOMED)
    anemia_desc = df["DESCRIPTION"].str.contains(r"\banemia\b", case=False, regex=True)
    anemia_rows = df[anemia_code | anemia_desc]

    # ── Observed anemia-related codes inventory ───────────────────────────────
    observed_codes = (
        anemia_rows
        .groupby(["CODE", "DESCRIPTION"])["PATIENT"]
        .nunique()
        .reset_index()
        .rename(columns={"PATIENT": "patient_count"})
        .sort_values("patient_count", ascending=False)
        .reset_index(drop=True)
    )

    return {
        "anemia_patient_ids": set(anemia_rows["PATIENT"].dropna()),
        "ida_patient_ids":    set(ida_rows["PATIENT"].dropna()),
        "observed_codes":     observed_codes,
    }
