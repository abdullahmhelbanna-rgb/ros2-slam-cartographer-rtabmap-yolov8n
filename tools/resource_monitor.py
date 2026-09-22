#!/usr/bin/env python3

import argparse
import csv
import os
import subprocess
import time
from pathlib import Path

import psutil


parser = argparse.ArgumentParser()
parser.add_argument("--out", required=True)
parser.add_argument("--match", required=True)
parser.add_argument("--period", type=float, default=1.0)
args = parser.parse_args()

out = Path(args.out)
out.parent.mkdir(parents=True, exist_ok=True)

# Preserve command-line order while removing duplicates.
pattern_list = []
for item in args.match.split(","):
    item = item.strip()
    if item and item not in pattern_list:
        pattern_list.append(item)

pattern_set = set(pattern_list)

if not pattern_list:
    raise SystemExit("No valid process names supplied to --match")

self_pid = os.getpid()
known = {}


def process_candidates(info):
    candidates = set()

    name = info.get("name") or ""
    if name:
        candidates.add(name)

    cmdline = info.get("cmdline") or []

    # Only executable/script positions are examined.
    # Command arguments such as:
    # --match cartographer_node,yolo_node
    # must NOT cause the resource monitor itself to match.
    if len(cmdline) >= 1:
        candidates.add(
            os.path.basename(cmdline[0])
        )

    if len(cmdline) >= 2:
        candidates.add(
            os.path.basename(cmdline[1])
        )

    return candidates


def matching_patterns(info):
    candidates = process_candidates(info)

    return [
        pattern
        for pattern in pattern_list
        if pattern in candidates
    ]


def gpu_stats():
    try:
        text = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=utilization.gpu,memory.used",
                "--format=csv,noheader,nounits",
            ],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=2,
        ).strip()

        if not text:
            return "", ""

        first = text.splitlines()[0]
        gpu, mem = first.split(",")[:2]

        return (
            float(gpu.strip()),
            float(mem.strip()),
        )

    except Exception:
        return "", ""


# Warm-up system CPU counter.
psutil.cpu_percent(None)

header = [
    "wall_time",
    "system_cpu_percent",
    "system_ram_percent",
    "system_ram_used_mb",
    "matched_processes",
    "process_cpu_percent_sum",
    "process_rss_mb_sum",
]

# Add per-process-pattern measurements while preserving
# the original combined columns above.
for pattern in pattern_list:
    header.extend([
        f"{pattern}_cpu_percent",
        f"{pattern}_rss_mb",
    ])

header.extend([
    "gpu_util_percent",
    "gpu_memory_used_mb",
])


with out.open(
    "w",
    newline="",
    buffering=1,
    encoding="utf-8",
) as f:

    writer = csv.writer(f)
    writer.writerow(header)

    try:
        while True:

            system_cpu = psutil.cpu_percent(None)
            vm = psutil.virtual_memory()

            current_pids = set()
            matched = []

            total_cpu = 0.0
            total_rss = 0.0

            per_pattern_cpu = {
                pattern: 0.0
                for pattern in pattern_list
            }

            per_pattern_rss = {
                pattern: 0.0
                for pattern in pattern_list
            }

            for p in psutil.process_iter([
                "pid",
                "name",
                "cmdline",
            ]):
                try:
                    pid = p.info["pid"]

                    if pid == self_pid:
                        continue

                    matched_patterns = matching_patterns(
                        p.info
                    )

                    if not matched_patterns:
                        continue

                    current_pids.add(pid)

                    if pid not in known:
                        proc = psutil.Process(pid)

                        # Warm-up process-specific CPU counter.
                        proc.cpu_percent(None)

                        known[pid] = proc

                    proc = known[pid]

                    cpu = proc.cpu_percent(None)

                    rss = (
                        proc.memory_info().rss /
                        (1024 * 1024)
                    )

                    # Combined totals count each OS process once.
                    total_cpu += cpu
                    total_rss += rss

                    # Pattern-specific totals.
                    for pattern in matched_patterns:
                        per_pattern_cpu[pattern] += cpu
                        per_pattern_rss[pattern] += rss

                    cmdline = (
                        p.info.get("cmdline") or []
                    )

                    executable = (
                        os.path.basename(cmdline[0])
                        if cmdline
                        else (
                            p.info.get("name") or ""
                        )
                    )

                    matched.append(
                        f"{pid}:{executable}"
                    )

                except (
                    psutil.NoSuchProcess,
                    psutil.AccessDenied,
                    psutil.ZombieProcess,
                ):
                    continue

            for pid in list(known):
                if pid not in current_pids:
                    known.pop(pid, None)

            gpu_util, gpu_mem = gpu_stats()

            row = [
                time.time(),
                system_cpu,
                vm.percent,
                vm.used / (1024 * 1024),
                "|".join(matched),
                total_cpu,
                total_rss,
            ]

            for pattern in pattern_list:
                row.extend([
                    per_pattern_cpu[pattern],
                    per_pattern_rss[pattern],
                ])

            row.extend([
                gpu_util,
                gpu_mem,
            ])

            writer.writerow(row)

            time.sleep(args.period)

    except KeyboardInterrupt:
        pass
