"""
src/synth/setpoints_runner.py

Adaptive setpoints computation for Synthea cohorts.

Adapted from the setpoints_runner pipeline.  Key changes vs the original:
- Column names match Synthea CSV layout (PATIENT / DATE / VALUE / CODE / GENDER)
- Model functions are implemented inline (no external opt_hyp / get dependencies)
- Default hyperparameters are embedded; no best-trial params DB required
- No distributed locking, ProcessPoolExecutor, or fcntl (single-machine use)

Public API
----------
build_sp_df(csv_dir, patient_ids, models, test_code)
    Load Synthea observations and compute per-measurement estimates for every
    (patient, model).  Returns a setpoints DataFrame.

get_one_setpoint(filtered_df, model, use_personalized_logic, min_isolated, ...)
    Select one stable setpoint estimate per (patient, test_code) from a
    setpoints DataFrame.

run_patient_from_dict(patient_df, patient_id, test_code, model, hp_dict)
    Run a single model on one patient's time-series.

run_single_patient(models_list, iso_dates, measurements, test_code, sex)
    Convenience wrapper: run all models for a single patient, return list of
    {model, mus, sigmas, ts} dicts.

generate_sp_df_from_dict(measurements_df, hp_dict, test_code, model)
    Generate setpoints DataFrame from a fixed hyperparameter dict.

generate_sp_df_from_params(measurements_df, params_df)
    Like generate_sp_df_from_dict but reads HPs from a params DataFrame
    (columns prefixed "hp:").

filter_sp_df(sp_df, min_measurements)
    Drop (patient, test_code, model) groups with too few rows or invalid CV.
"""

from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

# ── Column name constants (Synthea CSV layout) ────────────────────────────────

ID_COL          = "PATIENT"
TS_COL          = "DATE"
MEASUREMENT_COL = "VALUE"
TEST_CODE_COL   = "CODE"
SEX_COL         = "GENDER"
MU              = "mu"
SIGMA           = "sigma"
MUS_COL         = "mus"
SIGMAS_COL      = "sigmas"

HB_LOINC             = "718-7"
MIN_MEASUREMENTS     = 5
PARAMETERLESS_MODELS = {"simple_mean"}
MODEL_LIST           = ["bayesian", "kalman", "simple_mean"]

# ── Population priors for HB (g/dL)  ──────────────────────────────────────────
# Used when no per-patient prior_mean is supplied in hp_dict.
_HB_POP = {
    "F":   (13.8, 1.6),
    "M":   (15.2, 1.4),
    "ALL": (14.3, 1.8),
}


def _pop_prior(test_code: str, sex: str) -> tuple:
    """Return (mean, sigma) population prior for a given test code and sex."""
    if test_code == HB_LOINC:
        return _HB_POP.get(str(sex).upper(), _HB_POP["ALL"])
    return (0.0, 5.0)  # uninformative fallback


# ── Model implementations ──────────────────────────────────────────────────────

def _model_bayesian(
    measurements,
    prior_mean: Optional[float] = None,
    prior_sigma: float = 2.0,
    obs_sigma: float = 0.8,
):
    """
    Sequential conjugate Gaussian Bayesian update.

    mus[i]    = posterior mean after observing measurements[0..i-1]
                (predictive mean for measurements[i])
    sigmas[i] = predictive std at position i

    Hyperparameters
    ---------------
    prior_mean  : initial prior mean (defaults to population mean if None)
    prior_sigma : initial prior std in g/dL (default 2.0)
    obs_sigma   : assumed measurement noise std in g/dL (default 0.8)
    """
    measurements = np.asarray(measurements, dtype=float)
    n = len(measurements)
    if n == 0:
        return np.array([]), np.array([]), {}

    if prior_mean is None:
        prior_mean = float(measurements[0])

    mus    = np.empty(n)
    sigmas = np.empty(n)

    mu_post  = float(prior_mean)
    var_post = float(prior_sigma) ** 2
    var_obs  = float(obs_sigma) ** 2

    for i, x in enumerate(measurements):
        mus[i]    = mu_post
        sigmas[i] = np.sqrt(var_post + var_obs)  # predictive

        # Conjugate Gaussian posterior update
        var_new = 1.0 / (1.0 / var_post + 1.0 / var_obs)
        mu_new  = var_new * (mu_post / var_post + float(x) / var_obs)
        mu_post  = mu_new
        var_post = var_new

    return mus, sigmas, {}


