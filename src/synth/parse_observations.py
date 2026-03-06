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
IRON_PANEL_LOINCS = {FERRITIN_LOINC, IRON_LOINC, "2500-7", "2502-3"}

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


def _iter_obs_chunks(csv_dir: Path, chunksize: int = 250_000):
    cols = ["DATE", "PATIENT", "CODE", "DESCRIPTION", "VALUE", "UNITS"]
    for chunk in pd.read_csv(csv_dir / "observations.csv", low_memory=False, usecols=cols, chunksize=chunksize):
        chunk["CODE"] = chunk["CODE"].astype(str).str.strip()
        yield chunk


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
    if patient_ids is not None:
        pts = pts[pts["PATIENT"].isin(patient_ids)]

    # Pass 1: running HB stats, per-patient latest HB, ferritin and iron-panel counts.
    hb_n = 0
    hb_sum = 0.0
    hb_sum_sq = 0.0
    hb_min = float("inf")
    hb_max = float("-inf")
    hb_patient_ids = set()
    hb_latest_by_patient = {}  # pid -> (date, value)
    ferritin_count = 0
    iron_panel_counts = {}     # code -> int
    iron_panel_desc = {}       # code -> description
    iron_panel_desc_counts = {}  # code -> {desc: count}

    for chunk in _iter_obs_chunks(csv_dir):
        if patient_ids is not None:
            chunk = chunk[chunk["PATIENT"].isin(patient_ids)]
        if chunk.empty:
            continue

        hb = chunk[chunk["CODE"] == HB_LOINC][["PATIENT", "DATE", "VALUE"]].copy()
        if not hb.empty:
            hb["DATE"] = pd.to_datetime(hb["DATE"], errors="coerce", utc=True)
            hb["VALUE"] = pd.to_numeric(hb["VALUE"], errors="coerce")
            hb = hb.dropna(subset=["DATE", "VALUE"])

            if not hb.empty:
                vals = hb["VALUE"].to_numpy(dtype=float)
                hb_n += len(vals)
                hb_sum += float(vals.sum())
                hb_sum_sq += float((vals * vals).sum())
                hb_min = min(hb_min, float(vals.min()))
                hb_max = max(hb_max, float(vals.max()))
                hb_patient_ids.update(hb["PATIENT"].dropna().tolist())

                latest_chunk = (
                    hb.sort_values("DATE")
                      .groupby("PATIENT", as_index=False)
                      .last()[["PATIENT", "DATE", "VALUE"]]
                )
                for _, row in latest_chunk.iterrows():
                    pid = row["PATIENT"]
                    dt = row["DATE"]
                    prev = hb_latest_by_patient.get(pid)
                    if prev is None or dt > prev[0]:
                        hb_latest_by_patient[pid] = (dt, float(row["VALUE"]))

        ferr = chunk[chunk["CODE"] == FERRITIN_LOINC]
        ferritin_count += int(len(ferr))

        panel = chunk[chunk["CODE"].isin(IRON_PANEL_LOINCS)][["CODE", "DESCRIPTION"]].copy()
        if not panel.empty:
            panel["DESCRIPTION"] = panel["DESCRIPTION"].fillna("").astype(str).str.strip()
            grouped = panel.groupby(["CODE", "DESCRIPTION"]).size()
            for (code, desc), cnt in grouped.items():
                code = str(code)
                cnt_i = int(cnt)
                iron_panel_counts[code] = iron_panel_counts.get(code, 0) + cnt_i
                if code not in iron_panel_desc_counts:
                    iron_panel_desc_counts[code] = {}
                desc_counts = iron_panel_desc_counts[code]
                desc_counts[desc] = desc_counts.get(desc, 0) + cnt_i

    if hb_n == 0:
        hb_histogram = []
        hb_mean = 0.0
        hb_std = 0.0
    else:
        hb_mean = hb_sum / hb_n
        hb_std = 0.0
        if hb_n > 1:
            var = (hb_sum_sq - hb_n * hb_mean * hb_mean) / (hb_n - 1)
            hb_std = float(np.sqrt(max(var, 0.0)))

        # Pass 2: histogram with fixed edges from pass 1 min/max.
        if hb_min == hb_max:
            edges = np.linspace(hb_min - 0.5, hb_max + 0.5, 11)
        else:
            edges = np.linspace(hb_min, hb_max, 11)

        hist_counts = np.zeros(10, dtype=int)
        for chunk in _iter_obs_chunks(csv_dir):
            if patient_ids is not None:
                chunk = chunk[chunk["PATIENT"].isin(patient_ids)]
            if chunk.empty:
                continue

            hb = chunk[chunk["CODE"] == HB_LOINC][["VALUE"]].copy()
            if hb.empty:
                continue
            hb["VALUE"] = pd.to_numeric(hb["VALUE"], errors="coerce")
            hb = hb.dropna(subset=["VALUE"])
            if hb.empty:
                continue
            vals = hb["VALUE"].to_numpy(dtype=float)
            hist_counts += np.histogram(vals, bins=edges)[0]

        hb_histogram = [
            {
                "bin_start": round(float(edges[i]), 2),
                "bin_end": round(float(edges[i + 1]), 2),
                "count": int(hist_counts[i]),
            }
            for i in range(len(hist_counts))
        ]

    if hb_latest_by_patient:
        hb_latest = pd.DataFrame(
            [
                {"PATIENT": pid, "hb_date": dt, "hb_latest": value}
                for pid, (dt, value) in hb_latest_by_patient.items()
            ]
        )
    else:
        hb_latest = pd.DataFrame(columns=["PATIENT", "hb_date", "hb_latest"])

    hb_latest = hb_latest.merge(pts[["PATIENT", "BIRTHDATE", "GENDER"]], on="PATIENT", how="left")
    hb_latest["age"] = _age_at(hb_latest["BIRTHDATE"], pd.Timestamp.today())
    hb_latest["threshold"] = hb_latest.apply(
        lambda r: _who_threshold(r["GENDER"], r["age"]), axis=1
    )
    hb_latest["lab_anemia"] = hb_latest["hb_latest"] < hb_latest["threshold"]

    iron_panel_codes = []
    for code in sorted(iron_panel_counts):
        desc_counts = iron_panel_desc_counts.get(code, {})
        if desc_counts:
            best_desc = max(desc_counts.items(), key=lambda kv: kv[1])[0]
        else:
            best_desc = ""
        iron_panel_codes.append(
            {
                "CODE": code,
                "DESCRIPTION": best_desc,
                "count": int(iron_panel_counts[code]),
            }
        )

    return {
        "hb_observations": hb_n,
        "patients_with_hb": len(hb_patient_ids),
        "hb_mean": round(float(hb_mean), 3),
        "hb_std": round(float(hb_std), 3),
        "hb_histogram": hb_histogram,
        "lab_anemia_ids": set(hb_latest.loc[hb_latest["lab_anemia"], "PATIENT"]),
        "ferritin_present": ferritin_count > 0,
        "ferritin_count": ferritin_count,
        "iron_panel_codes": iron_panel_codes,
    }
