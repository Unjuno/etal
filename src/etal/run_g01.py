"""Execute the prospectively specified G0-1 diagnostic, retaining every cell."""
import argparse
import csv
from datetime import datetime, timezone
from fractions import Fraction as Q
import hashlib
from itertools import product
import json
from pathlib import Path
import platform
import shlex
import sqlite3
import subprocess
import sys
import time

from .sequential import (Costs, ExactPlanner, NO_CODE, ONE_SYMBOL_CODES,
                         SUFFICIENT_CODE, make_row, select_cell)
from .sqlite_backend import SQLiteBackend


def jsonable(value):
    if isinstance(value, Q):
        return str(value)
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    return value


def write_json(path, value):
    path.write_text(json.dumps(jsonable(value), indent=2, ensure_ascii=False) + "\n")


def write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def calculate(protocol, out):
    grid = protocol["grid"]
    max_calls = protocol["environment"]["max_calls"]
    u = protocol["utility"]
    values, metrics, timings, policy_records, traces = {}, {}, [], [], []
    codes = ONE_SYMBOL_CODES + (NO_CODE, SUFFICIENT_CODE)
    backend_jobs, backend_steps = 0, 0
    for inspect, branch in product(map(Q, grid["inspect_cost"]), grid["branches"]):
        started = time.perf_counter()
        planner = ExactPlanner(branch, Costs(inspect, Q(u["write_cost"]),
                                             Q(u["repair_cost"]), Q(u["damage_penalty"])),
                               max_calls)
        cell_values = {code: planner.code_value(code) for code in codes}
        cell_metrics = {code: planner.code_metrics(code) for code in codes}
        values[(inspect, branch)] = cell_values
        metrics[(inspect, branch)] = cell_metrics
        for code in codes:
            policy_records.append({"branch": branch, "inspect_cost": inspect,
                                   "code": ",".join(code), **cell_metrics[code]})
        # Independent real SQLite execution of every optimal-code tie, plus
        # no-message and sufficient controls, over every finite world.
        best = max(cell_values[c] for c in ONE_SYMBOL_CODES)
        checked = [c for c in ONE_SYMBOL_CODES if cell_values[c] == best]
        checked += [NO_CODE, SUFFICIENT_CODE]
        for code in checked:
            for state, probability in planner.worlds:
                finite = planner.rollout(code, state)
                with SQLiteBackend(state, branch) as backend:
                    actual = planner.rollout(code, state, backend)
                    events = backend.event_log()
                if finite != actual:
                    raise AssertionError("independent SQLite rollout differs")
                backend_jobs += 1
                backend_steps += actual["calls"]
                if inspect == Q(1, 10) and branch == "C" and code == checked[0]:
                    traces.append({"initial_counts": state.counts,
                                   "pending_fault_evaluator_only": state.pending_fault,
                                   "probability": probability, "code": code,
                                   "result": actual, "sqlite_events_evaluator_only": events})
        timings.append({"branch": branch, "inspect_cost": inspect,
                        "elapsed_seconds": time.perf_counter() - started,
                        "bellman_cache_entries": planner.value.cache_info().currsize,
                        "transition_cache_entries": planner.transitions.cache_info().currsize})
        planner.value.cache_clear()
        planner.transitions.cache_clear()
        print(f"Solved branch={branch} inspection={inspect}", flush=True)
    rows = []
    for inspect, byte, fee, horizon, branch in product(
            map(Q, grid["inspect_cost"]), map(Q, grid["byte_cost"]),
            map(Q, grid["extra_update_fee"]), grid["jobs_per_phase"], grid["branches"]):
        rows.append(make_row(branch, byte, inspect, fee, horizon,
                             values[(inspect, "N")], values[(inspect, branch)],
                             metrics[(inspect, branch)]))
    if len(rows) != grid["expected_cells"]:
        raise AssertionError("incomplete grid")
    chosen = select_cell(rows)
    summary = {
        "protocol": protocol["id"], "cells": len(rows),
        "signed_forced_gain": {
            "positive_for_all_source_ties": sum(r["forced_gain_min"] > 0 for r in rows),
            "negative_for_all_source_ties": sum(r["forced_gain_max"] < 0 for r in rows),
            "identically_zero": sum(r["forced_gain_min"] == r["forced_gain_max"] == 0 for r in rows),
            "other_tie_dependent": sum(not(r["forced_gain_min"] > 0 or r["forced_gain_max"] < 0 or
                                         r["forced_gain_min"] == r["forced_gain_max"] == 0) for r in rows)},
        "optional_gain_zero_for_all_ties": sum(r["optional_gain_max"] == 0 for r in rows),
        "positive_lifecycle_advantage_over_all_three_static_controls":
            sum(r["lifecycle_advantage_min"] > 0 for r in rows),
        "selected_cell": chosen,
        "sqlite_validation": {"jobs": backend_jobs, "atomic_calls": backend_steps,
                              "mismatches": 0, "selection": "all target-optimal one-symbol ties plus NC/FS at each of nine branch/inspection cells"},
        "claim": "finite exact model-based oracle diagnostic; no learned adaptation"}
    write_csv(out / "grid.csv", rows)
    write_csv(out / "codec_metrics.csv", policy_records)
    write_json(out / "summary.json", summary)
    write_json(out / "representative_traces.json", traces)
    write_json(out / "cell_timings.json", timings)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=Path("protocols/g01.json"))
    parser.add_argument("--out", type=Path, default=Path("results/g01"))
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    started_at = datetime.now(timezone.utc).isoformat()
    protocol = json.loads(args.protocol.read_text())
    summary = calculate(protocol, args.out)
    manifest = {"protocol_sha256": hashlib.sha256(args.protocol.read_bytes()).hexdigest(),
                "source_sha256": {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                                   for p in sorted(Path("src/etal").glob("*.py"))},
                "result_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                   for p in sorted(args.out.iterdir())
                                   if p.is_file() and p.name not in ("manifest.json", "runtime.json")}}
    write_json(args.out / "manifest.json", manifest)
    cpu = "unavailable"
    cpuinfo = Path("/proc/cpuinfo")
    if cpuinfo.exists():
        cpu = next((line.split(":", 1)[1].strip() for line in cpuinfo.read_text().splitlines()
                    if line.startswith("model name")), cpu)
    try:
        parent = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        parent = "unavailable"
    write_json(args.out / "runtime.json", {
        "started_at_utc": started_at, "elapsed_seconds": time.perf_counter() - started,
        "python": platform.python_version(), "sqlite": sqlite3.sqlite_version,
        "platform": platform.platform(), "cpu": cpu, "clock_control": "not controlled",
        "device": "CPU", "execution": "single process, no parallel workers", "batch": "not applicable: exact enumeration",
        "container_runtime": "not executed", "parent_git_head": parent,
        "command": shlex.join([sys.executable, "-m", "etal.run_g01", "--protocol",
                               str(args.protocol), "--out", str(args.out)])})
    print(json.dumps(jsonable(summary), indent=2))


if __name__ == "__main__":
    main()