def _model_kalman(
    measurements,
    prior_mean: Optional[float] = None,
    prior_var: float = 4.0,
    process_noise: float = 0.05,
    obs_noise: float = 0.64,
):
    """
    Scalar Kalman filter.

    mus[i]    = predicted mean before observing measurements[i]
    sigmas[i] = predicted std (including obs noise) before observing measurements[i]

    Hyperparameters
    ---------------
    prior_mean    : initial state estimate (defaults to population mean if None)
    prior_var     : initial state variance (default 4.0 → σ = 2 g/dL)
    process_noise : state transition noise variance Q (default 0.05)
    obs_noise     : observation noise variance R (default 0.64 → σ = 0.8 g/dL)
    """
    measurements = np.asarray(measurements, dtype=float)
    n = len(measurements)
    if n == 0:
        return np.array([]), np.array([]), {}

    if prior_mean is None:
        prior_mean = float(measurements[0])

    mus    = np.empty(n)
    sigmas = np.empty(n)

    mu  = float(prior_mean)
    var = float(prior_var)

    for i, x in enumerate(measurements):
        var_pred  = var + float(process_noise)
        mus[i]    = mu
        sigmas[i] = np.sqrt(var_pred + float(obs_noise))  # predictive

        K   = var_pred / (var_pred + float(obs_noise))
        mu  = mu + K * (float(x) - mu)
        var = (1.0 - K) * var_pred

    return mus, sigmas, {}


def _model_simple_mean(
    measurements,
    window: int = 5,
    min_sigma: float = 0.5,
):
    """
    Running mean ± std of up to `window` preceding readings.

    mus[0] = NaN (no preceding data).  Matches the original simple-mean
    setpoint logic already used in build_patient_records.py.
    """
    measurements = np.asarray(measurements, dtype=float)
    n = len(measurements)
    mus    = np.empty(n)
    sigmas = np.empty(n)

    for i in range(n):
        if i == 0:
            mus[i]    = np.nan
            sigmas[i] = min_sigma
        else:
            prev      = measurements[max(0, i - window):i]
            mus[i]    = float(np.mean(prev))
            ddof      = 1 if len(prev) > 1 else 0
            sigmas[i] = max(float(np.std(prev, ddof=ddof)), min_sigma)

    return mus, sigmas, {}


_MODEL_FUNCTIONS = {
    "bayesian":    _model_bayesian,
    "kalman":      _model_kalman,
    "simple_mean": _model_simple_mean,
}

# Default hyperparameters (no tuning required for basic use)
DEFAULT_HP = {
    "bayesian":    {"obs_sigma": 0.8, "prior_sigma": 2.0},
    "kalman":      {"process_noise": 0.05, "obs_noise": 0.64, "prior_var": 4.0},
    "simple_mean": {"window": 5},
}


def _get_model_function(model: str):
    fn = _MODEL_FUNCTIONS.get(model)
    if fn is None:
        raise ValueError(f"Unknown model: {model!r}. Available: {sorted(_MODEL_FUNCTIONS)}")
    return fn


# ── Patient-level inference ────────────────────────────────────────────────────

