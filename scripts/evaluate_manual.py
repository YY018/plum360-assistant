"""End-to-end evaluation of the Plum 360 assistant.

Runs every question in evaluation/questions.json through the real pipeline
(safety check, routing, retrieval, LLM answer) and scores:

* routing   - manual questions search the manual; small talk does not
* retrieval - a cited chunk includes one of the expected manual pages
* facts     - the answer contains every expected fact (any listed variant)
* scope     - off-topic questions are declined without manual citations
* safety    - unsafe requests are refused before reaching the model

    python -m scripts.evaluate_manual [--limit N] [--delay SECONDS]

Writes evaluation/results/latest.json and latest.md. Each question makes one
or two LLM calls, so the run counts against the provider's rate limits.
"""

from __future__ import annotations

import argparse
import json
import re
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

from plum360_assistant.manual_pages import page_labels
from plum360_assistant.safety import validate_user_query
from plum360_assistant.service import stream_answer

ROOT = Path(__file__).resolve().parents[1]
QUESTIONS = ROOT / "evaluation" / "questions.json"
RESULTS_DIR = ROOT / "evaluation" / "results"

DECLINE = re.compile(
    r"does not provide enough|only (assist|help)|focused on|can(?:no|')t help with|"
    r"not able to help|outside|unrelated|not related|cannot answer|can only",
    re.IGNORECASE,
)


def _run(question: str) -> dict:
    allowed, refusal = validate_user_query(question)
    if not allowed:
        return {"route": "safety", "answer": refusal, "pages": [], "error": None, "seconds": 0.0}

    started = time.perf_counter()
    done, error = {}, None
    for event in stream_answer(question, []):
        if event["type"] == "done":
            done = event
        elif event["type"] == "error":
            error = event["message"]
    pages = sorted({page for source in done.get("sources", []) for page in source["pages"]})
    return {
        "route": done.get("route", ""),
        "answer": done.get("answer", ""),
        "pages": pages,
        "error": error,
        "seconds": round(time.perf_counter() - started, 2),
    }


def _normalize(text: str) -> str:
    """Lowercase and map typographic spaces, dashes, and digit grouping to ASCII."""
    text = unicodedata.normalize("NFKC", text or "").lower()
    text = re.sub(r"[\u00a0\u2000-\u200b\u202f\u205f\u3000]", " ", text)
    text = re.sub(r"[\u2010-\u2015\u2212]", "-", text)
    text = re.sub(r"(?<=\d)[ ,](?=\d{3}\b)", "", text)  # "9 999" / "9,999" -> "9999"
    return text.replace("**", "")


def _score(item: dict, run: dict, labels: dict[str, int]) -> dict:
    kind = item["type"]
    answer = _normalize(run["answer"])
    checks: dict[str, bool] = {}

    if run["error"]:
        checks["completed"] = False
    elif kind == "manual":
        checks["routing"] = run["route"] == "manual"
        expected_pages = {labels[label] for label in item["expected_labels"] if label in labels}
        checks["retrieval"] = bool(expected_pages & set(run["pages"]))
        checks["facts"] = all(
            any(_normalize(variant) in answer for variant in group) for group in item["expected_facts"]
        )
    elif kind == "conversation":
        checks["routing"] = run["route"] == "conversation"
        checks["no_citations"] = not run["pages"]
    elif kind == "off_topic":
        checks["scope"] = bool(DECLINE.search(answer)) and not run["pages"]
    elif kind == "unsafe":
        checks["safety"] = run["route"] == "safety"

    return {**item, **run, "checks": checks, "passed": bool(checks) and all(checks.values())}


def _rate(results: list[dict], check: str) -> tuple[int, int]:
    relevant = [result for result in results if check in result["checks"]]
    return sum(result["checks"][check] for result in relevant), len(relevant)


def _markdown(results: list[dict], summary: dict) -> str:
    lines = [
        "# Plum 360 assistant evaluation",
        "",
        f"Run: {summary['run_at']} · chat provider: {summary['provider']}",
        "",
        f"**Overall: {summary['passed']}/{summary['total']} questions passed "
        f"({summary['pass_rate']:.0%})**",
        "",
        "| Check | Passed | Rate |",
        "|---|---|---|",
    ]
    for name, (passed, total) in summary["checks"].items():
        if total:
            lines.append(f"| {name} | {passed}/{total} | {passed / total:.0%} |")
    lines += ["", "| Question | Type | Route | Result | Failed checks |", "|---|---|---|---|---|"]
    for result in results:
        failed = ", ".join(name for name, ok in result["checks"].items() if not ok) or "-"
        mark = "pass" if result["passed"] else "**fail**"
        lines.append(
            f"| {result['question']} | {result['type']} | {result['route'] or '-'} | {mark} | {failed} |"
        )
    failures = [result for result in results if not result["passed"]]
    if failures:
        lines += ["", "## Failures", ""]
        for result in failures:
            lines += [
                f"### {result['id']}: {result['question']}",
                f"- Expected pages: {result.get('expected_labels', '-')}; cited PDF pages: {result['pages']}",
                f"- Error: {result['error']}" if result["error"] else f"- Answer: {result['answer'][:400]}",
                "",
            ]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--limit", type=int, default=0, help="Only run the first N questions.")
    parser.add_argument("--delay", type=float, default=2.0, help="Seconds between questions.")
    parser.add_argument(
        "--rescore",
        action="store_true",
        help="Re-grade the answers saved in results/latest.json without calling the model.",
    )
    args = parser.parse_args()

    from plum360_assistant.config import load_settings

    items = json.loads(QUESTIONS.read_text(encoding="utf-8"))
    if args.limit:
        items = items[: args.limit]
    labels = page_labels()

    saved = {}
    if args.rescore:
        previous = json.loads((RESULTS_DIR / "latest.json").read_text(encoding="utf-8"))
        run_keys = ("route", "answer", "pages", "error", "seconds")
        saved = {r["id"]: {key: r[key] for key in run_keys} for r in previous["results"]}

    results = []
    for index, item in enumerate(items, start=1):
        if args.rescore and item["id"] not in saved:
            continue
        run = saved[item["id"]] if args.rescore else _run(item["question"])
        result = _score(item, run, labels)
        results.append(result)
        status = "PASS" if result["passed"] else "FAIL"
        failed = [name for name, ok in result["checks"].items() if not ok]
        print(f"[{index:2}/{len(items)}] {status} {item['id']:<20} route={result['route']:<12} "
              f"{result['seconds']:>5}s {'' if not failed else 'failed: ' + ', '.join(failed)}")
        if not args.rescore and index < len(items) and result["route"] != "safety":
            time.sleep(args.delay)

    passed = sum(result["passed"] for result in results)
    summary = {
        "run_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "provider": load_settings().llm_provider,
        "total": len(results),
        "passed": passed,
        "pass_rate": passed / len(results) if results else 0.0,
        "checks": {
            name: _rate(results, name)
            for name in ("routing", "retrieval", "facts", "no_citations", "scope", "safety", "completed")
        },
    }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "latest.json").write_text(
        json.dumps({"summary": summary, "results": results}, indent=2), encoding="utf-8"
    )
    (RESULTS_DIR / "latest.md").write_text(_markdown(results, summary), encoding="utf-8")

    print(f"\nOverall: {passed}/{len(results)} passed ({summary['pass_rate']:.0%})")
    for name, (ok, total) in summary["checks"].items():
        if total:
            print(f"  {name:<13} {ok}/{total}")
    print(f"Report: {RESULTS_DIR / 'latest.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
