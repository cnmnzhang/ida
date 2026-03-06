"""
apps/api/main.py

FastAPI backend for the synthetic cohort and policy builder features.
"""

import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Ensure src/ is importable when running from repo root
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from synth import parse, runner, summary  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]

PB_SETPOINT_THRESHOLDS = (0.5, 1.0, 1.5, 2.0, 2.5, 3.0)
PB_HB_BINS = (
    {"label": "<10", "min": float("-inf"), "max": 10.0},
    {"label": "10-11", "min": 10.0, "max": 11.0},
    {"label": "11-12", "min": 11.0, "max": 12.0},
    {"label": "12-13", "min": 12.0, "max": 13.0},
    {"label": ">=13", "min": 13.0, "max": float("inf")},
)
PB_DROP_BINS = (
    {"label": ">=2.0", "min": 2.0, "max": float("inf")},
    {"label": "1.5-2.0", "min": 1.5, "max": 2.0},
    {"label": "1.0-1.5", "min": 1.0, "max": 1.5},
    {"label": "0.5-1.0", "min": 0.5, "max": 1.0},
    {"label": "<0.5", "min": float("-inf"), "max": 0.5},
)
PB_MIN_HEATMAP_CELL = 5
PB_FLAGGED_DEFAULT_LIMIT = 200
PB_FLAGGED_MAX_LIMIT = 1000
PB_CACHE_SCHEMA_VERSION = 2