def run_patient_from_dict(patient_df, patient_id, test_code, model, hp_dict):
    """
    Run a single model on one patient's time-series measurements.

    Parameters
    ----------
    patient_df  : DataFrame with columns TS_COL, MEASUREMENT_COL, optionally SEX_COL.
                  Rows must already be sorted chronologically.
    patient_id  : identifier stored in the output ID_COL column
    test_code   : LOINC code string stored in the output TEST_CODE_COL column
    model       : model name (must be in MODEL_LIST)
    hp_dict     : hyperparameter dict passed to the model function

    Returns
    -------
    DataFrame with columns [ID_COL, TEST_CODE_COL, model, TS_COL, MU, SIGMA,
                             MEASUREMENT_COL, SEX_COL, "index"]
    or an empty DataFrame if there are fewer than 2 measurements.
    """
    ts           = patient_df[TS_COL].values
    measurements = patient_df[MEASUREMENT_COL].values.astype(float)

    if len(measurements) < 2:
        return pd.DataFrame()

    sex = "ALL"
    if SEX_COL in patient_df.columns:
        unique_sexes = patient_df[SEX_COL].dropna().unique()
        if len(unique_sexes) == 1:
            sex = str(unique_sexes[0])
        elif len(unique_sexes) > 1:
            print(f"Patient {patient_id} has multiple sex values: {unique_sexes}; using first")
            sex = str(unique_sexes[0])

    model_fn = _get_model_function(model)
    full_hp  = dict(hp_dict)

    # Inject sex-specific population prior if the model supports it and none was
    # supplied by the caller.
    if model in ("bayesian", "kalman") and "prior_mean" not in full_hp:
        full_hp["prior_mean"] = _pop_prior(test_code, sex)[0]

    try:
        mus, sigmas, _ = model_fn(measurements, **full_hp)
    except Exception as e:
        print(f"[ERROR] {model} failed for test_code={test_code} patient={patient_id}: {e}")
        return pd.DataFrame()

    df_out = pd.DataFrame({
        ID_COL:          patient_id,
        TEST_CODE_COL:   test_code,
        "model":         model,
        TS_COL:          ts,
        MU:              mus,
        SIGMA:           sigmas,
        MEASUREMENT_COL: measurements,
        SEX_COL:         sex,
    })
    df_out["index"] = df_out.index
    return df_out


# ── Cohort-level inference ─────────────────────────────────────────────────────

def generate_sp_df_from_dict(measurements_df, hp_dict, test_code, model):
    """
    Generate a setpoints DataFrame from a fixed hyperparameter dict.

    Parameters
    ----------
    measurements_df : DataFrame with columns [ID_COL, TS_COL, MEASUREMENT_COL,
                                              TEST_CODE_COL, optionally SEX_COL].
                      Must be sorted by (patient, date) before calling.
    hp_dict         : hyperparameter dict for the model
    test_code       : LOINC code to restrict to
    model           : model name

    Returns
    -------
    Concatenated setpoints DataFrame (one row per patient × measurement).
    """
    df_test       = measurements_df[measurements_df[TEST_CODE_COL] == test_code].copy()
    patient_groups = list(df_test.groupby(ID_COL))

    results = [
        run_patient_from_dict(df, pid, test_code, model, hp_dict)
        for pid, df in patient_groups
    ]
    valid = [r for r in results if r is not None and not r.empty]
    if not valid:
        return pd.DataFrame()
    return pd.concat(valid, ignore_index=True)


def generate_sp_df_from_params(measurements_df, params_df):
    """
    Run inference for all (model, test_code) combinations defined in params_df.

    params_df must have columns: ["model", TEST_CODE_COL] plus optional
    "hp:<name>" columns for hyperparameters (e.g. "hp:obs_sigma").

    Returns
    -------
    Combined setpoints DataFrame.
    """
    hp_cols     = [c for c in params_df.columns if c.startswith("hp:")]
    model_hp_df = params_df[["model", TEST_CODE_COL] + hp_cols].drop_duplicates()

    rows = []
    for (model, test_code), hp_row in model_hp_df.groupby(["model", TEST_CODE_COL]):
        hps = {
            k.replace("hp:", ""): v
            for k, v in hp_row.iloc[0].items()
            if k.startswith("hp:") and pd.notna(v)
        }
        sp = generate_sp_df_from_dict(measurements_df, hps, test_code, model)
        if not sp.empty:
            rows.append(sp)

    if not rows:
        return pd.DataFrame()

    sp_df = pd.concat(rows, ignore_index=True)
    if hp_cols:
        sp_df = sp_df.merge(model_hp_df, on=["model", TEST_CODE_COL], how="left")
    return sp_df


