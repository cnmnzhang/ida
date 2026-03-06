"""
src/synth/build_patient_records.py

Builds a per-patient JSON for the Policy Builder investigation panel.

This version is optimized for larger cohorts by streaming Synthea CSVs in
chunks instead of loading observations.csv / conditions.csv fully into memory.
"""

import json
import sys
from math import sqrt
from pathlib import Path

import pandas as pd

# ── Repo layout ───────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src" / "synth"))

from parse_conditions import ANEMIA_SNOMED  # noqa: E402

# ── LOINC / WHO constants ─────────────────────────────────────────────────────
HB_LOINC = "718-7"
FERRITIN_LOINC = "2276-4"

HB_THRESHOLD_MALE = 13.0
HB_THRESHOLD_FEMALE = 12.0
HB_THRESHOLD_CHILD = 11.5

# Same defaults as setpoints_runner.py for the bayesian model.
_HB_POP_PRIOR = {"F": 13.8, "M": 15.2, "ALL": 14.3}
_BAYES_PRIOR_SIGMA = 2.0
_BAYES_OBS_SIGMA = 0.8


def _who_threshold(gender: str, age: float) -> float:
    if age < 15:
        return HB_THRESHOLD_CHILD
    return HB_THRESHOLD_MALE if gender == "M" else HB_THRESHOLD_FEMALE


def _age_at(birthdate: pd.Timestamp, ref: pd.Timestamp) -> float:
    if pd.isna(birthdate):
        return 99.0
    return (ref - birthdate).days / 365.25


def _filter_patients(csv_dir: Path, gender: str, min_age: int, max_age: int) -> pd.DataFrame:
    pts = pd.read_csv(
        csv_dir / "patients.csv",
        low_memory=False,
        usecols=["Id", "BIRTHDATE", "GENDER", "DEATHDATE"],
    )
    pts["BIRTHDATE"] = pd.to_datetime(pts["BIRTHDATE"], errors="coerce")
    pts["GENDER"] = pts["GENDER"].str.upper().str.strip()
    ref = pd.Timestamp.today()
    pts["age"] = pts["BIRTHDATE"].apply(lambda b: _age_at(b, ref))

    mask = (
        pts["DEATHDATE"].isna()
        & (pts["age"] >= min_age)
        & (pts["age"] <= max_age)
    )
    if gender:
        mask &= pts["GENDER"] == gender.upper()

    return pts[mask][["Id", "GENDER", "age"]].rename(columns={"Id": "PATIENT"})


def _bayesian_setpoint_history(hb_hist: list, gender: str) -> list:
    """
    Return per-reading predictive (mu, sigma) history.
    Matches conjugate Gaussian update used by setpoints_runner bayesian model.
    """
    if len(hb_hist) < 2:
        return []

    mu_post = float(_HB_POP_PRIOR.get(str(gender).upper(), _HB_POP_PRIOR["ALL"]))
    var_post = float(_BAYES_PRIOR_SIGMA) ** 2
    var_obs = float(_BAYES_OBS_SIGMA) ** 2

    history = []
    for row in hb_hist:
        x = float(row["value"])
        mu_pred = mu_post
        sigma_pred = sqrt(var_post + var_obs)
        history.append(
            {
                "date": row["date"],
                "mu": round(mu_pred, 3),
                "sigma": round(sigma_pred, 3),
            }
        )

        var_new = 1.0 / (1.0 / var_post + 1.0 / var_obs)
        mu_new = var_new * (mu_post / var_post + x / var_obs)
        mu_post = mu_new
        var_post = var_new

    return history


def _collect_observation_features(csv_dir: Path, patient_ids: set) -> tuple:
    """
    Stream observations.csv and collect:
      - hb_by_pt: {PATIENT: [{date, value}, ...]}
      - fer_counts: {PATIENT: ferritin_count}
    """
    hb_by_pt_raw = {}   # pid -> [(ts, value), ...]
    fer_counts = {}

    cols = ["DATE", "PATIENT", "CODE", "VALUE"]
    for chunk in pd.read_csv(csv_dir / "observations.csv", low_memory=False, usecols=cols, chunksize=250_000):
        chunk["CODE"] = chunk["CODE"].astype(str).str.strip()
        chunk = chunk[chunk["PATIENT"].isin(patient_ids)]
        if chunk.empty:
            continue

        hb = chunk[chunk["CODE"] == HB_LOINC][["PATIENT", "DATE", "VALUE"]].copy()
        if not hb.empty:
            hb["DATE"] = pd.to_datetime(hb["DATE"], errors="coerce", utc=True)
            hb["VALUE"] = pd.to_numeric(hb["VALUE"], errors="coerce")
            hb = hb.dropna(subset=["DATE", "VALUE"])
            if not hb.empty:
                hb = hb.sort_values(["PATIENT", "DATE"])
                for pid, grp in hb.groupby("PATIENT"):
                    rows = hb_by_pt_raw.setdefault(pid, [])
                    rows.extend(zip(grp["DATE"].tolist(), grp["VALUE"].tolist()))

        ferr = chunk[chunk["CODE"] == FERRITIN_LOINC][["PATIENT"]]
        if not ferr.empty:
            for pid, cnt in ferr.groupby("PATIENT").size().items():
                fer_counts[pid] = fer_counts.get(pid, 0) + int(cnt)

    hb_by_pt = {}
    for pid, vals in hb_by_pt_raw.items():
        vals.sort(key=lambda x: x[0])
        hb_by_pt[pid] = [
            {"date": dt.strftime("%Y-%m-%d"), "value": round(float(v), 2)}
            for dt, v in vals
        ]

    return hb_by_pt, fer_counts


