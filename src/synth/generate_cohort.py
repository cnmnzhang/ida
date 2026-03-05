"""
src/synth/generate_cohort.py

CLI entry point for the synthetic cohort pipeline.

Usage:
    python src/synth/generate_cohort.py --location Washington --n 5000 --seed 1
    python src/synth/generate_cohort.py --n 5000 --seed 1 --gender F --min-age 18 --max-age 65

Steps:
  1. Run Synthea (skipped if cached)
  2. Filter patients to cohort (gender, age window)
  3. Parse conditions  → anemia / IDA patient sets
  4. Parse observations → HB stats, WHO lab-anemia patient set
  5. Compute metrics   → diagnostic gap, summary dict
  6. Save JSON         → data/synth_runs/{n}_{seed}/cohort_summary_{filter}.json
  7. Print inspection report
"""

import argparse
import json
import sys
from pathlib import Path

# ── Path setup ────────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from synth import runner                        # noqa: E402
from synth.parse_conditions  import parse_conditions   # noqa: E402
from synth.parse_observations import parse_observations # noqa: E402
from synth.compute_anemia_metrics import compute_anemia_metrics  # noqa: E402

import pandas as pd  # noqa: E402
from typing import Optional  # noqa: E402


# ── Helpers ───────────────────────────────────────────────────────────────────

def _bar(count: int, total: int, width: int = 28) -> str:
    filled = round(count / total * width) if total else 0
    return "█" * filled + "░" * (width - filled)