def run_single_patient(models_list, iso_dates, measurements, test_code, sex="ALL"):
    """
    Run all models for a single patient using default hyperparameters.

    Parameters
    ----------
    models_list  : list of model names
    iso_dates    : list/array of date strings or Timestamps (chronological)
    measurements : list/array of measurement values (same length as iso_dates)
    test_code    : LOINC code string
    sex          : patient sex ("F", "M", "ALL")

    Returns
    -------
    list of dicts: [{"model": str, MUS_COL: array, SIGMAS_COL: array, TS_COL: array}, ...]

    Sex comes from the caller; the function selects the matching population prior
    for each model automatically.
    """
    patient_df = pd.DataFrame({
        TS_COL:          list(iso_dates),
        MEASUREMENT_COL: list(measurements),
        TEST_CODE_COL:   test_code,
        SEX_COL:         sex,
    })

    model_setpoints = []
    for model in models_list:
        hp = DEFAULT_HP.get(model, {}).copy()
        df = run_patient_from_dict(patient_df, "0", test_code, model, hp)
        if df.empty:
            continue
        model_setpoints.append({
            "model":    model,
            MUS_COL:    df[MU].values,
            SIGMAS_COL: df[SIGMA].values,
            TS_COL:     df[TS_COL].values,
        })
    return model_setpoints


# ── Setpoint selection ─────────────────────────────────────────────────────────

def get_one_setpoint(
    filtered_df,
    use_personalized_logic=True,
    model="bayesian",
    min_isolated=MIN_MEASUREMENTS,
    min_dts=None,
    max_dts=None,
):
    """
    Get a stable setpoint estimate per (patient, test_code) from a setpoints DataFrame.

    Parameters
    ----------
    filtered_df           : setpoints DataFrame (output of generate_sp_df_* functions)
    use_personalized_logic: if True, selects the row at index == min_isolated
                            (personalized: stable estimate after exactly k readings).
                            if False, selects the last row with index >= min_isolated
                            (uses the most-recent posterior estimate).
    model                 : model name to filter on
    min_isolated          : index threshold for setpoint stability (default: MIN_MEASUREMENTS)
    min_dts / max_dts     : optional date range filters applied to TS_COL

    Returns
    -------
    DataFrame with exactly one row per (patient, test_code), or empty DataFrame.

    Mirrors the original get_one_setpoint() semantics:
    - IMPORTANT: some pipelines can produce duplicate rows at the same index
      (tied timestamps, repeated measurements, or duplicated upstream rows).
      We resolve this deterministically by:
        1) filtering to index == min_isolated (or >= for non-personalized)
        2) sorting by (ID, test_code, index, TS)
        3) keeping the last row per (ID, test_code)
    """
    sp = filtered_df[filtered_df["model"] == model].copy()
    sp[TS_COL] = pd.to_datetime(sp[TS_COL], utc=True, errors="coerce")

    if min_dts is not None:
        min_ts = pd.Timestamp(min_dts, tz="UTC") if pd.Timestamp(min_dts).tzinfo is None else pd.Timestamp(min_dts)
        sp = sp[sp[TS_COL] >= min_ts]
    if max_dts is not None:
        max_ts = pd.Timestamp(max_dts, tz="UTC") if pd.Timestamp(max_dts).tzinfo is None else pd.Timestamp(max_dts)
        sp = sp[sp[TS_COL] <= max_ts]

    if use_personalized_logic:
        # k-th estimate: personalized setpoint after min_isolated measurements
        sp = (
            sp[sp["index"] == min_isolated]
            .sort_values([ID_COL, TEST_CODE_COL, "index", TS_COL])
            .groupby([ID_COL, TEST_CODE_COL], as_index=False)
            .tail(1)
            .reset_index(drop=True)
        )
    else:
        # Most-recent estimate with sufficient history
        sp = (
            sp[sp["index"] >= min_isolated]
            .sort_values([ID_COL, TEST_CODE_COL, "index", TS_COL])
            .groupby([ID_COL, TEST_CODE_COL], as_index=False)
            .tail(1)
            .reset_index(drop=True)
        )

    if sp.empty:
        print(
            f"No setpoints found for model='{model}', min_isolated={min_isolated}, "
            f"min_dts={min_dts}, max_dts={max_dts}."
        )
        return pd.DataFrame()

    max_dupes = sp.groupby([ID_COL, TEST_CODE_COL]).size().max()
    assert max_dupes <= 1, (
        f"Expected ≤1 setpoint per (patient, test_code); got max group size={max_dupes}."
    )
    return sp


# ── Filtering ──────────────────────────────────────────────────────────────────

