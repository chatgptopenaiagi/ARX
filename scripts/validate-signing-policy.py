"""Validate public ARX signing policy without resolving signing credentials."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCHEMA = ROOT / "security" / "signing" / "signing-policy.schema.json"
FORBIDDEN_KEY_PARTS = {
    "password",
    "private_key",
    "secret",
    "token",
    "pfx",
    "pin",
}


def _walk_keys(value: object) -> list[str]:
    keys: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            keys.append(str(key).casefold())
            keys.extend(_walk_keys(item))
    elif isinstance(value, list):
        for item in value:
            keys.extend(_walk_keys(item))
    return keys


def validate_policy(policy: object, schema: object) -> None:
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.validate(policy, schema, format_checker=jsonschema.FormatChecker())
    if not isinstance(policy, dict):
        raise ValueError("Signing policy must be a JSON object.")
    forbidden = sorted(
        key
        for key in _walk_keys(policy)
        if any(part in key for part in FORBIDDEN_KEY_PARTS)
    )
    if forbidden:
        raise ValueError("Signing policy contains a forbidden secret-bearing field name.")

    if policy["state"] == "UNCONFIGURED":
        if any(
            policy[field] not in (None, [])
            for field in (
                "signing_provider",
                "certificate_selector",
                "timestamp_url",
                "expected_publisher_subject",
                "expected_issuer_subjects",
            )
        ):
            raise ValueError("An unconfigured signing policy must not imply a signing identity.")
        return

    required = (
        "signing_provider",
        "certificate_selector",
        "timestamp_url",
        "expected_publisher_subject",
        "expected_issuer_subjects",
    )
    if any(not policy[field] for field in required):
        raise ValueError("A configured signing policy is missing required public identity metadata.")
    parsed = urlsplit(policy["timestamp_url"])
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("Timestamp URL is invalid.") from exc
    if (
        parsed.scheme.casefold() != "https"
        or not parsed.hostname
        or port not in (None, 443)
        or parsed.username is not None
        or parsed.password is not None
        or not parsed.path
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(
            "Timestamp URL must use credential-free HTTPS on the default port "
            "with a fixed path and no query or fragment."
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("policy", type=Path)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    arguments = parser.parse_args()
    policy = json.loads(arguments.policy.read_text(encoding="utf-8"))
    schema = json.loads(arguments.schema.read_text(encoding="utf-8"))
    validate_policy(policy, schema)
    print(f"Signing policy: VALID ({policy['state']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