def print_inspection_report(
    outdir: Path,
    cond: dict,
    obs: dict,
    metrics: dict,
) -> None:
    pts_gen   = metrics["patients_generated"]
    cohort_n  = metrics["cohort_size"]
    lab_n     = metrics["lab_anemia"]["lab_anemia_count"]
    dx_n      = metrics["diagnoses"]["anemia_dx_count"]
    ida_n     = metrics["diagnoses"]["ida_dx_count"]
    gap_n     = metrics["diagnostic_gap"]["lab_anemia_without_dx"]
    filt      = metrics.get("cohort_filter", {})

    sep = "─" * 64

    print(f"\n{'═' * 64}")
    print(f"  SYNTHEA COHORT INSPECTION REPORT")
    print(f"  Location : {metrics['location']}   Seed : {metrics['seed']}")
    print(f"  Synthea  : {pts_gen:,} generated  ({metrics['patients_requested']:,} requested)")
    if filt:
        gender_str = filt.get("gender", "all")
        print(f"  Filter   : gender={gender_str}  age {filt.get('min_age', 0)}–{filt.get('max_age', '∞')}")
    print(f"  Cohort   : {cohort_n:,} patients after filter")
    print(f"{'═' * 64}\n")

    # ── Diagnosis inventory ───────────────────────────────────────────────────
    print("1. ANEMIA-RELATED SNOMED CODES OBSERVED")
    print(sep)
    if cond["observed_codes"].empty:
        print("  (none found)")
    else:
        for _, row in cond["observed_codes"].iterrows():
            bar = _bar(row["patient_count"], cohort_n)
            print(f"  {row['CODE']:>12}  {bar}  {row['patient_count']:>4} pts"
                  f"  {row['DESCRIPTION']}")
    print()

    # ── IDA specific ──────────────────────────────────────────────────────────
    print("2. IRON DEFICIENCY ANEMIA (IDA)")
    print(sep)
    if ida_n > 0:
        print(f"  IDA diagnoses found:  {ida_n} patients")
    else:
        print("  IDA diagnoses: NONE — Synthea's generic anemia module uses SNOMED")
        print("  271737000 ('Anemia (disorder)') rather than IDA-specific codes.")
        print("  IDA codes (87522002 / 234347009) appear only when Synthea's")
        print("  iron_deficiency_anemia sub-module fires (low probability by default).")
    print()

    # ── Ferritin ──────────────────────────────────────────────────────────────
    print("3. FERRITIN LABS")
    print(sep)
    if obs["ferritin_present"]:
        print(f"  Ferritin (LOINC 2276-4): {obs['ferritin_count']:,} observations  ✓")
        print("  Note: Synthea DOES generate ferritin in the iron-panel CBC when the")
        print("  anemia module fires. This contradicts older README claims.")
    else:
        print("  Ferritin (LOINC 2276-4): NOT PRESENT in this cohort")
    print()

    # ── Iron panel ────────────────────────────────────────────────────────────
    print("4. IRON PANEL LABS OBSERVED")
    print(sep)
    for entry in obs["iron_panel_codes"]:
        print(f"  {entry['CODE']:>10}  {entry['DESCRIPTION']}")
    if not obs["iron_panel_codes"]:
        print("  (none)")
    print()

    # ── HB stats ─────────────────────────────────────────────────────────────
    print("5. HEMOGLOBIN STATISTICS  (LOINC 718-7)")
    print(sep)
    print(f"  Observations : {obs['hb_observations']:,}")
    print(f"  Patients     : {obs['patients_with_hb']:,}")
    print(f"  Mean HB      : {obs['hb_mean']:.2f} g/dL")
    print(f"  Std dev      : {obs['hb_std']:.2f} g/dL")
    print()
    print("  Distribution (all HB readings):")
    max_count = max(b["count"] for b in obs["hb_histogram"]) if obs["hb_histogram"] else 1
    for b in obs["hb_histogram"]:
        bar = _bar(b["count"], max_count)
        print(f"  {b['bin_start']:5.1f}–{b['bin_end']:4.1f}  {bar}  {b['count']:>4}")
    print()

    # ── Lab anemia ────────────────────────────────────────────────────────────
    print("6. LAB-DEFINED ANEMIA  (WHO thresholds, most-recent HB per patient)")
    print(sep)
    print(f"  Male threshold   < 13.0 g/dL")
    print(f"  Female threshold < 12.0 g/dL")
    print(f"  Child threshold  < 11.5 g/dL  (age < 15)")
    print()
    bar = _bar(lab_n, cohort_n)
    print(f"  Lab anemia : {bar}  {lab_n} / {cohort_n}  "
          f"({metrics['lab_anemia']['lab_anemia_prevalence']:.1%})")
    bar2 = _bar(dx_n, cohort_n)
    print(f"  Dx anemia  : {bar2}  {dx_n} / {cohort_n}  "
          f"({dx_n / cohort_n:.1%})")
    print()

    # ── Diagnostic gap ────────────────────────────────────────────────────────
    print("7. DIAGNOSTIC GAP")
    print(sep)
    bar = _bar(gap_n, cohort_n)
    print(f"  Lab anemia WITHOUT any anemia diagnosis:")
    print(f"  {bar}  {gap_n} / {cohort_n}  "
          f"({metrics['diagnostic_gap']['gap_rate']:.1%})")
    print()
    print("  Interpretation: these patients have HB below WHO thresholds")
    print("  at their most recent measurement but carry no anemia diagnosis")
    print("  code in conditions.csv.  They represent a plausible synthetic")
    print("  underdiagnosis signal — though Synthea's coding is not a direct")
    print("  model of real clinical documentation practices.")
    print(f"\n{'═' * 64}\n")


# ── Main ──────────────────────────────────────────────────────────────────────

