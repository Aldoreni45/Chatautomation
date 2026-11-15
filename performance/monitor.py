"""
Resource monitor for load-test runs.

Samples, every INTERVAL seconds:
- CPU% and RSS memory of the uvicorn server process tree
- PostgreSQL connection counts for the perf database by state

Writes CSV rows to performance/reports/resources_<tag>.csv

Usage:
    uv run python performance/monitor.py --tag baseline_10u --seconds 120
"""

import argparse
import csv
import os
import sys
import time
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import environ
import psutil
import psycopg

ROOT = Path(__file__).resolve().parent.parent
REPORTS = ROOT / "performance" / "reports"

env = environ.Env()
env.read_env(ROOT / ".env")

PERF_DB_NAME = os.environ.get("PERF_DB_NAME", "chatbot_perf")
_parts = urlparse(env("DATABASE_URL"))
PERF_URL = urlunparse(_parts._replace(path=f"/{PERF_DB_NAME}"))


def server_processes():
    procs = []
    for p in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            cmdline = " ".join(p.info["cmdline"] or [])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
        if "run_server.py" in cmdline or "uvicorn" in cmdline:
            procs.append(psutil.Process(p.info["pid"]))
    return procs


def sample_db_connections(cur):
    cur.execute(
        "SELECT state, count(*) FROM pg_stat_activity "
        "WHERE datname = %s GROUP BY state",
        (PERF_DB_NAME,),
    )
    counts = {"active": 0, "idle": 0, "idle_in_transaction": 0, "other": 0}
    for state, count in cur.fetchall():
        key = state if state in counts else "other"
        counts[key] = count
    counts["total"] = sum(counts.values())
    return counts


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", required=True)
    parser.add_argument("--seconds", type=int, default=120)
    parser.add_argument("--interval", type=float, default=2.0)
    args = parser.parse_args()

    REPORTS.mkdir(parents=True, exist_ok=True)
    out_path = REPORTS / f"resources_{args.tag}.csv"

    fields = [
        "timestamp", "server_cpu_percent", "server_mem_mb",
        "server_procs", "db_total", "db_active", "db_idle",
        "db_idle_in_transaction",
    ]

    conn = psycopg.connect(PERF_URL, autocommit=True)
    deadline = time.time() + args.seconds
    rows = 0
    tracked = {}  # pid -> psutil.Process (persistent for cpu_percent)

    with out_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()

        while time.time() < deadline:
            # Refresh tracked processes and their children.
            current = {}
            for p in server_processes():
                try:
                    candidates = [p] + p.children(recursive=True)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
                for c in candidates:
                    current[c.pid] = c
            tracked = {
                pid: proc
                for pid, proc in tracked.items()
                if pid in current
            }
            tracked.update(
                {pid: proc for pid, proc in current.items()
                 if pid not in tracked}
            )

            cpu = 0.0
            mem_mb = 0.0
            for p in tracked.values():
                try:
                    cpu += p.cpu_percent(interval=None)
                    mem_mb += p.memory_info().rss / (1024 * 1024)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass

            with conn.cursor() as cur:
                db = sample_db_connections(cur)

            writer.writerow({
                "timestamp": time.time(),
                "server_cpu_percent": round(cpu, 1),
                "server_mem_mb": round(mem_mb, 1),
                "server_procs": len(tracked),
                "db_total": db["total"],
                "db_active": db["active"],
                "db_idle": db["idle"],
                "db_idle_in_transaction": db["idle_in_transaction"],
            })
            f.flush()
            rows += 1
            time.sleep(args.interval)

    conn.close()
    print(f"[monitor] wrote {rows} samples to {out_path}")


if __name__ == "__main__":
    main()
