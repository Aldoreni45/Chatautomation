"""Summarize locust CSV stats into a compact table."""

import csv
import glob
import os


def main():
    for path in sorted(glob.glob("performance/reports/users_*_stats.csv")):
        tag = (
            os.path.basename(path)
            .replace("users_", "")
            .replace("_stats.csv", "")
        )
        with open(path, newline="") as f:
            rows = list(csv.DictReader(f))
        agg = next(r for r in rows if r["Type"] == "")
        total = int(agg["Request Count"])
        fails = int(agg["Failure Count"])
        print(
            f"{tag}u | reqs={total} fails={fails} "
            f"({100*fails/total:.2f}%) | rps={float(agg['Requests/s']):.1f} "
            f"| p50={agg['50%']}ms p95={agg['95%']}ms "
            f"p99={agg['99%']}ms max={agg['Max Response Time']}ms"
        )

        if tag in ("10", "100"):
            print("   per-endpoint (name: reqs, fail%, p50, p95, p99):")
            for r in rows:
                if r["Type"] == "":
                    continue
                name = f"{r['Type']} {r['Name']}"
                reqs = int(r["Request Count"])
                if reqs == 0:
                    continue
                failpct = 100 * int(r["Failure Count"]) / reqs
                print(
                    f"     {name:38s} n={reqs:5d} "
                    f"fail={failpct:5.1f}% "
                    f"p50={r['50%']:>6s} p95={r['95%']:>6s} "
                    f"p99={r['99%']:>6s}"
                )


if __name__ == "__main__":
    main()
