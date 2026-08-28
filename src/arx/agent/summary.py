from __future__ import annotations

from .models import AgentDNASnapshot


def summary_text(snapshot: AgentDNASnapshot) -> str:
    counts = snapshot.summary["status_counts"]
    ordered = ("PASS", "FAIL", "BLOCKED", "UNKNOWN", "NOT_TESTED", "NOT_APPLICABLE")
    lines = [
        "ARX - AGENT DNA",
        "",
        f"Agent: {snapshot.agent.name}",
        f"Snapshot: {snapshot.snapshot_id}",
        f"Capabilities: {snapshot.summary['capability_record_count']}",
        "States: " + ", ".join(f"{key}={counts.get(key, 0)}" for key in ordered),
        f"Contradictions: {snapshot.summary['contradiction_count']}",
        f"Interventions: {snapshot.summary['intervention_count']}",
        "Machine DNA reference: unresolved" if snapshot.machine_reference.status == "UNRESOLVED" else f"Machine DNA reference: {snapshot.machine_reference.machine_dna_id}",
    ]
    return "\n".join(lines)
