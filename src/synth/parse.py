"""
src/synth/parse.py

Parses Synthea CSV output to extract cohort size, HB values, and IDA patient IDs.
"""

from pathlib import Path

import pandas as pd

HB_LOINC = "718-7"

# SNOMED-CT codes for iron deficiency anemia (from curate_data.py)
IDA_SNOMED_CODES = {"87522002", "234347009"}


def parse_outputs(outdir: Path) -> tuple[int, list[float], set[str]]:
    """
    Parse Synthea CSV output directory.

    Returns:
        cohort_size: total number of patients generated
        hb_values: list of hemoglobin float values (g/dL)
        ida_patient_ids: set of patient UUIDs with an IDA diagnosis
    """
    csv_dir = outdir / "csv"

    # --- Patients ---
    patients_df = pd.read_csv(csv_dir / "patients.csv", low_memory=False)
    cohort_size = len(patients_df)

    # --- Hemoglobin observations ---
    obs_df = pd.read_csv(csv_dir / "observations.csv", low_memory=False)
    hb_df = obs_df[obs_df["CODE"] == HB_LOINC].copy()
    hb_df["VALUE"] = pd.to_numeric(hb_df["VALUE"], errors="coerce")
    hb_values = hb_df["VALUE"].dropna().tolist()

    # --- IDA conditions ---
    cond_df = pd.read_csv(csv_dir / "conditions.csv", low_memory=False)
    cond_df["CODE"] = cond_df["CODE"].astype(str)

    code_match = cond_df["CODE"].isin(IDA_SNOMED_CODES)
    desc_match = (
        cond_df["DESCRIPTION"]
        .fillna("")
        .str.contains("iron deficiency", case=False, na=False)
    )
    ida_rows = cond_df[code_match | desc_match]
    ida_patient_ids = set(ida_rows["PATIENT"].dropna().unique())

    return cohort_size, hb_values, ida_patient_ids
