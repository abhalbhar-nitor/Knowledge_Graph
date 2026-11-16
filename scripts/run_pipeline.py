"""Run all 16 stages headless (same code the UI calls).

    python scripts/run_pipeline.py                 # in-memory sample data, offline AI fixture
    python scripts/run_pipeline.py --postgres      # PG* settings from env / .env
    python scripts/run_pipeline.py --use-groq      # real Groq call (needs GROQ_API_KEY)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from kg.core.context import PipelineContext  # noqa: E402
from kg.pipeline import run_all  # noqa: E402
from kg.stages import s02_connect  # noqa: E402

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--postgres", action="store_true")
    ap.add_argument("--use-groq", action="store_true")
    ap.add_argument("--author", default="data.modeller")
    ap.add_argument("--reviewer", default="reviewer.lead")
    args = ap.parse_args()

    ctx = run_all(PipelineContext(), postgres=s02_connect.env_defaults() if args.postgres else None,
                  use_groq=args.use_groq, author=args.author, reviewer=args.reviewer)
    for e in ctx.events:
        print(f"[{e['time']}] S{e['stage']:02d} {e['level']:7s} {e['message']}")
    if ctx.ontology_report is not None and not ctx.ontology_report.ok:
        for i in ctx.ontology_report.issues:
            print(" ", i.level, i.code, i.path, i.message)
    gr = ctx.graph_report
    if gr is None:
        print("\nPipeline stopped early; see the log above.")
        return 1
    print("\nnodes_by_class:", gr["nodes_by_class"])
    print("edges_by_type:", gr["edges_by_type"])
    print("errors:", gr["errors"])
    print("snapshot:", ctx.snapshot["path"], "published:", ctx.snapshot["published"])
    return 0 if gr["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
