"""
src/synth/parse_observations.py

Parses Synthea observations.csv to extract hemoglobin and iron-panel labs.

WHO anemia thresholds applied to each patient's most-recent HB reading:
  Adult male   (≥ 15 y):  Hb < 13.0 g/dL
  Adult female (≥ 15 y):  Hb < 12.0 g/dL
  Child        (< 15 y):  Hb < 11.5 g/dL  (WHO 2011 simplified)

Patients are joined with patients.csv for GENDER and BIRTHDATE.
"""

from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

# ── LOINC codes ───────────────────────────────────────────────────────────────
HB_LOINC       = "718-7"    # Hemoglobin [Mass/volume] in Blood  (g/dL)
FERRITIN_LOINC = "2276-4"   # Ferritin [Mass/volume] in Serum    (ug/L)
IRON_LOINC     = "2498-4"   # Iron [Mass/volume] in Serum        (ug/dL)

# ── WHO HB thresholds (g/dL) ──────────────────────────────────────────────────
HB_THRESHOLD_MALE   = 13.0
HB_THRESHOLD_FEMALE = 12.0
HB_THRESHOLD_CHILD  = 11.5   # < 15 years


def _load_patients(csv_dir: Path) -> pd.DataFrame:
    pts = pd.read_csv(csv_dir / "patients.csv", low_memory=False,
                      usecols=["Id", "BIRTHDATE", "GENDER", "DEATHDATE"])
    pts["BIRTHDATE"] = pd.to_datetime(pts["BIRTHDATE"], errors="coerce")
    pts["GENDER"]    = pts["GENDER"].str.upper().str.strip()
    return pts.rename(columns={"Id": "PATIENT"})


def _load_observations(csv_dir: Path) -> pd.DataFrame:
    obs = pd.read_csv(csv_dir / "observations.csv", low_memory=False,
                      usecols=["DATE", "PATIENT", "CODE", "DESCRIPTION", "VALUE", "UNITS"])
    obs["DATE"]  = pd.to_datetime(obs["DATE"], errors="coerce", utc=True)
    obs["VALUE"] = pd.to_numeric(obs["VALUE"], errors="coerce")
    obs["CODE"]  = obs["CODE"].astype(str).str.strip()
    return obs


def _age_at(birthdate: pd.Series, ref_date: pd.Timestamp) -> pd.Series:
    return ((ref_date - birthdate).dt.days / 365.25).fillna(99)


def _who_threshold(gender: str, age: float) -> float:
    if age < 15:
        return HB_THRESHOLD_CHILD
    return HB_THRESHOLD_MALE if gender == "M" else HB_THRESHOLD_FEMALE


def parse_observations(csv_dir: Path, patient_ids: Optional[set] = None) -> dict:
    """
    Returns a dict with:
      hb_observations    — count of all HB rows
      patients_with_hb   — count of unique patients with any HB reading
      hb_mean / hb_std   — over all HB readings
      hb_histogram       — list of {bin_start, bin_end, count} dicts (10 bins)
      lab_anemia_ids     — set of patient UUIDs with most-recent HB below WHO threshold
      ferritin_present   — bool: does the cohort have ferritin observations?
      ferritin_count     — number of ferritin rows
      iron_panel_codes   — list of LOINC codes observed in the iron panel

    patient_ids: if provided, restrict all observations to this set of patient UUIDs.
    """
    pts = _load_patients(csv_dir)
    obs = _load_observations(csv_dir)

    if patient_ids is not None:
        pts = pts[pts["PATIENT"].isin(patient_ids)]
        obs = obs[obs["PATIENT"].isin(patient_ids)]

    # ── Hemoglobin ────────────────────────────────────────────────────────────
    hb = obs[obs["CODE"] == HB_LOINC].dropna(subset=["VALUE"]).copy()

    hb_all_values = hb["VALUE"].values.astype(float)
    counts, edges  = np.histogram(hb_all_values, bins=10)
    hb_histogram   = [
        {"bin_start": round(float(edges[i]), 2),
         "bin_end":   round(float(edges[i + 1]), 2),
         "count":     int(counts[i])}
        for i in range(len(counts))
    ]

    # Most-recent HB per patient (for WHO threshold)
    hb_latest = (
        hb.sort_values("DATE")
          .groupby("PATIENT", as_index=False)
          .last()[["PATIENT", "DATE", "VALUE"]]
          .rename(columns={"VALUE": "hb_latest", "DATE": "hb_date"})
    )
    hb_latest = hb_latest.merge(pts[["PATIENT", "BIRTHDATE", "GENDER"]], on="PATIENT", how="left")
    hb_latest["age"] = _age_at(hb_latest["BIRTHDATE"], pd.Timestamp.today())
    hb_latest["threshold"] = hb_latest.apply(
        lambda r: _who_threshold(r["GENDER"], r["age"]), axis=1
    )
    hb_latest["lab_anemia"] = hb_latest["hb_latest"] < hb_latest["threshold"]

    # ── Ferritin + iron panel ─────────────────────────────────────────────────
    IRON_PANEL_LOINCS = {FERRITIN_LOINC, IRON_LOINC, "2500-7", "2502-3"}
    iron_panel_obs    = obs[obs["CODE"].isin(IRON_PANEL_LOINCS)]
    ferritin_obs      = obs[obs["CODE"] == FERRITIN_LOINC]

    iron_panel_codes  = (
        iron_panel_obs[["CODE", "DESCRIPTION"]]
        .drop_duplicates()
        .assign(count=iron_panel_obs.groupby("CODE")["CODE"].transform("count"))
        .drop_duplicates(subset="CODE")
        .sort_values("CODE")
        .to_dict(orient="records")
    )

    return {
        "hb_observations":  len(hb),
        "patients_with_hb": hb["PATIENT"].nunique(),
        "hb_mean":          round(float(np.mean(hb_all_values)), 3),
        "hb_std":           round(float(np.std(hb_all_values, ddof=1)), 3),
        "hb_histogram":     hb_histogram,
        "lab_anemia_ids":   set(hb_latest.loc[hb_latest["lab_anemia"], "PATIENT"]),
        "ferritin_present": len(ferritin_obs) > 0,
        "ferritin_count":   len(ferritin_obs),
        "iron_panel_codes": iron_panel_codes,
    }
