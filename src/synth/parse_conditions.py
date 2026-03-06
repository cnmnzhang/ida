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
    anemia_patient_ids = set()
    ida_patient_ids = set()
    # key: (CODE, DESCRIPTION) -> set(PATIENT) for unique patient counts
    observed_map = {}

    cols = ["PATIENT", "CODE", "DESCRIPTION"]
    for chunk in pd.read_csv(csv_dir / "conditions.csv", low_memory=False, usecols=cols, chunksize=250_000):
        chunk["CODE"] = chunk["CODE"].astype(str).str.strip()
        chunk["DESCRIPTION"] = chunk["DESCRIPTION"].fillna("").str.strip()

        if patient_ids is not None:
            chunk = chunk[chunk["PATIENT"].isin(patient_ids)]
        if chunk.empty:
            continue

        # ── IDA match ─────────────────────────────────────────────────────────
        ida_code = chunk["CODE"].isin(IDA_SNOMED)
        ida_desc = chunk["DESCRIPTION"].str.contains("iron deficiency", case=False)
        ida_rows = chunk[ida_code | ida_desc]
        if not ida_rows.empty:
            ida_patient_ids.update(ida_rows["PATIENT"].dropna().tolist())

        # ── Anemia match (superset) ───────────────────────────────────────────
        anemia_code = chunk["CODE"].isin(ANEMIA_SNOMED)
        anemia_desc = chunk["DESCRIPTION"].str.contains(r"\banemia\b", case=False, regex=True)
        anemia_rows = chunk[anemia_code | anemia_desc][["PATIENT", "CODE", "DESCRIPTION"]]
        if anemia_rows.empty:
            continue

        anemia_rows = anemia_rows.dropna(subset=["PATIENT"])
        anemia_patient_ids.update(anemia_rows["PATIENT"].tolist())

        # Count distinct patients per (CODE, DESCRIPTION)
        dedup = anemia_rows.drop_duplicates(subset=["PATIENT", "CODE", "DESCRIPTION"])
        for (code, desc), grp in dedup.groupby(["CODE", "DESCRIPTION"]):
            key = (str(code), str(desc))
            if key not in observed_map:
                observed_map[key] = set()
            observed_map[key].update(grp["PATIENT"].tolist())

    rows = [
        {"CODE": code, "DESCRIPTION": desc, "patient_count": len(pids)}
        for (code, desc), pids in observed_map.items()
    ]
    if rows:
        observed_codes = (
            pd.DataFrame(rows)
            .sort_values("patient_count", ascending=False)
            .reset_index(drop=True)
        )
    else:
        observed_codes = pd.DataFrame(columns=["CODE", "DESCRIPTION", "patient_count"])

    return {
        "anemia_patient_ids": anemia_patient_ids,
        "ida_patient_ids": ida_patient_ids,
        "observed_codes": observed_codes,
    }
