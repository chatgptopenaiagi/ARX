import argparse,json,sys
from pathlib import Path

def main(argv=None):
    parser=argparse.ArgumentParser(add_help=False)
    parser.add_argument("--smoke-test",nargs=2,metavar=("TARGET","OUTPUT"))
    parser.add_argument("--ui-smoke-test",nargs=2,metavar=("TARGET","OUTPUT"))
    parser.add_argument("--project-ui-smoke-test",nargs=2,metavar=("PROJECT","OUTPUT"))
    parser.add_argument("--ai-ui-smoke-test",nargs=3,metavar=("PYTHON","INVENTORY","OUTPUT"))
    parser.add_argument("--ai-report",type=Path)
    args,_=parser.parse_known_args(argv)
    if args.ai_ui_smoke_test:
        from .ai_compute import ai_ui_smoke_test
        result=ai_ui_smoke_test(*args.ai_ui_smoke_test)
        return 0 if result["health"]=="VERIFIED" and result["display_matches_result"] else 2
    if args.smoke_test:
        from .controllers import smoke_test
        target,output=args.smoke_test;result=smoke_test(target,output);Path(str(output)+".result.json").write_text(json.dumps(result,indent=2),encoding="utf-8");return 0
    if args.ui_smoke_test:
        from .app import ui_smoke_test
        target,output=args.ui_smoke_test;result=ui_smoke_test(target,output);Path(str(output)+".result.json").write_text(json.dumps(result,indent=2),encoding="utf-8");return 0
    if args.project_ui_smoke_test:
        from .app import project_ui_smoke_test
        target,output=args.project_ui_smoke_test;result=project_ui_smoke_test(target,output);Path(str(output)+".result.json").write_text(json.dumps(result,indent=2),encoding="utf-8");return 0
    from .app import run
    run(ai_report=args.ai_report);return 0

if __name__=="__main__":raise SystemExit(main())
