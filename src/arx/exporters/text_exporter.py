def render_summary(report):
    compatibility=report.get("compatibility") or {}
    return "\n".join(("ARX compatibility report",f"Status: {compatibility.get('status','unknown').upper()}",f"Score: {compatibility.get('score','n/a')}",*(f"Blocker: {item}" for item in compatibility.get("blockers",[]))))
