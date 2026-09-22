#!/usr/bin/env python3

from pathlib import Path
import csv
import math
import re
import statistics

ROOT = Path.home() / "turtlebot3_ws"
BASE = ROOT / "metrics" / "experiments"

CONFIGS = [
    "cartographer",
    "cartographer_yolo",
    "rtab",
    "rtab_yolo",
]

FIRST_EXP = 1
LAST_EXP = 10


def clean_float(v):
    if v is None:
        return None

    s = str(v).strip()

    if s == "":
        return None

    if s.lower() in {
        "nan", "na", "n/a", "none",
        "not available", "not_applicable"
    }:
        return None

    try:
        x = float(s)
        if math.isfinite(x):
            return x
    except Exception:
        pass

    return None


def read_csv_row(path):
    if not path.exists():
        return None

    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        return None

    return rows[0]


def parse_results_summary(path):
    """
    Fallback mainly for an older experiment such as Experiment 01
    if summary_row.csv is missing.
    """
    if not path.exists():
        return {}

    text = path.read_text(
        encoding="utf-8",
        errors="ignore"
    )

    out = {}

    patterns = {
        "ape_translation_rmse_m": [
            r"APE Translation RMSE\s*[:=]\s*([0-9.eE+-]+)",
        ],
        "ape_yaw_rmse_deg": [
            r"APE Yaw RMSE\s*[:=]\s*([0-9.eE+-]+)",
        ],
        "rpe_translation_rmse_m": [
            r"RPE Translation RMSE\s*[:=]\s*([0-9.eE+-]+)",
        ],
        "rpe_yaw_rmse_deg": [
            r"RPE Yaw RMSE\s*[:=]\s*([0-9.eE+-]+)",
        ],
    }

    for key, pats in patterns.items():
        for pat in pats:
            m = re.search(pat, text, flags=re.I)
            if m:
                out[key] = m.group(1)
                break

    return out


def validation_status(exp_dir):
    path = exp_dir / "experiment_validation.txt"

    if not path.exists():
        return ""

    text = path.read_text(
        encoding="utf-8",
        errors="ignore"
    )

    m = re.search(
        r"FINAL STATUS:\s*(\S+)",
        text,
        flags=re.I
    )

    if m:
        return m.group(1).upper()

    return ""


def metric_kind(name):
    n = name.lower()

    non_metrics = {
        "experiment",
        "experiment_number",
        "run",
        "run_number",
        "configuration",
        "config",
    }

    if n in non_metrics:
        return False

    return True


