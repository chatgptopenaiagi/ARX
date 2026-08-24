from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

class EvidenceKind(str, Enum):
    DECLARED="declared"; OBSERVED="observed"; INFERRED="inferred"; ESTIMATED="estimated"; SIMULATED="simulated"; STRUCTURAL="structural"; UNKNOWN="unknown"
class Status(str, Enum):
    READY="ready"; PARTIAL="partial"; BLOCKED="blocked"; UNKNOWN="unknown"; NOT_APPLICABLE="not_applicable"; MISSING="missing"

@dataclass
class Evidence:
    kind: EvidenceKind; source: str; value: Any; method: str; confidence: float=1.0; note: str|None=None
@dataclass
class ToolRecord:
    name: str; detected: bool; version: str|None=None; path: str|None=None; evidence: list[Evidence]=field(default_factory=list); probe_method: str="command"; confidence: float=1.0; notes: list[str]=field(default_factory=list)
@dataclass
class Capability:
    name: str; status: Status; reason: str; dependencies: list[str]=field(default_factory=list); evidence: list[Evidence]=field(default_factory=list)

def utc_now(): return datetime.now(timezone.utc).isoformat()
def serialize(value):
    if hasattr(value,"__dataclass_fields__"): value=asdict(value)
    if isinstance(value,Enum): return value.value
    if isinstance(value,Path): return str(value)
    if isinstance(value,dict): return {k:serialize(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)): return [serialize(v) for v in value]
    return value

