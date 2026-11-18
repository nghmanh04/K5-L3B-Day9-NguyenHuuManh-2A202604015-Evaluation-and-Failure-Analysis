"""Compare a PR report with a baseline and return a blocking CI verdict."""

from __future__ import annotations

import argparse
import json
from math import isclose, isfinite
from pathlib import Path

from lab8.console import utf8_stdio
from lab9 import stats
from lab9.eval import SPEC, aggregate, load_spec, per_item
from lab9.graders import GRADERS


def _report_problems(report: dict, spec: dict) -> tuple[list[str], dict]:
    problems = []
    rows, manifest = report["rows"], report["manifest"]
    keys = [(row.get("item_id"), row.get("seed")) for row in rows]
    seeds = manifest["seeds"]
    if len(rows) != manifest["items"] * len(seeds):
        problems.append("row count differs from manifest items × seeds")
    if len(set(keys)) != len(rows):
        problems.append("duplicate (item_id, seed) rows")
    items = {item for item, _ in keys}
    if (not items or None in items or len(items) != manifest["items"]
            or not seeds or len(seeds) != len(set(seeds))
            or set(keys) != {(item, seed) for item in items for seed in seeds}):
        problems.append("rows do not cover the manifest's complete item × seed grid")
    if report.get("evaluator_failures"):
        problems.append("evaluator_failures is nonempty")

    slices = {}
    membership = {}
    for (item, seed), row in zip(keys, rows, strict=True):
        tags = frozenset(row.get("slices") or [])
        if membership.setdefault(item, tags) != tags:
            problems.append(f"{item}@{seed}: inconsistent slice membership across seeds")
        slices[item, seed] = tags

    totals = report["metrics"]
    for metric, value in totals.items():
        if value is not None and (not isinstance(value, (int, float)) or not isfinite(value)):
            problems.append(f"metric {metric} has a non-finite or invalid aggregate")

    spec_ids = {metric["id"] for metric in spec["metrics"]}
    graded = sorted(mid for mid in spec_ids if mid in GRADERS or any(mid in row for row in rows))
    for mid in graded:
        bad = next((key for key, row in zip(keys, rows, strict=True) if not isinstance(row.get(mid), bool)), None)
        if bad is not None:
            problems.append(f"{bad[0]}@{bad[1]}: missing or invalid graded score {mid}")

    for metric in spec["metrics"]:
        mid = metric["id"]
        if totals.get(mid) is None and (metric.get("blocking") or mid in graded):
            problems.append(f"metric {mid} has no aggregate")

    if rows and not problems:
        has_cost = all("cost" in row for row in rows)
        if has_cost and any(not isinstance(row["cost"], (int, float)) or not isfinite(row["cost"])
                            or row["cost"] < 0 for row in rows):
            problems.append("trial cost must be finite and nonnegative")
        else:
            inputs = rows if has_cost else [{**row, "cost": 0.0} for row in rows]
            recomputed = aggregate(inputs, graded, k_values=spec.get("pass_k", []))
            if not has_cost:
                recomputed.pop("cost_per_success")
            for mid in sorted(spec_ids & recomputed.keys()):
                actual, expected = totals.get(mid), recomputed[mid]
                if actual != expected and (actual is None or expected is None
                                           or not isclose(actual, expected, rel_tol=0, abs_tol=1e-9)):
                    problems.append(f"metric {mid} differs from its trial rows")
    return problems, slices


def _threshold_problems(spec: dict) -> list[str]:
    thresholds = [(metric["id"], metric.get("threshold", {})) for metric in spec["metrics"]]
    thresholds.extend((f"slice:{s['name']}/{s['metric']}", s) for s in spec.get("slices", []))
    problems = []
    for metric, threshold in thresholds:
        for key in ("min", "max", "max_increase"):
            if key not in threshold:
                continue
            value = threshold[key]
            if type(value) is not int and not (isinstance(value, float) and isfinite(value)):
                problems.append(f"{metric}: threshold {key} must be a finite number")
    return problems


def _ratchet(current: dict, previous: dict, *, slices: bool = False) -> list[str]:
    problems = []
    for key, old in previous.items():
        if key not in current:
            problems.append(f"ratchet: removed {key}")
            continue
        new = current[key]
        if old.get("blocking") and not new.get("blocking"):
            problems.append(f"ratchet: {key} no longer blocks")
        old_th, new_th = (old, new) if slices else (old.get("threshold", {}), new.get("threshold", {}))
        for name in ("min", "max", "max_increase"):
            if name not in old_th:
                continue
            value = new_th.get(name)
            if value is None or (value < old_th[name] if name == "min" else value > old_th[name]):
                problems.append(f"ratchet: {key} loosened {name}")
        if old_th.get("no_significant_drop") and not new_th.get("no_significant_drop"):
            problems.append(f"ratchet: {key} removed no_significant_drop")
    return problems