def _collect_conditions(csv_dir: Path, patient_ids: set) -> tuple:
    """
    Stream conditions.csv and collect:
      - coded_anemia_ids: set(PATIENT)
      - cond_by_pt: {PATIENT: [{date, code, description}, ...]}
    """
    coded_anemia_ids = set()
    cond_by_pt = {}

    cols = ["START", "PATIENT", "CODE", "DESCRIPTION"]
    for chunk in pd.read_csv(csv_dir / "conditions.csv", low_memory=False, usecols=cols, chunksize=200_000):
        chunk["CODE"] = chunk["CODE"].astype(str).str.strip()
        chunk["DESCRIPTION"] = chunk["DESCRIPTION"].fillna("").astype(str).str.strip()
        chunk = chunk[chunk["PATIENT"].isin(patient_ids)]
        if chunk.empty:
            continue

        chunk["START"] = pd.to_datetime(chunk["START"], errors="coerce")

        anemia_mask = (
            chunk["CODE"].isin(ANEMIA_SNOMED)
            | chunk["DESCRIPTION"].str.contains(r"\banemia\b", case=False, regex=True)
        )
        if anemia_mask.any():
            coded_anemia_ids.update(chunk.loc[anemia_mask, "PATIENT"].dropna().tolist())

        for pid, grp in chunk.groupby("PATIENT"):
            rows = cond_by_pt.setdefault(pid, [])
            for _, row in grp.iterrows():
                rows.append(
                    {
                        "date": row["START"].strftime("%Y-%m-%d") if pd.notna(row["START"]) else None,
                        "code": row["CODE"],
                        "description": row["DESCRIPTION"],
                    }
                )

    for pid, rows in cond_by_pt.items():
        rows.sort(key=lambda r: (r["date"] is None, r["date"] or ""))

    return coded_anemia_ids, cond_by_pt


def build_records(
    csv_dir: Path,
    gender: str = "F",
    min_age: int = 18,
    max_age: int = 65,
) -> list:
    pts = _filter_patients(csv_dir, gender, min_age, max_age)
    patient_ids = set(pts["PATIENT"])

    print("  Streaming observations.csv …")
    hb_by_pt, fer_counts = _collect_observation_features(csv_dir, patient_ids)

    print("  Streaming conditions.csv …")
    coded_anemia_ids, cond_by_pt = _collect_conditions(csv_dir, patient_ids)

    records = []
    for _, row in pts.iterrows():
        pid = row["PATIENT"]
        gender_val = row["GENDER"]
        age = row["age"]
        thresh = _who_threshold(gender_val, age)

        hb_hist = hb_by_pt.get(pid, [])
        latest_hb = hb_hist[-1]["value"] if hb_hist else None
        lab_anemia = (latest_hb is not None) and (latest_hb < thresh)

        sp_history = _bayesian_setpoint_history(hb_hist, gender_val)
        if sp_history:
            setpoint = sp_history[-1]["mu"]
            setpoint_sigma = sp_history[-1]["sigma"]
        else:
            setpoint = None
            setpoint_sigma = None

        if setpoint is not None and latest_hb is not None:
            hb_drop = round(setpoint - latest_hb, 3)
            hb_drop_z = round(hb_drop / setpoint_sigma, 3) if setpoint_sigma else None
        else:
            hb_drop = None
            hb_drop_z = None

        records.append(
            {
                "id": pid,
                "gender": gender_val,
                "age": round(age, 1),
                "hb_history": hb_hist,
                "setpoint_history": sp_history,
                "latest_hb": latest_hb,
                "who_threshold": thresh,
                "lab_anemia": lab_anemia,
                "setpoint": setpoint,
                "setpoint_sigma": setpoint_sigma,
                "hb_drop": hb_drop,
                "hb_drop_z": hb_drop_z,
                "coded_anemia": pid in coded_anemia_ids,
                "ferritin_tests": fer_counts.get(pid, 0),
                "conditions": cond_by_pt.get(pid, []),
            }
        )

    return records


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Build per-patient JSON for Policy Builder")
    parser.add_argument("--n", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--gender", default="F")
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
