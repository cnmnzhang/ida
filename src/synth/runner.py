"""
src/synth/runner.py

Runs Synthea JAR to generate synthetic patient data.
Caches results by (n_patients, seed) to avoid re-running.
"""

import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
JAR_PATH = Path(__file__).resolve().parent / "synthea-with-dependencies.jar"


def _check_java_version() -> None:
    """Raise a clear error if the active Java runtime is below version 11."""
    result = subprocess.run(
        ["java", "-version"], capture_output=True, text=True
    )
    # java -version writes to stderr
    output = result.stderr or result.stdout
    # Output looks like: java version "1.8.0_xxx" or openjdk version "11.0.x"
    import re
    m = re.search(r'version "(\d+)(?:\.(\d+))?', output)
    if m:
        major = int(m.group(1))
        # Old-style versioning: "1.8" → major=1, minor=8
        if major == 1:
            major = int(m.group(2) or 0)
        if major < 11:
            raise RuntimeError(
                f"Java {major} detected, but Synthea requires Java 11+. "
                f"Install a newer JDK (e.g. via 'brew install openjdk@21') and "
                f"ensure it comes first on PATH.\n"
                f"Detected: {output.strip().splitlines()[0]}"
            )


def run_synthea(n_patients: int, seed: int) -> Path:
    """
    Run Synthea for the given parameters and return the output directory.
    Skips execution if patients.csv already exists (cache hit).
    """
    if shutil.which("java") is None:
        raise RuntimeError(
            "Java not found on PATH. Install Java 11+ and ensure 'java' is accessible."
        )

    _check_java_version()

    outdir = REPO_ROOT / "data" / "synth_runs" / f"{n_patients}_{seed}"
    patients_csv = outdir / "csv" / "patients.csv"

    if patients_csv.exists():
        return outdir

    outdir.mkdir(parents=True, exist_ok=True)

    cmd = [
        "java", "-jar", str(JAR_PATH),
        "-p", str(n_patients),
        "--exporter.csv.export", "true",
        "--exporter.fhir.export", "false",
        "--exporter.ccda.export", "false",
        "--exporter.baseDirectory", str(outdir),
        "-s", str(seed),
        "Washington",
        "Seattle",
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"Synthea failed (exit {result.returncode}):\n"
            f"stdout: {result.stdout[-2000:]}\n"
            f"stderr: {result.stderr[-2000:]}"
        )

    return outdir
