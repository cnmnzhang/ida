# IDA Research Explorer

Interactive anemia explorer with a static frontend (`index.html`) and a FastAPI backend (`apps/api/main.py`) for synthetic cohort + policy-builder data.

## Local Quickstart (recommended)

Run from repo root:

```bash
cd /Users/cindyz1/ida

# 1) Python env
python3 -m venv .venv
source .venv/bin/activate
pip install -r apps/api/requirements.txt

# 2) API server
uvicorn apps.api.main:app --reload --port 8000
```

In a second terminal:

```bash
cd /Users/cindyz1/ida
source .venv/bin/activate

# 3) Build policy-builder precomputed cache (one-time per cohort/filter)
curl -X POST "http://localhost:8000/v1/policy-builder/precompute?n_patients=5000&seed=1&gender=F&min_age=18&max_age=65"

# 4) Serve frontend over HTTP (not file://)
python3 -m http.server 8080
```

Open:

- API mode (preferred): `http://localhost:8080/?pb_source=api&pb_api_base=http://localhost:8000`
- Static mode: `http://localhost:8080/?pb_source=static`
- Auto mode (default): `http://localhost:8080/`
- Override run/filter in URL (optional): add `pb_n`, `pb_seed`, `pb_gender`, `pb_min_age`, `pb_max_age`
- Override static JSON paths (optional): add `pb_cohort_path`, `pb_patients_path`

## What changed for Policy Builder

The policy builder now supports precomputed API endpoints:

- `POST /v1/policy-builder/precompute`
- `GET /v1/policy-builder/summary`
- `GET /v1/policy-builder/heatmap`
- `GET /v1/policy-builder/flagged`
- `GET /v1/policy-builder/patient/{patient_id}`

Legacy endpoint is still available:

- `GET /v1/policy-builder/cohort`

## Optional: generate cohort artifacts

If needed, generate or refresh local cohort files first:

```bash
cd /Users/cindyz1/ida
source .venv/bin/activate

python src/synth/generate_cohort.py --n 5000 --seed 1 --gender F --min-age 18 --max-age 65
python src/synth/build_patient_records.py --n 5000 --seed 1 --gender F --min-age 18 --max-age 65
```

This writes:

- `data/synth_runs/5000_1/cohort_summary_F_18_65.json`
- `data/synth_runs/5000_1/patients_F_18_65.json`

## Using a large run (example: `1000000_1`)

If `data/synth_runs/1000000_1/csv/` already exists, skip Synthea and build artifacts directly:

```bash
cd /Users/cindyz1/ida
source .venv/bin/activate

# Build cohort summary from cached CSV
python src/synth/generate_cohort.py --n 1000000 --seed 1 --gender F --min-age 18 --max-age 65 --skip-synthea

# Build patient records (streaming/chunked)
python src/synth/build_patient_records.py --n 1000000 --seed 1 --gender F --min-age 18 --max-age 65

# Build API precompute cache
curl -X POST "http://localhost:8000/v1/policy-builder/precompute?n_patients=1000000&seed=1&gender=F&min_age=18&max_age=65"
```

Then open:

- `http://localhost:8080/?pb_source=api&pb_api_base=http://localhost:8000&pb_n=1000000&pb_seed=1&pb_gender=F&pb_min_age=18&pb_max_age=65`

If you only want a lightweight static demo, generate and use a 20-patient representative sample:

```bash
python src/synth/sample_patients.py \
  --input data/synth_runs/1000000_1/patients_F_18_65.json \
  --output data/synth_runs/1000000_1/patients_F_18_65_sample20.json \
  --n 20 --seed 1
```

Open static sample mode:

- `http://localhost:8080/?pb_source=static&pb_cohort_path=data/synth_runs/1000000_1/cohort_summary_F_18_65.json&pb_patients_path=data/synth_runs/1000000_1/patients_F_18_65_sample20.json`

Note: Synthea may generate fewer than requested (`patients_generated` can be less than `--n`), which is expected.

## Frontend config for deploys (GitHub Pages)

Edit `index.html` and set:

- `window.IDA_CONFIG.apiBase = "https://your-backend.example.com"`
- `window.IDA_CONFIG.policyBuilder.source = "api"`

GitHub Pages cannot serve your large ignored `data/synth_runs/*` artifacts, so production should use API mode.

## Troubleshooting

- `Unable to load cohort ... HTTP 404 data/synth_runs/...`:
  - You are in static mode without committed data files. Use API mode URL above.
- `Could not reach the API at http://localhost:8000`:
  - Start uvicorn and confirm port 8000 is open.
- Page is blank or fetch fails from `file://`:
  - Serve via HTTP (`python3 -m http.server 8080`).
