"""Command line entry point for explicit AI operations."""
import argparse
import json
import uuid
from datetime import datetime

from .engine import DEFAULT_ROOT, discover, preserve, verify, write_reports


def configure(parser):
    parser.add_argument("--root", action="append", default=[], help="Additional bounded environment search directory")
    parser.add_argument("--python", action="append", dest="interpreters", help="Explicit interpreter; repeatable")
    parser.add_argument("--verify", action="store_true", help="Run bounded tests in every detected torch environment")
    parser.add_argument("--benchmark", action="store_true", help="Verify and run six short benchmarks")
    parser.add_argument("--preserve", action="store_true", help="Copy packages from one explicitly selected, verified interpreter")
    parser.add_argument("--preserve-to", help="Preservation parent directory; always creates a unique child")
    parser.add_argument("--reports-dir", help="Report destination; defaults to a unique repair-workspace directory")
    return parser


def run_cli(args):
    if args.preserve and (not args.interpreters or len(args.interpreters) != 1):
        raise ValueError("--preserve requires exactly one --python to prevent copying an unintended environment")
    report = discover(args.root, interpreters=args.interpreters)
    if args.verify or args.benchmark or args.preserve:
        for env in report["environments"]:
            if any(p["name"].lower()=="torch" for p in env.get("packages", [])):
                report["verification"].append(verify(env, benchmark=args.benchmark))
    if args.preserve:
        verified = {v["environment_id"] for v in report["verification"] if v["health"]=="VERIFIED"}
        target = next((e for e in report["environments"] if not e.get("user_site") and e["id"] in verified), None)
        if target is None: raise ValueError("Selected isolated environment did not pass all required verification checks")
        report["preservation"].append(preserve(target, args.preserve_to))
    destination = args.reports_dir or DEFAULT_ROOT/("ARX-AI-"+datetime.now().strftime("%Y%m%d-%H%M%S")+"-"+uuid.uuid4().hex[:6])
    write_reports(report, destination)
    print(json.dumps({"reports":str(destination), "environments":len(report["environments"]), "verification":[{"environment":v["executable"], "health":v["health"]} for v in report["verification"]]}, indent=2))
    if (args.verify or args.benchmark or args.preserve) and not report["verification"]: return 2
    return 2 if any(v["health"]!="VERIFIED" for v in report["verification"]) or any(p["status"]!="PRESERVED" for p in report["preservation"]) else 0


def main(argv=None):
    parser = configure(argparse.ArgumentParser(description="ARX AI Compute — explicit discovery, testing and preservation"))
    args = parser.parse_args(argv)
    try: return run_cli(args)
    except (OSError, ValueError, RuntimeError) as exc: parser.error(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