def integrity_check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> list[str]:
    """Validate case coverage, evaluator scores, slice membership and policy ratchets."""
    problems = [f"spec: {problem}" for problem in _threshold_problems(spec)]
    comparable_spec = (base_spec is not None and spec["eval_set_version"] == base_spec["eval_set_version"])
    if comparable_spec:
        problems.extend(f"base spec: {problem}" for problem in _threshold_problems(base_spec))
    if problems:
        return problems

    pr_problems, pr_slices = _report_problems(pr, spec)
    base_problems, base_slices = _report_problems(base, base_spec if comparable_spec else spec)
    problems = [f"PR: {problem}" for problem in pr_problems]
    problems.extend(f"baseline: {problem}" for problem in base_problems)
    if pr_slices.keys() != base_slices.keys():
        problems.append("PR and baseline (item_id, seed) sets differ")
    if any(tags != base_slices[key] for key, tags in pr_slices.items() if key in base_slices):
        problems.append("PR and baseline slice membership differs")

    if comparable_spec:
        problems.extend(_ratchet({m["id"]: m for m in spec["metrics"]},
                                 {m["id"]: m for m in base_spec["metrics"]}))
        problems.extend(_ratchet({f"slice:{s['name']}/{s['metric']}": s for s in spec.get("slices", [])},
                                 {f"slice:{s['name']}/{s['metric']}": s for s in base_spec.get("slices", [])},
                                 slices=True))
    return problems


def _paired_note(a: dict, b: dict, spec: dict) -> tuple[str, str]:
    if not a or a.keys() != b.keys():
        return "missing", "no aligned item scores"
    keys = sorted(a)
    bs = spec.get("bootstrap", {})
    delta, lo, hi = stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys],
                                           n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027),
                                           confidence=bs.get("confidence", 0.95))
    return ("fail" if hi < 0 else "ok"), f"Δ {delta:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"


def _label(verdict: str, blocking: bool) -> str:
    if verdict == "ok":
        return "ok"
    if verdict == "missing":
        return "MISSING"
    return "BLOCK" if blocking else "warn"


def slice_check(pr: dict, base: dict, spec: dict) -> tuple[list[str], list[str]]:
    """Compare per-item means inside each configured slice."""
    blocked, lines = [], []
    for setting in spec.get("slices", []):
        name, metric = setting["name"], setting["metric"]
        check_id = f"slice:{name}/{metric}"
        scores = per_item(pr, metric, slice_name=name)
        value = sum(scores.values()) / len(scores) if scores else None
        floor = setting.get("min")
        verdict, note = "ok", ""
        if value is None:
            verdict = "missing"
        elif floor is not None and value < floor:
            verdict = "fail"

        if value is not None and setting.get("no_significant_drop"):
            paired, note = _paired_note(scores, per_item(base, metric, slice_name=name), spec)
            if paired != "ok":
                verdict = paired

        blocking = setting.get("blocking", False)
        if verdict != "ok" and blocking:
            blocked.append(check_id)
        shown = "None" if value is None else f"{value:.4f}"
        lines.append(f"  {check_id:<32} {shown:<8} min={floor}  {note:<28} {_label(verdict, blocking)}")
    return blocked, lines


def check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> tuple[list[str], list[str]]:
    if pr["manifest"]["eval_set_sha"] != base["manifest"]["eval_set_sha"]:
        return ["eval_set_sha"], ["  EVAL SET differs from the baseline's: re-run the baseline on the same eval set"]
    problems = integrity_check(pr, base, spec, base_spec)
    if problems:
        return ["integrity"], [f"  INTEGRITY {problem}" for problem in problems]

    blocked, lines = [], []
    for metric in spec["metrics"]:
        mid, threshold = metric["id"], metric.get("threshold", {})
        value, baseline = pr["metrics"].get(mid), base["metrics"].get(mid)
        verdict, note = "ok", ""
        if value is None:
            verdict = "missing"
        elif "max" in threshold and value > threshold["max"]:
            verdict = "fail"
        elif "min" in threshold and value < threshold["min"]:
            verdict = "fail"
        elif "max_increase" in threshold and baseline is not None:
            if value > baseline * (1 + threshold["max_increase"]):
                verdict = "fail"

        if threshold.get("no_significant_drop") and value is not None:
            paired, note = _paired_note(per_item(pr, mid), per_item(base, mid), spec)
            if paired != "ok":
                verdict = paired

        blocking = metric.get("blocking", False)
        if verdict != "ok" and blocking:
            blocked.append(mid)
        lines.append(f"  {mid:<24} {value!s:<8} {json.dumps(threshold):<40} {note:<28} {_label(verdict, blocking)}")

    slice_blocked, slice_lines = slice_check(pr, base, spec)
    return blocked + slice_blocked, lines + slice_lines


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    ap = argparse.ArgumentParser(prog="lab9.gate")
    ap.add_argument("--pr", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--spec", default=str(SPEC))
    ap.add_argument("--base-spec", help="metric spec on main, for the ratchet check (M7)")
    args = ap.parse_args(argv)
    pr = json.loads(Path(args.pr).read_text(encoding="utf-8"))
    base = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    base_spec = load_spec(Path(args.base_spec)) if args.base_spec else None
    blocked, lines = check(pr, base, load_spec(Path(args.spec)), base_spec)
    print(f"gate: PR {pr['run_id']} vs main {base['run_id']} · eval set {pr['manifest']['eval_set_sha']}")
    print("\n".join(lines))
    if blocked:
        print(f"exit 1 — blocked: {', '.join(blocked)}")
        return 1
    print("exit 0 — merge")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
