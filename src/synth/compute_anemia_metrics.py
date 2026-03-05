"""
src/synth/compute_anemia_metrics.py

Combines condition and observation outputs into the final anemia metrics dict.

Diagnostic gap:
  patients whose most-recent HB meets WHO lab-anemia criteria
  but who have NO recorded anemia diagnosis in conditions.csv.
"""

from datetime import datetime, timezone
from typing import Optional


def compute_anemia_metrics(
    n_patients_requested: int,
    location: str,
    seed: int,
    patients_generated: int,
    cohort_size: int,
    cond: dict,
    obs: dict,
    cohort_filter: Optional[dict] = None,
) -> dict:
    """
    Parameters
    ----------
    n_patients_requested : int
    location             : str
    seed                 : int
    patients_generated   : int    — total patients Synthea produced
    cohort_size          : int    — patients after applying gender/age filter
    cond                 : output of parse_conditions.parse_conditions()
    obs                  : output of parse_observations.parse_observations()
    cohort_filter        : dict describing the applied filter, e.g.
                           {"gender": "F", "min_age": 18, "max_age": 65}

    Returns
    -------
    dict matching the JSON summary schema.
    Prevalences use cohort_size as denominator.
    """
    anemia_ids   = cond["anemia_patient_ids"]
    ida_ids      = cond["ida_patient_ids"]
    lab_anemia   = obs["lab_anemia_ids"]

    # Diagnostic gap: lab-confirmed anemia with no diagnosis on record
    gap_ids      = lab_anemia - anemia_ids

    denom        = cohort_size if cohort_size else 1
    prevalence   = len(lab_anemia) / denom
    gap_rate     = len(gap_ids)    / denom

    return {
        "location":           location,
        "seed":               seed,
        "patients_requested": n_patients_requested,
        "patients_generated": patients_generated,
        "cohort_size":        cohort_size,
        "cohort_filter":      cohort_filter or {},
        "generated_at":       datetime.now(timezone.utc).isoformat(),

        "labs": {
            "hb_observations":  obs["hb_observations"],
            "patients_with_hb": obs["patients_with_hb"],
            "hb_mean":          obs["hb_mean"],
            "hb_std":           obs["hb_std"],
            "hb_histogram":     obs["hb_histogram"],
            "ferritin_present": obs["ferritin_present"],
            "ferritin_count":   obs["ferritin_count"],
            "iron_panel_codes": obs["iron_panel_codes"],
        },

        "diagnoses": {
            "anemia_dx_count": len(anemia_ids),
            "ida_dx_count":    len(ida_ids),
        },

        "lab_anemia": {
            "lab_anemia_count":      len(lab_anemia),
            "lab_anemia_prevalence": round(prevalence, 4),
        },

        "diagnostic_gap": {
            "lab_anemia_without_dx": len(gap_ids),
            "gap_rate":              round(gap_rate, 4),
        },
    }
