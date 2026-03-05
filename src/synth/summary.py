"""
src/synth/summary.py

Computes a summary dict from parsed Synthea cohort data.
"""

from datetime import datetime, timezone

import numpy as np


def compute_summary(
    cohort_size: int,
    hb_values: list[float],
    ida_patient_ids: set[str],
    n_patients: int,
    seed: int,
) -> dict:
    """
    Compute IDA prevalence and HB statistics from parsed Synthea data.
    """
    ida_dx_count = len(ida_patient_ids)
    ida_prevalence = ida_dx_count / cohort_size if cohort_size > 0 else 0.0

    if hb_values:
        arr = np.array(hb_values, dtype=float)
        hb_mean = float(np.mean(arr))
        hb_std = float(np.std(arr, ddof=1)) if len(arr) > 1 else 0.0
        counts, edges = np.histogram(arr, bins=10)
        hb_hist = [
            {"bin_start": float(edges[i]), "bin_end": float(edges[i + 1]), "count": int(counts[i])}
            for i in range(len(counts))
        ]
    else:
        hb_mean = None
        hb_std = None
        hb_hist = []

    return {
        "n_patients_requested": n_patients,
        "seed": seed,
        "cohort_size": cohort_size,
        "location": "Washington",
        "ida_dx_count": ida_dx_count,
        "ida_prevalence": round(ida_prevalence, 4),
        "hb_mean": round(hb_mean, 3) if hb_mean is not None else None,
        "hb_std": round(hb_std, 3) if hb_std is not None else None,
        "hb_observation_count": len(hb_values),
        "hb_hist": hb_hist,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
