"""Small extension contracts for third-party ARX detectors and rules."""
from typing import Any, Protocol

class MachineScanner(Protocol):
    def scan(self, deep: bool = True) -> dict[str, Any]: ...

class SoftwareScanner(Protocol):
    def scan(self, target: str) -> dict[str, Any]: ...

class CapabilityProvider(Protocol):
    def capabilities(self, machine: dict[str, Any]) -> dict[str, Any]: ...

class CompatibilityRule(Protocol):
    def evaluate(self, machine: dict[str, Any], software: dict[str, Any]) -> dict[str, Any]: ...

class Exporter(Protocol):
    def render(self, report: dict[str, Any]) -> str: ...
