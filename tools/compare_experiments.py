#!/usr/bin/env python3
"""Compare experiment summary JSON files without reading full logs."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


LOWER_IS_BETTER = ("loss", "error", "mae", "mse", "rmse", "wer", "cer")


def metric_direction(metric_name: str) -> str:
    name = metric_name.lower()
    if any(token in name for token in LOWER_IS_BETTER):
        return "lower"
    return "higher"


def is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def fmt(value: Any) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)


def escape_md(value: Any) -> str:
    return fmt(value).replace("|", "\\|").replace("\n", " ")


def summary_name(path: Path) -> str:
    name = path.name
    return name[: -len(".summary.json")] if name.endswith(".summary.json") else path.stem


def load_summaries(directory: Path) -> Tuple[List[Dict[str, Any]], int, List[str]]:
    if not directory.is_dir():
        raise FileNotFoundError(f"Summaries directory does not exist: {directory}")

    paths = sorted(directory.glob("*.summary.json"))
    if not paths:
        raise FileNotFoundError(f"No *.summary.json files found in: {directory}")

    experiments: List[Dict[str, Any]] = []
    warnings: List[str] = []
    skipped = 0
    for path in paths:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("top-level JSON is not an object")
        except Exception as exc:
            skipped += 1
            warnings.append(f"Skipped {path.name}: failed to parse JSON ({exc}).")
            continue

        facts = data.get("facts") if isinstance(data.get("facts"), dict) else {}
        metrics = data.get("metrics") if isinstance(data.get("metrics"), dict) else {}
        name = str(data.get("experiment_name") or summary_name(path))
        if not metrics:
            warnings.append(f"{name}: metrics missing or empty.")

        experiments.append(
            {
                "experiment_name": name,
                "status": data.get("status", "unknown"),
                "note": data.get("note", ""),
                "metrics": metrics,
                "metrics_source": data.get("metrics_source") or "none",
                "adapter_status": data.get("adapter_status") or "none",
                "duration_seconds": facts.get("duration_seconds"),
                "git_commit": facts.get("git_commit", "unknown"),
                "command": facts.get("command", "unknown"),
                "log_path": facts.get("log_path", "unknown"),
            }
        )

    return experiments, skipped, warnings


def split_metric_keys(experiments: List[Dict[str, Any]], warnings: List[str]) -> Tuple[List[str], List[str]]:
    numeric = set()
    non_numeric = set()
    for exp in experiments:
        for key, value in exp["metrics"].items():
            if is_number(value):
                numeric.add(str(key))
            else:
                non_numeric.add(str(key))
                warnings.append(f"{exp['experiment_name']}: non-numeric metric skipped: {key}.")

    return sorted(numeric), sorted(non_numeric)


def sort_experiments(
    experiments: List[Dict[str, Any]],
    metric_keys: List[str],
    sort_by: Optional[str],
    ascending: bool,
    descending: bool,
    warnings: List[str],
) -> List[Dict[str, Any]]:
    if not sort_by:
        return experiments
    if sort_by not in metric_keys:
        warnings.append(f"Sort metric not found or not numeric: {sort_by}.")
        return experiments

    reverse = descending or (not ascending and metric_direction(sort_by) == "higher")
    with_values = [exp for exp in experiments if is_number(exp["metrics"].get(sort_by))]
    without_values = [exp for exp in experiments if not is_number(exp["metrics"].get(sort_by))]
    return sorted(with_values, key=lambda exp: float(exp["metrics"][sort_by]), reverse=reverse) + without_values


def markdown_table(headers: List[str], rows: List[List[Any]], numeric_from: int = 0) -> str:
    align = ["---:" if idx >= numeric_from else "---" for idx in range(len(headers))]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(align) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(escape_md(item) for item in row) + " |")
    return "\n".join(lines)


def render_report(
    summaries_dir: Path,
    experiments: List[Dict[str, Any]],
    skipped: int,
    metric_keys: List[str],
    baseline: Optional[str],
    warnings: List[str],
) -> str:
    baseline_exp = None
    if baseline:
        baseline_exp = next((exp for exp in experiments if exp["experiment_name"] == baseline), None)
        if baseline_exp is None:
            warnings.append(f"Baseline not found: {baseline}.")

    if not baseline:
        baseline_text = "None provided"
    elif baseline_exp:
        baseline_text = baseline
    else:
        baseline_text = f"{baseline} (not found)"

    lines = [
        "# Experiment Comparison",
        "",
        "## Overview",
        f"- Summaries directory: `{summaries_dir}`",
        f"- Number of loaded experiments: {len(experiments)}",
        f"- Number of skipped files: {skipped}",
        f"- Baseline: {baseline_text}",
        f"- Generated time: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}",
        "",
        "## Metrics Table",
    ]

    headers = ["Experiment", "Status", "Metrics Source"] + metric_keys
    rows = [
        [
            exp["experiment_name"],
            exp["status"],
            exp["metrics_source"],
            *[exp["metrics"].get(key) if is_number(exp["metrics"].get(key)) else None for key in metric_keys],
        ]
        for exp in experiments
    ]
    lines.append(markdown_table(headers, rows, numeric_from=3))

    lines.extend(["", "## Delta vs Baseline"])
    if baseline_exp and metric_keys:
        lower = [key for key in metric_keys if metric_direction(key) == "lower"]
        if lower:
            lines.append(f"Lower is better for: {', '.join(lower)}.")
            lines.append("")
        delta_headers = ["Experiment"] + [f"{key} Δ" for key in metric_keys]
        delta_rows = []
        for exp in experiments:
            row = [exp["experiment_name"]]
            for key in metric_keys:
                value = exp["metrics"].get(key)
                base = baseline_exp["metrics"].get(key)
                row.append((float(value) - float(base)) if is_number(value) and is_number(base) else None)
            delta_rows.append(row)
        lines.append(markdown_table(delta_headers, delta_rows, numeric_from=1))
    else:
        lines.append("No valid baseline was provided; delta table is skipped.")

    lines.extend(["", "## Best Experiments"])
    best_rows = []
    for key in metric_keys:
        candidates = [(exp, exp["metrics"].get(key)) for exp in experiments if is_number(exp["metrics"].get(key))]
        if not candidates:
            continue
        direction = metric_direction(key)
        best_exp, best_value = (min if direction == "lower" else max)(candidates, key=lambda item: item[1])
        best_rows.append([key, direction, best_exp["experiment_name"], best_value])
    lines.append(markdown_table(["Metric", "Direction", "Experiment", "Value"], best_rows, numeric_from=3) if best_rows else "No numeric metrics found.")

    lines.extend(["", "## Warnings"])
    if warnings:
        lines.extend(f"- {warning}" for warning in warnings)
    else:
        lines.append("- None")

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summaries", default="experiments/summaries")
    parser.add_argument("--baseline")
    parser.add_argument("--output")
    parser.add_argument("--sort-by")
    direction = parser.add_mutually_exclusive_group()
    direction.add_argument("--ascending", action="store_true")
    direction.add_argument("--descending", action="store_true")
    args = parser.parse_args()

    summaries_dir = Path(args.summaries)
    try:
        experiments, skipped, warnings = load_summaries(summaries_dir)
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    metric_keys, _ = split_metric_keys(experiments, warnings)
    experiments = sort_experiments(experiments, metric_keys, args.sort_by, args.ascending, args.descending, warnings)
    report = render_report(summaries_dir, experiments, skipped, metric_keys, args.baseline, warnings)

    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(report, encoding="utf-8")
        print(f"Wrote {output}")
    else:
        print(report, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
