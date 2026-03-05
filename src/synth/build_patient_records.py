"""
src/synth/build_patient_records.py

Builds a per-patient JSON for the Policy Builder investigation panel.

For each patient in the filtered cohort (F 18-65, Washington, seed=1, n=5000):
  - hb_history       : [{date, value}] sorted chronologically
  - latest_hb        : most-recent HB reading (null if none)
  - who_threshold    : WHO cutoff for this patient
  - lab_anemia       : latest_hb < who_threshold
  - setpoint         : mean of up to 5 readings *preceding* the most-recent one (null if < 2 readings)
  - hb_drop          : setpoint - latest_hb (positive = dropped; null if setpoint is null)
  - coded_anemia     : has any anemia dx code on record
  - ferritin_tests   : count of ferritin observations
  - conditions       : [{date, code, description}] for ALL conditions (not just anemia)

Output: data/synth_runs/{n}_{seed}/patients_{gender}_{min_age}_{max_age}.json
"""

import json
import sys
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

# ── Repo layout ───────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src" / "synth"))

from parse_conditions import ANEMIA_SNOMED  # noqa: E402

# ── LOINC / WHO constants ─────────────────────────────────────────────────────
HB_LOINC       = "718-7"
FERRITIN_LOINC = "2276-4"

HB_THRESHOLD_MALE   = 13.0
HB_THRESHOLD_FEMALE = 12.0
HB_THRESHOLD_CHILD  = 11.5


def _who_threshold(gender: str, age: float) -> float:
    if age < 15:
        return HB_THRESHOLD_CHILD
    return HB_THRESHOLD_MALE if gender == "M" else HB_THRESHOLD_FEMALE


def _age_at(birthdate: pd.Timestamp, ref: pd.Timestamp) -> float:
    if pd.isna(birthdate):
        return 99.0
    return (ref - birthdate).days / 365.25


def _filter_patients(csv_dir: Path, gender: str, min_age: int, max_age: int) -> pd.DataFrame:
    pts = pd.read_csv(csv_dir / "patients.csv", low_memory=False,
                      usecols=["Id", "BIRTHDATE", "GENDER", "DEATHDATE"])
    pts["BIRTHDATE"] = pd.to_datetime(pts["BIRTHDATE"], errors="coerce")
    pts["GENDER"]    = pts["GENDER"].str.upper().str.strip()
    ref              = pd.Timestamp.today()
    pts["age"]       = pts["BIRTHDATE"].apply(lambda b: _age_at(b, ref))

    mask = (
        pts["DEATHDATE"].isna()
        & (pts["age"] >= min_age)
        & (pts["age"] <= max_age)
    )
    if gender:
        mask &= pts["GENDER"] == gender.upper()

    return pts[mask][["Id", "GENDER", "age"]].rename(columns={"Id": "PATIENT"})


def _compute_setpoint(values: list) -> Optional[float]:
    """Mean of up to 5 readings preceding the last one."""
    if len(values) < 2:
        return None
    preceding = values[:-1][-5:]
    return float(np.mean(preceding))


