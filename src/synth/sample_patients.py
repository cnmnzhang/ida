"""
src/synth/sample_patients.py

Create a small representative sample from a policy-builder patients JSON file.

Representation strategy:
  - Stratify by (lab_anemia, coded_anemia, hb_count>=3)
  - Allocate sample counts approximately proportionally
  - Guarantee at least 1 sample per non-empty stratum when feasible
"""

import argparse
import json
import math
import random
from collections import defaultdict
from pathlib import Path


def _stratum(patient: dict) -> tuple:
    hb_count = len(patient.get("hb_history") or [])
    return (
        bool(patient.get("lab_anemia")),
        bool(patient.get("coded_anemia")),
        hb_count >= 3,
    )


def _richness(patient: dict) -> int:
    hb = len(patient.get("hb_history") or [])
    conds = len(patient.get("conditions") or [])
    ferritin = patient.get("ferritin_tests") or 0
    return hb + conds + ferritin


def _allocate(group_sizes: dict, n: int) -> dict:
    total = sum(group_sizes.values())
    if total <= 0 or n <= 0:
        return {k: 0 for k in group_sizes}

    keys = [k for k, size in group_sizes.items() if size > 0]
    if not keys:
        return {k: 0 for k in group_sizes}

    if n <= len(keys):
        # Too few samples to cover all groups; assign by largest groups.
        ranked = sorted(keys, key=lambda k: group_sizes[k], reverse=True)
        out = {k: 0 for k in group_sizes}
        for k in ranked[:n]:
            out[k] = 1
        return out

    raw = {k: (group_sizes[k] / total) * n for k in keys}
    alloc = {k: int(math.floor(raw[k])) for k in keys}

    # Ensure at least 1 per non-empty group (feasible because n > len(keys)).
    for k in keys:
        if alloc[k] == 0:
            alloc[k] = 1

    used = sum(alloc.values())
    if used < n:
        # Add remaining by largest fractional remainder.
        remainders = sorted(
            keys,
            key=lambda k: raw[k] - math.floor(raw[k]),
            reverse=True,
        )
        i = 0
        while used < n:
            k = remainders[i % len(remainders)]
            alloc[k] += 1
            used += 1
            i += 1
    elif used > n:
        # Remove extras from largest allocations while keeping >=1.
        ranked = sorted(keys, key=lambda k: alloc[k], reverse=True)
        i = 0
        while used > n and ranked:
            k = ranked[i % len(ranked)]
            if alloc[k] > 1:
                alloc[k] -= 1
                used -= 1
            i += 1
            if i > 10_000:
                break

    out = {k: 0 for k in group_sizes}
    out.update(alloc)
    return out


def sample_patients(patients: list, n: int, seed: int) -> list:
    rng = random.Random(seed)
    groups = defaultdict(list)
    for p in patients:
        groups[_stratum(p)].append(p)

    sizes = {k: len(v) for k, v in groups.items()}
    alloc = _allocate(sizes, n)

    sampled = []
    for k, want in alloc.items():
        candidates = sorted(groups.get(k, []), key=_richness, reverse=True)
        if want <= 0 or not candidates:
            continue
        sampled.extend(candidates[:want])

    # If rounding/constraints undershot, fill from remaining pool (richest first).
    if len(sampled) < n:
        seen = {p["id"] for p in sampled}
        remaining = sorted(
            (p for p in patients if p["id"] not in seen),
            key=_richness, reverse=True,
        )
        sampled.extend(remaining[:n - len(sampled)])

    # Cap in rare overshoot case (richest first).
    if len(sampled) > n:
        sampled = sorted(sampled, key=_richness, reverse=True)[:n]

    return sampled


def main() -> None:
    parser = argparse.ArgumentParser(description="Create representative patient JSON sample")
    parser.add_argument("--input", required=True, help="Input patients JSON path")
    parser.add_argument("--output", required=True, help="Output sampled JSON path")
    parser.add_argument("--n", type=int, default=20, help="Sample size")
    parser.add_argument("--seed", type=int, default=1, help="Random seed")
    args = parser.parse_args()

    in_path = Path(args.input)
    out_path = Path(args.output)

    with in_path.open() as f:
        patients = json.load(f)

    sampled = sample_patients(patients, args.n, args.seed)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w") as f:
        json.dump(sampled, f, separators=(",", ":"))

    print(f"Input patients: {len(patients):,}")
    print(f"Sampled patients: {len(sampled):,}")
    print(f"Wrote: {out_path}")


if __name__ == "__main__":
    main()
