"""Run the sanitised single-project municipal workflow acceptance check."""

from __future__ import annotations

import argparse
import json
import sys

from adapters.municipal_workflow import persist_municipal_demo, run_municipal_workflow


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify the complete BuildCostIQ municipal project workflow")
    parser.add_argument("--project-id", default="municipal-road-demo-2026")
    parser.add_argument("--json", action="store_true", help="print the complete acceptance packet")
    parser.add_argument("--persist", action="store_true", help="persist the validated packet into runtime/projects")
    args = parser.parse_args(argv)
    result = run_municipal_workflow(args.project_id)
    if args.persist and result["status"] == "PASSED":
        persist_municipal_demo(result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    else:
        checks = result["checks"]
        print(f"municipal workflow: {result['status']}")
        for name, passed in checks.items():
            print(f"{'PASS' if passed else 'FAIL'}  {name}")
        suffix = " persisted=runtime/projects" if args.persist else ""
        print(f"project={result['project']['id']} events={len(result['events'])} p09_open={result['p09']['summary']['open_event_count']}{suffix}")
    return 0 if result["status"] == "PASSED" else 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