def build_records(
    csv_dir: Path,
    gender: str = "F",
    min_age: int = 18,
    max_age: int = 65,
) -> list:
    pts = _filter_patients(csv_dir, gender, min_age, max_age)
    patient_ids = set(pts["PATIENT"])

    # ── HB observations ───────────────────────────────────────────────────────
    obs = pd.read_csv(csv_dir / "observations.csv", low_memory=False,
                      usecols=["DATE", "PATIENT", "CODE", "VALUE"])
    obs["CODE"]  = obs["CODE"].astype(str).str.strip()
    obs["DATE"]  = pd.to_datetime(obs["DATE"], errors="coerce", utc=True)
    obs["VALUE"] = pd.to_numeric(obs["VALUE"], errors="coerce")
    obs          = obs[obs["PATIENT"].isin(patient_ids)]

    hb_obs  = obs[obs["CODE"] == HB_LOINC].dropna(subset=["VALUE"]).copy()
    fer_obs = obs[obs["CODE"] == FERRITIN_LOINC]

    # ferritin count per patient
    fer_counts = fer_obs.groupby("PATIENT").size().to_dict()

    # HB history per patient (sorted)
    hb_by_pt = {}
    for pid, grp in hb_obs.sort_values("DATE").groupby("PATIENT"):
        hb_by_pt[pid] = [
            {"date": row["DATE"].strftime("%Y-%m-%d"), "value": round(float(row["VALUE"]), 2)}
            for _, row in grp.iterrows()
        ]

    # ── Conditions ────────────────────────────────────────────────────────────
    cond = pd.read_csv(csv_dir / "conditions.csv", low_memory=False,
                       usecols=["START", "PATIENT", "CODE", "DESCRIPTION"])
    cond["CODE"]        = cond["CODE"].astype(str).str.strip()
    cond["DESCRIPTION"] = cond["DESCRIPTION"].fillna("").str.strip()
    cond["START"]       = pd.to_datetime(cond["START"], errors="coerce")
    cond                = cond[cond["PATIENT"].isin(patient_ids)]

    anemia_mask = (
        cond["CODE"].isin(ANEMIA_SNOMED)
        | cond["DESCRIPTION"].str.contains(r"\banemia\b", case=False, regex=True)
    )
    coded_anemia_ids = set(cond.loc[anemia_mask, "PATIENT"].dropna())

    cond_by_pt = {}
    for pid, grp in cond.sort_values("START").groupby("PATIENT"):
        cond_by_pt[pid] = [
            {
                "date":        row["START"].strftime("%Y-%m-%d") if pd.notna(row["START"]) else None,
                "code":        row["CODE"],
                "description": row["DESCRIPTION"],
            }
            for _, row in grp.iterrows()
        ]

    # ── Assemble per-patient records ──────────────────────────────────────────
    ref = pd.Timestamp.today()
    records = []

    for _, row in pts.iterrows():
        pid    = row["PATIENT"]
        gender_val = row["GENDER"]
        age    = row["age"]
        thresh = _who_threshold(gender_val, age)

        hb_hist = hb_by_pt.get(pid, [])
        hb_vals = [h["value"] for h in hb_hist]

        latest_hb = hb_vals[-1] if hb_vals else None
        setpoint  = _compute_setpoint(hb_vals)
        hb_drop   = round(setpoint - latest_hb, 3) if (setpoint is not None and latest_hb is not None) else None
        lab_anemia = (latest_hb is not None) and (latest_hb < thresh)

        records.append({
            "id":            pid,
            "gender":        gender_val,
            "age":           round(age, 1),
            "hb_history":    hb_hist,
            "latest_hb":     latest_hb,
            "who_threshold": thresh,
            "lab_anemia":    lab_anemia,
            "setpoint":      round(setpoint, 3) if setpoint is not None else None,
            "hb_drop":       hb_drop,
            "coded_anemia":  pid in coded_anemia_ids,
            "ferritin_tests": fer_counts.get(pid, 0),
            "conditions":    cond_by_pt.get(pid, []),
        })

    return records


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Build per-patient JSON for Policy Builder")
    parser.add_argument("--n",       type=int, default=5000)
    parser.add_argument("--seed",    type=int, default=1)
    parser.add_argument("--gender",  default="F")
    parser.add_argument("--min-age", type=int, default=18)
    parser.add_argument("--max-age", type=int, default=65)
    args = parser.parse_args()

    csv_dir = REPO_ROOT / "data" / "synth_runs" / f"{args.n}_{args.seed}" / "csv"
    if not csv_dir.exists():
        print(f"ERROR: CSV dir not found: {csv_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"Building patient records from {csv_dir} …")
    records = build_records(csv_dir, args.gender, args.min_age, args.max_age)
    print(f"  {len(records)} patients")

    out_name = f"patients_{args.gender}_{args.min_age}_{args.max_age}.json"
    out_path = csv_dir.parent / out_name

    with open(out_path, "w") as f:
        json.dump(records, f, separators=(",", ":"))

    size_kb = out_path.stat().st_size / 1024
    print(f"  Wrote {out_path}  ({size_kb:.1f} KB)")


if __name__ == "__main__":
    main()