def aggregate_configuration(config):
    config_dir = BASE / config

    if not config_dir.exists():
        print(f"[SKIP] {config}: folder does not exist")
        return

    out_dir = config_dir / "aggregate_01_10"
    out_dir.mkdir(parents=True, exist_ok=True)

    runs = []
    missing = []

    for exp in range(FIRST_EXP, LAST_EXP + 1):

        exp_dir = config_dir / f"experiment_{exp:02d}"

        row_path = exp_dir / "summary_row.csv"
        result_path = exp_dir / "results_summary.txt"

        row = read_csv_row(row_path)

        if row is None:
            fallback = parse_results_summary(result_path)

            if not fallback:
                missing.append(exp)
                continue

            row = fallback

        row = dict(row)

        row["experiment"] = exp
        row["validation_status"] = validation_status(exp_dir)

        runs.append(row)

    if not runs:
        print(f"[SKIP] {config}: no experiment data")
        return

    # Collect every column seen in all runs.
    columns = []

    for row in runs:
        for key in row.keys():
            if key not in columns:
                columns.append(key)

    preferred_front = [
        "experiment",
        "validation_status",
        "configuration",
        "config",
    ]

    ordered_columns = []

    for c in preferred_front:
        if c in columns and c not in ordered_columns:
            ordered_columns.append(c)

    for c in columns:
        if c not in ordered_columns:
            ordered_columns.append(c)

    # ----------------------------------------------------------
    # Full run-level CSV
    # ----------------------------------------------------------

    all_runs_csv = out_dir / "all_runs_01_10.csv"

    with all_runs_csv.open(
        "w",
        newline="",
        encoding="utf-8"
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=ordered_columns,
            extrasaction="ignore"
        )

        writer.writeheader()

        for row in sorted(
            runs,
            key=lambda r: int(r["experiment"])
        ):
            writer.writerow(row)

    # ----------------------------------------------------------
    # Aggregate numerical metrics
    # ----------------------------------------------------------

    aggregate_rows = []

    for col in columns:

        if not metric_kind(col):
            continue

        vals = []

        for row in runs:
            x = clean_float(row.get(col))
            if x is not None:
                vals.append(x)

        if not vals:
            continue

        n = len(vals)
        mean = statistics.mean(vals)

        if n >= 2:
            sd = statistics.stdev(vals)  # sample SD, n-1
        else:
            sd = float("nan")

        median = statistics.median(vals)
        vmin = min(vals)
        vmax = max(vals)

        aggregate_rows.append({
            "metric": col,
            "n": n,
            "mean": mean,
            "sd": sd,
            "mean_plus_minus_sd": (
                f"{mean:.6f} ± {sd:.6f}"
                if math.isfinite(sd)
                else f"{mean:.6f} ± N/A"
            ),
            "median": median,
            "min": vmin,
            "max": vmax,
        })

    aggregate_csv = out_dir / "aggregate_mean_sd_01_10.csv"

    fieldnames = [
        "metric",
        "n",
        "mean",
        "sd",
        "mean_plus_minus_sd",
        "median",
        "min",
        "max",
    ]

    with aggregate_csv.open(
        "w",
        newline="",
        encoding="utf-8"
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=fieldnames
        )

        writer.writeheader()
        writer.writerows(aggregate_rows)

    # ----------------------------------------------------------
    # Human-readable summary
    # ----------------------------------------------------------

    txt = out_dir / "aggregate_summary_01_10.txt"

    valid_runs = [
        int(r["experiment"])
        for r in runs
        if str(r.get("validation_status", "")).upper() == "VALID"
    ]

    with txt.open("w", encoding="utf-8") as f:

        f.write("=" * 72 + "\n")
        f.write(
            f"AGGREGATE RESULTS: {config} "
            f"Experiments {FIRST_EXP:02d}-{LAST_EXP:02d}\n"
        )
        f.write("=" * 72 + "\n\n")

        f.write(
            "Experiments found: "
            + ", ".join(
                f"{int(r['experiment']):02d}"
                for r in sorted(
                    runs,
                    key=lambda r: int(r["experiment"])
                )
            )
            + "\n"
        )

        f.write(
            "VALID experiments: "
            + (
                ", ".join(f"{x:02d}" for x in valid_runs)
                if valid_runs
                else "None / validation unavailable"
            )
            + "\n"
        )

        if missing:
            f.write(
                "Missing experiments: "
                + ", ".join(f"{x:02d}" for x in missing)
                + "\n"
            )
        else:
            f.write("Missing experiments: None\n")

        f.write(
            "\n"
            "IMPORTANT:\n"
            "n is calculated independently for each metric.\n"
            "A metric with missing measurements in Experiment 01 "
            "is NOT filled or imputed.\n"
            "Therefore localization metrics may have n=10 while "
            "performance metrics may have n=9.\n"
            "SD is between-run sample standard deviation (ddof=1).\n"
        )

        f.write("\n" + "=" * 72 + "\n")
        f.write("MEAN ± BETWEEN-RUN SD\n")
        f.write("=" * 72 + "\n\n")

        for r in aggregate_rows:
            f.write(
                f"{r['metric']}\n"
                f"  n      : {r['n']}\n"
                f"  Mean±SD: {r['mean_plus_minus_sd']}\n"
                f"  Median : {r['median']:.6f}\n"
                f"  Min-Max: {r['min']:.6f} -> {r['max']:.6f}\n\n"
            )

    print()
    print("=" * 72)
    print(f"{config}: aggregation completed")
    print("=" * 72)
    print(f"Runs found : {len(runs)}/{LAST_EXP-FIRST_EXP+1}")
    print(
        "Experiments : "
        + ", ".join(
            f"{int(r['experiment']):02d}"
            for r in sorted(
                runs,
                key=lambda r: int(r["experiment"])
            )
        )
    )

    if missing:
        print(
            "Missing     : "
            + ", ".join(f"{x:02d}" for x in missing)
        )
    else:
        print("Missing     : None")

    print(f"Run table   : {all_runs_csv}")
    print(f"Mean ± SD   : {aggregate_csv}")
    print(f"Summary     : {txt}")
    print("=" * 72)


def main():
    import argparse

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "configuration",
        nargs="?",
        default="cartographer",
        choices=CONFIGS + ["all"],
        help="Configuration to aggregate"
    )

    args = parser.parse_args()

    if args.configuration == "all":
        for config in CONFIGS:
            aggregate_configuration(config)
    else:
        aggregate_configuration(args.configuration)


if __name__ == "__main__":
    main()
