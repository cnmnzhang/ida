"""
apps/api/main.py

FastAPI backend for the Synthetic Cohort feature.
Runs Synthea, parses CSV output, and returns IDA summary statistics.
"""

import json
import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Ensure src/ is importable when running from repo root
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from synth import runner, parse, summary  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]

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
        if "Java not found" in msg or "Java" in msg and "requires Java" in msg:
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