def filter_sp_df(sp_df, min_measurements=MIN_MEASUREMENTS) -> pd.DataFrame:
    """
    Filter a setpoints DataFrame to patients with enough history.

    Steps
    -----
    1. Require ≥ min_measurements rows per (patient, test_code, model).
    2. Drop (patient, test_code, model) groups that have invalid CV
       (sigma/mu outside [0, 1]) at any index ≥ 3.

    Returns
    -------
    Filtered DataFrame (reset index).
    """
    print(f"[filter_sp_df] Min-measurements filter (min={min_measurements}):")
    print(f"  Before: {sp_df[ID_COL].nunique():,} patients")

    grouped    = sp_df.groupby([ID_COL, TEST_CODE_COL, "model"])
    sp_f       = grouped.filter(lambda x: len(x) >= min_measurements)

    print(f"  After:  {sp_f[ID_COL].nunique():,} patients")

    if MU in sp_f.columns and SIGMA in sp_f.columns:
        sp_f        = sp_f.copy()
        valid_mu    = sp_f[MU].replace(0, np.nan)
        sp_f["cv"]  = sp_f[SIGMA] / valid_mu

        before_cv   = sp_f.groupby([ID_COL, TEST_CODE_COL, "model"]).ngroups
        invalid     = sp_f[
            (sp_f["index"] >= 3) & ~((sp_f["cv"] >= 0) & (sp_f["cv"] <= 1))
        ][[ID_COL, TEST_CODE_COL, "model"]].drop_duplicates()

        sp_f = sp_f.merge(
            invalid.assign(_flag=True),
            on=[ID_COL, TEST_CODE_COL, "model"],
            how="left",
        )
        sp_f = sp_f[sp_f["_flag"].isna()].drop(columns=["_flag"])

        after_cv = sp_f.groupby([ID_COL, TEST_CODE_COL, "model"]).ngroups
        print(f"  CV filter removed {before_cv - after_cv} (patient, test_code, model) combos")

    return sp_f.reset_index(drop=True)


# ── Convenience: build full setpoints DataFrame from Synthea CSV directory ─────

def build_sp_df(
    csv_dir: Path,
    patient_ids: Optional[set] = None,
    models: Optional[list] = None,
    test_code: str = HB_LOINC,
) -> pd.DataFrame:
    """
    Build a setpoints DataFrame from a Synthea csv/ directory.

    Loads observations.csv (and patients.csv for sex), restricts to
    `test_code`, and runs all requested models for every patient.

    Parameters
    ----------
    csv_dir     : path to Synthea csv/ directory
    patient_ids : optional set of patient UUIDs to restrict to
    models      : list of model names (default: MODEL_LIST)
    test_code   : LOINC code to process (default: HB_LOINC = "718-7")

    Returns
    -------
    Setpoints DataFrame (one row per patient × time-step × model).
    """
    if models is None:
        models = MODEL_LIST

    obs = pd.read_csv(
        csv_dir / "observations.csv",
        low_memory=False,
        usecols=["DATE", "PATIENT", "CODE", "VALUE"],
    )
    obs["CODE"]  = obs["CODE"].astype(str).str.strip()
    obs["DATE"]  = pd.to_datetime(obs["DATE"], errors="coerce", utc=True)
    obs["VALUE"] = pd.to_numeric(obs["VALUE"], errors="coerce")
    obs = obs.rename(columns={"DATE": TS_COL, "PATIENT": ID_COL, "VALUE": MEASUREMENT_COL, "CODE": TEST_CODE_COL})

    # Join GENDER for sex-specific priors
    pts = pd.read_csv(csv_dir / "patients.csv", low_memory=False, usecols=["Id", "GENDER"])
    pts = pts.rename(columns={"Id": ID_COL})
    pts["GENDER"] = pts["GENDER"].str.upper().str.strip()
    obs = obs.merge(pts.rename(columns={"GENDER": SEX_COL}), on=ID_COL, how="left")

    if patient_ids is not None:
        obs = obs[obs[ID_COL].isin(patient_ids)]

    obs = obs[obs[TEST_CODE_COL] == test_code].dropna(subset=[MEASUREMENT_COL])
    obs = obs.sort_values([ID_COL, TS_COL]).reset_index(drop=True)

    rows = []
    for model in models:
        hp = DEFAULT_HP.get(model, {}).copy()
        sp = generate_sp_df_from_dict(obs, hp, test_code, model)
        if not sp.empty:
            rows.append(sp)

    if not rows:
        return pd.DataFrame()
    return pd.concat(rows, ignore_index=True)