app = FastAPI(title="IDA Synthetic Cohort API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


class GenerateRequest(BaseModel):
    n_patients: int = 1000
    seed: int = 1


def _summary_path(n_patients: int, seed: int) -> Path:
    return REPO_ROOT / "data" / "synth_runs" / f"{n_patients}_{seed}" / "summary.json"


def _policy_builder_run_dir(n_patients: int, seed: int) -> Path:
    return REPO_ROOT / "data" / "synth_runs" / f"{n_patients}_{seed}"


def _policy_builder_paths(
    n_patients: int,
    seed: int,
    gender: str,
    min_age: int,
    max_age: int,
) -> Tuple[Path, Path]:
    run_dir = _policy_builder_run_dir(n_patients, seed)
    cohort = run_dir / f"cohort_summary_{gender}_{min_age}_{max_age}.json"
    patients = run_dir / f"patients_{gender}_{min_age}_{max_age}.json"
    return cohort, patients


def _policy_builder_db_path(
    n_patients: int,
    seed: int,
    gender: str,
    min_age: int,
    max_age: int,
) -> Path:
    run_dir = _policy_builder_run_dir(n_patients, seed)
    return run_dir / f"policy_builder_{gender}_{min_age}_{max_age}.sqlite3"


def _normalize_gender(gender: str) -> str:
    g = (gender or "").strip().upper()
    if g not in {"F", "M", "ALL"}:
        raise HTTPException(status_code=400, detail='gender must be one of: "F", "M", "ALL"')
    return g


def _normalize_trigger(trigger: str) -> str:
    t = (trigger or "").strip().lower()
    if t not in {"lab", "coded", "gap", "setpoint"}:
        raise HTTPException(status_code=400, detail='trigger must be one of: "lab", "coded", "gap", "setpoint"')
    return t


def _canonical_setpoint_threshold(threshold: Optional[float]) -> float:
    if threshold is None:
        return 1.0
    rounded = round(float(threshold) * 2.0) / 2.0
    return max(PB_SETPOINT_THRESHOLDS[0], min(PB_SETPOINT_THRESHOLDS[-1], rounded))


def _normalize_policy(
    trigger: str,
    exclude_coded: bool,
    threshold: Optional[float],
) -> Tuple[str, bool, Optional[float]]:
    t = _normalize_trigger(trigger)
    if t == "coded":
        return t, False, None
    if t == "gap":
        return t, True, None
    if t == "setpoint":
        return t, bool(exclude_coded), _canonical_setpoint_threshold(threshold)
    return t, bool(exclude_coded), None


def _policy_key(
    trigger: str,
    exclude_coded: bool,
    require_min_hb: bool,
    threshold: Optional[float],
) -> str:
    th = f"{threshold:.1f}" if threshold is not None else "na"
    return (
        f"trigger={trigger}"
        f"|exclude_coded={1 if exclude_coded else 0}"
        f"|require_min_hb={1 if require_min_hb else 0}"
        f"|threshold={th}"
    )


def _policy_combinations() -> List[Dict[str, Any]]:
    combos: List[Dict[str, Any]] = []
    for require_min_hb in (False, True):
        for exclude_coded in (False, True):
            combos.append(
                {
                    "trigger": "lab",
                    "exclude_coded": exclude_coded,
                    "require_min_hb": require_min_hb,
                    "threshold": None,
                }
            )
        combos.append(
            {
                "trigger": "coded",
                "exclude_coded": False,
                "require_min_hb": require_min_hb,
                "threshold": None,
            }
        )
        combos.append(
            {
                "trigger": "gap",
                "exclude_coded": True,
                "require_min_hb": require_min_hb,
                "threshold": None,
            }
        )
        for threshold in PB_SETPOINT_THRESHOLDS:
            for exclude_coded in (False, True):
                combos.append(
                    {
                        "trigger": "setpoint",
                        "exclude_coded": exclude_coded,
                        "require_min_hb": require_min_hb,
                        "threshold": threshold,
                    }
                )
    return combos


PB_POLICY_COMBINATIONS = _policy_combinations()


def _policy_match(
    lab_anemia: bool,
    coded_anemia: bool,
    hb_drop: Optional[float],
    hb_count: int,
    trigger: str,
    exclude_coded: bool,
    require_min_hb: bool,
    threshold: Optional[float],
) -> bool:
    if require_min_hb and hb_count < 3:
        return False

    if trigger == "lab":
        if not lab_anemia:
            return False
        return (not exclude_coded) or (not coded_anemia)

    if trigger == "coded":
        return coded_anemia

    if trigger == "gap":
        return lab_anemia and (not coded_anemia)

    if hb_drop is None:
        return False
    if threshold is None:
        return False
    if hb_drop < threshold:
        return False
    return (not exclude_coded) or (not coded_anemia)


def _bin_index(value: float, bins: Tuple[Dict[str, Any], ...]) -> Optional[int]:
    for i, b in enumerate(bins):
        if value >= b["min"] and value < b["max"]:
            return i
    return None


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any, fallback: int = 0) -> int:
    if value is None:
        return fallback
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _ensure_policy_builder_cache(
    n_patients: int,
    seed: int,
    gender: str,
    min_age: int,
    max_age: int,
    force_rebuild: bool = False,
) -> Path:
    cohort_path, patients_path = _policy_builder_paths(n_patients, seed, gender, min_age, max_age)
    db_path = _policy_builder_db_path(n_patients, seed, gender, min_age, max_age)

    missing = [str(p) for p in (cohort_path, patients_path) if not p.exists()]
    if missing:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "cohort_not_found",
                "message": "Policy builder artifacts were not found for the requested filter.",
                "missing_files": missing,
            },
        )

    if db_path.exists() and not force_rebuild:
        try:
            existing = sqlite3.connect(db_path)
            row = existing.execute(
                "SELECT value FROM meta WHERE key = 'cache_schema_version'"
            ).fetchone()
            existing.close()
            if row and str(row[0]) == str(PB_CACHE_SCHEMA_VERSION):
                return db_path
        except sqlite3.Error:
            pass

    try:
        with open(cohort_path) as f:
            cohort = json.load(f)
        with open(patients_path) as f:
            patients = json.load(f)
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=500,
            detail={"error": "invalid_json", "message": f"Failed to parse cached cohort artifacts: {e}"},
        )

    tmp_db_path = db_path.with_name(db_path.name + ".tmp")
    if tmp_db_path.exists():
        tmp_db_path.unlink()

    conn: Optional[sqlite3.Connection] = None
    try:
        conn = sqlite3.connect(tmp_db_path)
        cur = conn.cursor()

        cur.execute(
            """
            CREATE TABLE meta (
              key TEXT PRIMARY KEY,
              value TEXT NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE patients (
              id TEXT PRIMARY KEY,
              age REAL,
              latest_hb REAL,
              hb_drop REAL,
              hb_drop_z REAL,
              hb_count INTEGER NOT NULL,
              lab_anemia INTEGER NOT NULL,
              coded_anemia INTEGER NOT NULL,
              ferritin_tests INTEGER NOT NULL,
              detail_json TEXT NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE rollups (
              policy_key TEXT PRIMARY KEY,
              trigger TEXT NOT NULL,
              exclude_coded INTEGER NOT NULL,
              require_min_hb INTEGER NOT NULL,
              threshold REAL,
              flagged_count INTEGER NOT NULL,
              ferritin_count INTEGER NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE heatmap_cells (
              drop_bin_idx INTEGER NOT NULL,
              hb_bin_idx INTEGER NOT NULL,
              n INTEGER NOT NULL,
              ferritin_count INTEGER NOT NULL,
              rate REAL,
              PRIMARY KEY (drop_bin_idx, hb_bin_idx)
            )
            """
        )

        rollups: Dict[str, Dict[str, int]] = {}
        for combo in PB_POLICY_COMBINATIONS:
            key = _policy_key(
                combo["trigger"],
                combo["exclude_coded"],
                combo["require_min_hb"],
                combo["threshold"],
            )
            rollups[key] = {"flagged_count": 0, "ferritin_count": 0}

        heat_counts: List[List[Dict[str, int]]] = [
            [{"n": 0, "fer": 0} for _ in PB_HB_BINS] for _ in PB_DROP_BINS
        ]

        batch: List[Tuple[Any, ...]] = []
        for p in patients:
            pid = str(p.get("id", ""))
            if not pid:
                continue

            age = _safe_float(p.get("age"))
            latest_hb = _safe_float(p.get("latest_hb"))
            hb_drop = _safe_float(p.get("hb_drop"))
            hb_drop_z = _safe_float(p.get("hb_drop_z"))
            hb_history = p.get("hb_history") or []
            hb_count = len(hb_history) if isinstance(hb_history, list) else 0
            lab_anemia = bool(p.get("lab_anemia"))
            coded_anemia = bool(p.get("coded_anemia"))
            ferritin_tests = _safe_int(p.get("ferritin_tests"), 0)
            has_ferritin = ferritin_tests > 0

            batch.append(
                (
                    pid,
                    age,
                    latest_hb,
                    hb_drop,
                    hb_drop_z,
                    hb_count,
                    1 if lab_anemia else 0,
                    1 if coded_anemia else 0,
                    ferritin_tests,
                    json.dumps(p, separators=(",", ":")),
                )
            )
            if len(batch) >= 2000:
                cur.executemany(
                    """
                    INSERT INTO patients (
                      id, age, latest_hb, hb_drop, hb_drop_z, hb_count,
                      lab_anemia, coded_anemia, ferritin_tests, detail_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    batch,
                )
                batch = []

            if latest_hb is not None:
                drop_for_bin = hb_drop if hb_drop is not None else 0.0
                xi = _bin_index(latest_hb, PB_HB_BINS)
                yi = _bin_index(drop_for_bin, PB_DROP_BINS)
                if xi is not None and yi is not None:
                    heat_counts[yi][xi]["n"] += 1
                    if has_ferritin:
                        heat_counts[yi][xi]["fer"] += 1

            for combo in PB_POLICY_COMBINATIONS:
                if _policy_match(
                    lab_anemia=lab_anemia,
                    coded_anemia=coded_anemia,
                    hb_drop=hb_drop,
                    hb_count=hb_count,
                    trigger=combo["trigger"],
                    exclude_coded=combo["exclude_coded"],
                    require_min_hb=combo["require_min_hb"],
                    threshold=combo["threshold"],
                ):
                    key = _policy_key(
                        combo["trigger"],
                        combo["exclude_coded"],
                        combo["require_min_hb"],
                        combo["threshold"],
                    )
                    rollups[key]["flagged_count"] += 1
                    if has_ferritin:
                        rollups[key]["ferritin_count"] += 1

        if batch:
            cur.executemany(
                """
                INSERT INTO patients (
                  id, age, latest_hb, hb_drop, hb_drop_z, hb_count,
                  lab_anemia, coded_anemia, ferritin_tests, detail_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                batch,
            )

        cur.executemany(
            """
            INSERT INTO rollups (
              policy_key, trigger, exclude_coded, require_min_hb, threshold,
              flagged_count, ferritin_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    _policy_key(
                        combo["trigger"],
                        combo["exclude_coded"],
                        combo["require_min_hb"],
                        combo["threshold"],
                    ),
                    combo["trigger"],
                    1 if combo["exclude_coded"] else 0,
                    1 if combo["require_min_hb"] else 0,
                    combo["threshold"],
                    rollups[
                        _policy_key(
                            combo["trigger"],
                            combo["exclude_coded"],
                            combo["require_min_hb"],
                            combo["threshold"],
                        )
                    ]["flagged_count"],
                    rollups[
                        _policy_key(
                            combo["trigger"],
                            combo["exclude_coded"],
                            combo["require_min_hb"],
                            combo["threshold"],
                        )
                    ]["ferritin_count"],
                )
                for combo in PB_POLICY_COMBINATIONS
            ],
        )

        heat_rows: List[Tuple[int, int, int, int, Optional[float]]] = []
        for yi, row in enumerate(heat_counts):
            for xi, cell in enumerate(row):
                rate: Optional[float] = None
                if cell["n"] > 0:
                    rate = cell["fer"] / cell["n"]
                heat_rows.append((yi, xi, cell["n"], cell["fer"], rate))

        cur.executemany(
            """
            INSERT INTO heatmap_cells (
              drop_bin_idx, hb_bin_idx, n, ferritin_count, rate
            ) VALUES (?, ?, ?, ?, ?)
            """,
            heat_rows,
        )

        built_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        cur.executemany(
            "INSERT INTO meta (key, value) VALUES (?, ?)",
            [
                ("cache_schema_version", str(PB_CACHE_SCHEMA_VERSION)),
                ("built_at", built_at),
                ("cohort_json", json.dumps(cohort)),
                ("setpoint_thresholds", json.dumps(PB_SETPOINT_THRESHOLDS)),
                ("hb_bins", json.dumps(PB_HB_BINS)),
                ("drop_bins", json.dumps(PB_DROP_BINS)),
                ("min_heatmap_cell", json.dumps(PB_MIN_HEATMAP_CELL)),
            ],
        )

        cur.execute("CREATE INDEX idx_patients_lab_anemia ON patients(lab_anemia)")
        cur.execute("CREATE INDEX idx_patients_coded_anemia ON patients(coded_anemia)")
        cur.execute("CREATE INDEX idx_patients_hb_count ON patients(hb_count)")
        cur.execute("CREATE INDEX idx_patients_hb_drop ON patients(hb_drop)")
        cur.execute("CREATE INDEX idx_patients_latest_hb ON patients(latest_hb)")

        conn.commit()
        conn.close()
        conn = None

        tmp_db_path.replace(db_path)
        return db_path
    except HTTPException:
        if conn is not None:
            conn.close()
        if tmp_db_path.exists():
            tmp_db_path.unlink()
        raise
    except Exception as e:
        if conn is not None:
            conn.close()
        if tmp_db_path.exists():
            tmp_db_path.unlink()
        raise HTTPException(
            status_code=500,
            detail={"error": "precompute_failed", "message": f"Failed building policy cache: {e}"},
        )


def _open_policy_db(
    n_patients: int,
    seed: int,
    gender: str,
    min_age: int,
    max_age: int,
    force_rebuild: bool = False,
) -> sqlite3.Connection:
    db_path = _ensure_policy_builder_cache(
        n_patients=n_patients,
        seed=seed,
        gender=gender,
        min_age=min_age,
        max_age=max_age,
        force_rebuild=force_rebuild,
    )
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _get_meta_json(conn: sqlite3.Connection, key: str, default: Any) -> Any:
    row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    if not row:
        return default
    try:
        return json.loads(row["value"])
    except json.JSONDecodeError:
        return default


def _policy_where_clause(
    trigger: str,
    exclude_coded: bool,
    require_min_hb: bool,
    threshold: Optional[float],
) -> Tuple[str, List[Any]]:
    clauses: List[str] = []
    params: List[Any] = []

    if require_min_hb:
        clauses.append("hb_count >= 3")

    if trigger == "lab":
        clauses.append("lab_anemia = 1")
        if exclude_coded:
            clauses.append("coded_anemia = 0")
    elif trigger == "coded":
        clauses.append("coded_anemia = 1")
    elif trigger == "gap":
        clauses.append("lab_anemia = 1")
        clauses.append("coded_anemia = 0")
    elif trigger == "setpoint":
        clauses.append("hb_drop IS NOT NULL")
        clauses.append("hb_drop >= ?")
        params.append(threshold)
        if exclude_coded:
            clauses.append("coded_anemia = 0")

    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    return where, params


def _policy_order_clause(trigger: str) -> str:
    if trigger == "setpoint":
        return "ORDER BY hb_drop DESC, latest_hb ASC, id ASC"
    if trigger in {"lab", "gap"}:
        return "ORDER BY latest_hb ASC, hb_drop DESC, id ASC"
    return "ORDER BY id ASC"


@app.post("/v1/synth/generate")
def generate_cohort(req: GenerateRequest):
    cached = _summary_path(req.n_patients, req.seed)
    if cached.exists():
        with open(cached) as f:
            s = json.load(f)
        return {"job_id": f"{req.n_patients}_{req.seed}", "status": "done", "summary": s}

    try:
        outdir = runner.run_synthea(req.n_patients, req.seed)
    except RuntimeError as e:
        msg = str(e)
        if "Java not found" in msg or ("Java" in msg and "requires Java" in msg):
            raise HTTPException(status_code=503, detail={"error": "java_missing", "message": msg})
        raise HTTPException(status_code=500, detail={"error": "synthea_failed", "message": msg})

    try:
        cohort_size, hb_values, ida_patient_ids = parse.parse_outputs(outdir)
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": "parse_failed", "message": str(e)})

    s = summary.compute_summary(cohort_size, hb_values, ida_patient_ids, req.n_patients, req.seed)

    cached.parent.mkdir(parents=True, exist_ok=True)
    with open(cached, "w") as f:
        json.dump(s, f, indent=2)

    return {"job_id": f"{req.n_patients}_{req.seed}", "status": "done", "summary": s}


@app.get("/v1/synth/summary")
def get_summary(n_patients: int = 1000, seed: int = 1):
    cached = _summary_path(n_patients, seed)
    if not cached.exists():
        raise HTTPException(status_code=404, detail="No cached summary found. Run /v1/synth/generate first.")
    with open(cached) as f:
        s = json.load(f)
    return {"job_id": f"{n_patients}_{seed}", "status": "done", "summary": s}


@app.post("/v1/policy-builder/precompute")
def precompute_policy_builder(
    n_patients: int = 5000,
    seed: int = 1,
    gender: str = "F",
    min_age: int = 18,
    max_age: int = 65,
    force: bool = False,
):
    normalized_gender = _normalize_gender(gender)
    db_path = _ensure_policy_builder_cache(
        n_patients=n_patients,
        seed=seed,
        gender=normalized_gender,
        min_age=min_age,
        max_age=max_age,
        force_rebuild=force,
    )
    return {
        "status": "done",
        "source": "precomputed",
        "cache_path": str(db_path),
        "params": {
            "n_patients": n_patients,
            "seed": seed,
            "gender": normalized_gender,
            "min_age": min_age,
            "max_age": max_age,
        },
    }


@app.get("/v1/policy-builder/summary")
def get_policy_builder_summary(
    n_patients: int = 5000,
    seed: int = 1,
    gender: str = "F",
    min_age: int = 18,
    max_age: int = 65,
    trigger: Optional[str] = None,
    exclude_coded: bool = False,
    require_min_hb: bool = False,
    threshold: float = 1.0,
):
    normalized_gender = _normalize_gender(gender)
    conn = _open_policy_db(
        n_patients=n_patients,
        seed=seed,
        gender=normalized_gender,
        min_age=min_age,
        max_age=max_age,
    )
    try:
        cohort = _get_meta_json(conn, "cohort_json", {})
        rollup_rows = conn.execute(
            """
            SELECT policy_key, trigger, exclude_coded, require_min_hb, threshold, flagged_count, ferritin_count
            FROM rollups
            """
        ).fetchall()
        rollups: Dict[str, Dict[str, Any]] = {}
        for r in rollup_rows:
            rollups[r["policy_key"]] = {
                "trigger": r["trigger"],
                "exclude_coded": bool(r["exclude_coded"]),
                "require_min_hb": bool(r["require_min_hb"]),
                "threshold": r["threshold"],
                "flagged_count": int(r["flagged_count"]),
                "ferritin_count": int(r["ferritin_count"]),
            }

        active_policy: Optional[Dict[str, Any]] = None
        if trigger is not None:
            policy_trigger, policy_exclude_coded, policy_threshold = _normalize_policy(
                trigger=trigger,
                exclude_coded=exclude_coded,
                threshold=threshold,
            )
            key = _policy_key(
                trigger=policy_trigger,
                exclude_coded=policy_exclude_coded,
                require_min_hb=require_min_hb,
                threshold=policy_threshold,
            )
            item = rollups.get(
                key,
                {
                    "flagged_count": 0,
                    "ferritin_count": 0,
                    "trigger": policy_trigger,
                    "exclude_coded": policy_exclude_coded,
                    "require_min_hb": require_min_hb,
                    "threshold": policy_threshold,
                },
            )
            cohort_size = int(cohort.get("cohort_size", 0) or 0)
            flagged_count = int(item["flagged_count"])
            ferritin_count = int(item["ferritin_count"])
            active_policy = {
                "policy_key": key,
                "trigger": policy_trigger,
                "exclude_coded": policy_exclude_coded,
                "require_min_hb": require_min_hb,
                "threshold": policy_threshold,
                "flagged_count": flagged_count,
                "ferritin_count": ferritin_count,
                "flagged_pct": ((flagged_count / cohort_size) * 100.0) if cohort_size > 0 else 0.0,
                "ferritin_pct": ((ferritin_count / flagged_count) * 100.0) if flagged_count > 0 else 0.0,
            }

        return {
            "status": "done",
            "source": "precomputed",
            "cohort": cohort,
            "available_setpoint_thresholds": list(PB_SETPOINT_THRESHOLDS),
            "rollups": rollups,
            "active_policy": active_policy,
        }
    finally:
        conn.close()


@app.get("/v1/policy-builder/heatmap")
def get_policy_builder_heatmap(
    n_patients: int = 5000,
    seed: int = 1,
    gender: str = "F",
    min_age: int = 18,
    max_age: int = 65,
):
    normalized_gender = _normalize_gender(gender)
    conn = _open_policy_db(
        n_patients=n_patients,
        seed=seed,
        gender=normalized_gender,
        min_age=min_age,
        max_age=max_age,
    )
    try:
        cells = [
            [{"n": 0, "fer": 0, "rate": None} for _ in PB_HB_BINS]
            for _ in PB_DROP_BINS
        ]
        rows = conn.execute(
            """
            SELECT drop_bin_idx, hb_bin_idx, n, ferritin_count, rate
            FROM heatmap_cells
            ORDER BY drop_bin_idx, hb_bin_idx
            """
        ).fetchall()
        for r in rows:
            yi = int(r["drop_bin_idx"])
            xi = int(r["hb_bin_idx"])
            cells[yi][xi] = {
                "n": int(r["n"]),
                "fer": int(r["ferritin_count"]),
                "rate": float(r["rate"]) if r["rate"] is not None else None,
            }

        return {
            "status": "done",
            "source": "precomputed",
            "min_cell": PB_MIN_HEATMAP_CELL,
            "hb_bins": [{"label": b["label"]} for b in PB_HB_BINS],
            "drop_bins": [{"label": b["label"]} for b in PB_DROP_BINS],
            "cells": cells,
        }
    finally:
        conn.close()


@app.get("/v1/policy-builder/flagged")
def get_policy_builder_flagged(
    n_patients: int = 5000,
    seed: int = 1,
    gender: str = "F",
    min_age: int = 18,
    max_age: int = 65,
    trigger: str = "lab",
    exclude_coded: bool = False,
    require_min_hb: bool = False,
    threshold: float = 1.0,
    limit: int = PB_FLAGGED_DEFAULT_LIMIT,
    offset: int = 0,
):
    normalized_gender = _normalize_gender(gender)
    policy_trigger, policy_exclude_coded, policy_threshold = _normalize_policy(
        trigger=trigger,
        exclude_coded=exclude_coded,
        threshold=threshold,
    )
    clamped_limit = max(1, min(PB_FLAGGED_MAX_LIMIT, int(limit)))
    safe_offset = max(0, int(offset))

    conn = _open_policy_db(
        n_patients=n_patients,
        seed=seed,
        gender=normalized_gender,
        min_age=min_age,
        max_age=max_age,
    )
    try:
        cohort = _get_meta_json(conn, "cohort_json", {})
        cohort_size = int(cohort.get("cohort_size", 0) or 0)

        where_sql, where_params = _policy_where_clause(
            trigger=policy_trigger,
            exclude_coded=policy_exclude_coded,
            require_min_hb=require_min_hb,
            threshold=policy_threshold,
        )
        order_sql = _policy_order_clause(policy_trigger)

        agg_row = conn.execute(
            f"""
            SELECT
              COUNT(*) AS flagged_count,
              COALESCE(SUM(CASE WHEN ferritin_tests > 0 THEN 1 ELSE 0 END), 0) AS ferritin_count
            FROM patients
            {where_sql}
            """,
            where_params,
        ).fetchone()
        flagged_count = int(agg_row["flagged_count"])
        ferritin_count = int(agg_row["ferritin_count"])

        patient_rows = conn.execute(
            f"""
            SELECT
              id, age, latest_hb, hb_drop, hb_drop_z, hb_count,
              lab_anemia, coded_anemia, ferritin_tests
            FROM patients
            {where_sql}
            {order_sql}
            LIMIT ? OFFSET ?
            """,
            [*where_params, clamped_limit, safe_offset],
        ).fetchall()

        patients = [
            {
                "id": r["id"],
                "age": float(r["age"]) if r["age"] is not None else None,
                "latest_hb": float(r["latest_hb"]) if r["latest_hb"] is not None else None,
                "hb_drop": float(r["hb_drop"]) if r["hb_drop"] is not None else None,
                "hb_drop_z": float(r["hb_drop_z"]) if r["hb_drop_z"] is not None else None,
                "hb_count": int(r["hb_count"]),
                "lab_anemia": bool(r["lab_anemia"]),
                "coded_anemia": bool(r["coded_anemia"]),
                "ferritin_tests": int(r["ferritin_tests"]),
            }
            for r in patient_rows
        ]

        return {
            "status": "done",
            "source": "precomputed",
            "query": {
                "trigger": policy_trigger,
                "exclude_coded": policy_exclude_coded,
                "require_min_hb": require_min_hb,
                "threshold": policy_threshold,
                "limit": clamped_limit,
                "offset": safe_offset,
            },
            "summary": {
                "cohort_size": cohort_size,
                "flagged_count": flagged_count,
                "ferritin_count": ferritin_count,
                "flagged_pct": ((flagged_count / cohort_size) * 100.0) if cohort_size > 0 else 0.0,
                "ferritin_pct": ((ferritin_count / flagged_count) * 100.0) if flagged_count > 0 else 0.0,
                "returned_count": len(patients),
                "truncated": (safe_offset + len(patients)) < flagged_count,
            },
            "patients": patients,
        }
    finally:
        conn.close()


@app.get("/v1/policy-builder/patient/{patient_id}")
def get_policy_builder_patient(
    patient_id: str,
    n_patients: int = 5000,
    seed: int = 1,
    gender: str = "F",
    min_age: int = 18,
    max_age: int = 65,
):
    normalized_gender = _normalize_gender(gender)
    conn = _open_policy_db(
        n_patients=n_patients,
        seed=seed,
        gender=normalized_gender,
        min_age=min_age,
        max_age=max_age,
    )
    try:
        row = conn.execute("SELECT detail_json FROM patients WHERE id = ?", (patient_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f'Patient "{patient_id}" was not found for this cohort.')
        try:
            patient = json.loads(row["detail_json"])
        except json.JSONDecodeError:
            raise HTTPException(status_code=500, detail="Cached patient detail JSON is invalid.")

        return {
            "status": "done",
            "source": "precomputed",
            "patient": patient,
        }
    finally:
        conn.close()


@app.get("/v1/policy-builder/cohort")
def get_policy_builder_cohort(
    n_patients: int = 5000,
    seed: int = 1,
    gender: str = "F",
    min_age: int = 18,
    max_age: int = 65,
):
    normalized_gender = _normalize_gender(gender)
    cohort_path, patients_path = _policy_builder_paths(
        n_patients=n_patients,
        seed=seed,
        gender=normalized_gender,
        min_age=min_age,
        max_age=max_age,
    )

    missing = [str(p) for p in (cohort_path, patients_path) if not p.exists()]
    if missing:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "cohort_not_found",
                "message": "Policy builder artifacts were not found for the requested filter.",
                "missing_files": missing,
            },
        )

    try:
        with open(cohort_path) as f:
            cohort = json.load(f)
        with open(patients_path) as f:
            patients = json.load(f)
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=500,
            detail={"error": "invalid_json", "message": f"Failed to parse cached cohort artifacts: {e}"},
        )

    return {
        "status": "done",
        "source": "files",
        "cohort": cohort,
        "patients": patients,
    }