def _filter_patients(csv_dir: Path, gender: Optional[str], min_age: int, max_age: int) -> tuple:
    """
    Load patients.csv, apply gender and age filters, return (patient_id_set, total_generated).
    gender: "F", "M", or None (no filter).
    Age is computed from BIRTHDATE relative to today.
    """
    pts = pd.read_csv(csv_dir / "patients.csv", low_memory=False,
                      usecols=["Id", "BIRTHDATE", "GENDER", "DEATHDATE"])
    total = len(pts)

    pts["BIRTHDATE"] = pd.to_datetime(pts["BIRTHDATE"], errors="coerce")
    pts["age"] = (pd.Timestamp.today() - pts["BIRTHDATE"]).dt.days / 365.25
    pts["GENDER"] = pts["GENDER"].str.upper().str.strip()

    mask = (pts["age"] >= min_age) & (pts["age"] <= max_age) & pts["DEATHDATE"].isna()
    if gender:
        mask &= pts["GENDER"] == gender.upper()

    filtered = pts.loc[mask, "Id"]
    return set(filtered), total


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate and analyse a Synthea synthetic cohort for anemia metrics."
    )
    parser.add_argument("--location", default="Washington",
                        help="US state name passed to Synthea (default: Washington)")
    parser.add_argument("--n",        type=int, default=5000,
                        help="Number of patients to request (default: 5000)")
    parser.add_argument("--seed",     type=int, default=1,
                        help="Synthea random seed (default: 1)")
    parser.add_argument("--gender",   default="F",
                        help="Restrict analysis to gender M/F, or '' for all (default: F)")
    parser.add_argument("--min-age",  type=int, default=18,
                        help="Minimum age inclusive (default: 18)")
    parser.add_argument("--max-age",  type=int, default=65,
                        help="Maximum age inclusive (default: 65)")
    parser.add_argument("--skip-synthea", action="store_true",
                        help="Skip Synthea run even if cache is missing (parse existing CSV)")
    args = parser.parse_args()

    gender_arg = args.gender.upper() if args.gender else None

    # ── Step 1: Run Synthea ───────────────────────────────────────────────────
    if args.skip_synthea:
        outdir = REPO_ROOT / "data" / "synth_runs" / f"{args.n}_{args.seed}"
        if not (outdir / "csv" / "patients.csv").exists():
            print(f"ERROR: --skip-synthea set but no CSV found at {outdir}/csv/", file=sys.stderr)
            sys.exit(1)
        print(f"[skip-synthea] Using existing CSV at {outdir}")
    else:
        print(f"[1/6] Running Synthea  (n={args.n}, seed={args.seed}, location={args.location})")
        print("      (cached runs return immediately)")
        outdir = runner.run_synthea(args.n, args.seed)
        print(f"      Output: {outdir}")

    csv_dir = outdir / "csv"

    # ── Step 2: Filter patients ───────────────────────────────────────────────
    gender_label = gender_arg or "all"
    print(f"[2/6] Filtering patients  "
          f"(gender={gender_label}, age {args.min_age}–{args.max_age})")
    patient_ids, patients_generated = _filter_patients(
        csv_dir, gender_arg, args.min_age, args.max_age
    )
    cohort_size = len(patient_ids)
    print(f"      {cohort_size:,} of {patients_generated:,} patients match filter")

    cohort_filter = {"gender": gender_label, "min_age": args.min_age, "max_age": args.max_age}

    # ── Step 3: Parse conditions ──────────────────────────────────────────────
    print(f"[3/6] Parsing conditions.csv")
    cond = parse_conditions(csv_dir, patient_ids=patient_ids)

    # ── Step 4: Parse observations ────────────────────────────────────────────
    print(f"[4/6] Parsing observations.csv")
    obs = parse_observations(csv_dir, patient_ids=patient_ids)

    # ── Step 5: Compute metrics ───────────────────────────────────────────────
    print(f"[5/6] Computing anemia metrics")
    metrics = compute_anemia_metrics(
        n_patients_requested=args.n,
        location=args.location,
        seed=args.seed,
        patients_generated=patients_generated,
        cohort_size=cohort_size,
        cond=cond,
        obs=obs,
        cohort_filter=cohort_filter,
    )

    # ── Step 6: Save JSON ─────────────────────────────────────────────────────
    fname = f"cohort_summary_{gender_label}_{args.min_age}_{args.max_age}.json"
    out_path = outdir / fname
    with open(out_path, "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"[6/6] Saved summary → {out_path}")

    # ── Step 7: Print inspection report ──────────────────────────────────────
    print_inspection_report(outdir, cond, obs, metrics)


if __name__ == "__main__":
    main()
