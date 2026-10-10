"""Run the 30-sample benchmark (Section 17.2).

    python evaluation/scripts/run_benchmark.py --conditions system baseline --runs 2 --out evaluation/results/<timestamp>/

* system   — the real pipeline in-process (same code as the API). LLM_PROVIDER=gemini for the real evaluation,
             LLM_PROVIDER=mock for a dry run.
* baseline — the same provider and model with baseline_user.txt only (no system prompt, numbering, static
             findings or schema).

Results are saved after every sample; --resume skips outputs that already exist, so an interrupted run
(e.g. the Gemini daily quota was reached) can continue the next day.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

from common import REPO_ROOT, RESULTS_DIR, load_ground_truth, read_sample, write_json


def _git_commit() -> str | None:
    try:
        out = subprocess.run(  # noqa: S603,S607 - fixed command, evaluation script only
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return out.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def _database_url(out: Path) -> str:
    """A separate database for benchmark runs (BENCHMARK_DATABASE_URL, or a SQLite file in the output folder)."""
    return os.environ.get("BENCHMARK_DATABASE_URL") or f"sqlite:///{(out / 'benchmark.db').as_posix()}"


class QuotaReached(Exception):
    pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--conditions",
        nargs="+",
        choices=["system", "baseline"],
        default=["system", "baseline"],
    )
    parser.add_argument("--runs", type=int, default=2)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--resume", action="store_true", help="skip outputs that already exist")
    parser.add_argument("--samples", nargs="*", help="only these sample IDs (e.g. P01 J04)")
    args = parser.parse_args(argv)

    out: Path = args.out or RESULTS_DIR / dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    out.mkdir(parents=True, exist_ok=True)
    db_url = _database_url(out)

    from app.config import get_settings
    from app.db import SessionLocal, init_db, run_migrations
    from app.llm import prompt_builder
    from app.llm.client import LLMError, get_llm_client
    from app.pipeline.orchestrator import run_pipeline_for_code
    from app.seed import seed
    from app.services import settings_service

    settings = get_settings()
    run_migrations(db_url)
    init_db(db_url)
    with SessionLocal() as db:
        seed(db)
        values = settings_service.get(db)

    gt = load_ground_truth()
    sample_ids = [s for s in gt if not args.samples or s in args.samples]
    client = get_llm_client()
    manifest = {
        "created_at": dt.datetime.now(dt.UTC).isoformat(),
        "provider": settings.LLM_PROVIDER,
        "model": settings.LLM_MODEL if settings.LLM_PROVIDER != "mock" else "mock-v1",
        "prompt_version": settings.PROMPT_VERSION,
        "conditions": args.conditions,
        "runs": args.runs,
        "samples": sample_ids,
        "git_commit": _git_commit(),
        "python": platform.python_version(),
        "settings": {
            "llm_temperature": values["llm_temperature"],
            "consistency_check_enabled": values["consistency_check_enabled"],
            "enabled_tools": values["enabled_tools"],
            "gemini_thinking": settings.GEMINI_THINKING,
            "max_output_tokens": settings.LLM_MAX_OUTPUT_TOKENS,
        },
    }
    manifest_path = out / "manifest.json"
    if manifest_path.exists() and args.resume:
        previous = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["resumed_from"] = previous.get("created_at")
    write_json(manifest_path, manifest)

    jobs = [
        (sid, run, cond) for sid in sample_ids for run in range(1, args.runs + 1) for cond in args.conditions
    ]
    total = len(jobs)
    started = time.monotonic()
    done_now = 0
    try:
        for index, (sid, run, cond) in enumerate(jobs, start=1):
            entry = gt[sid]
            target = out / cond / (f"{sid}_run{run}.json" if cond == "system" else f"{sid}_run{run}.txt")
            if args.resume and target.exists():
                continue
            code = read_sample(entry)
            t0 = time.monotonic()
            if cond == "system":
                report = run_pipeline_for_code(code, entry["language"], Path(entry["file"]).name)
                if report["overview"]["ai_unavailable_reason"] == "quota_exhausted":
                    raise QuotaReached()
                write_json(target, {"sample_id": sid, "run": run, "report": report})
            else:
                prompt = prompt_builder.baseline_prompt(code, entry["language"], settings.PROMPT_VERSION)
                try:
                    result = client.complete(
                        None,
                        prompt,
                        temperature=float(values["llm_temperature"]),
                        max_output_tokens=settings.LLM_MAX_OUTPUT_TOKENS,
                        timeout_s=settings.LLM_TIMEOUT_SECONDS,
                        json_mode=False,
                    )
                except LLMError as e:
                    if e.kind == "quota_exhausted":
                        raise QuotaReached() from e
                    print(
                        f"  ! baseline {sid} run {run} failed: {e.kind} — rerun with --resume",
                        file=sys.stderr,
                    )
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(result.text, encoding="utf-8")
            done_now += 1
            elapsed = time.monotonic() - started
            remaining = (elapsed / done_now) * (total - index) if done_now else 0
            print(
                f"[{index}/{total}] {cond:8s} {sid} run {run}  ({time.monotonic() - t0:.1f}s)  "
                f"~{remaining / 60:.1f} min left"
            )
    except QuotaReached:
        print(
            "\nThe free Gemini quota for today has been used up. Run the same command again with --resume "
            "after midnight Pacific time to continue.",
            file=sys.stderr,
        )
        return 2
    print(f"\nDone. Results in {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
