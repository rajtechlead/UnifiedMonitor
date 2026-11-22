#!/usr/bin/env python3
"""Regenerate the Microsoft Zero Trust test catalogue from the upstream clone.

Microsoft's Zero Trust Assessment ships one PowerShell file per test, each with a
``[ZtTest(...)]`` attribute block. This reads that metadata and writes the Python
catalogue the assessment engine scores against, so the port can be refreshed when
the upstream project adds tests:

    python scripts/import_zt_tests.py \
        --source reference/zerotrustassessment/src/powershell/tests

Only metadata is copied. A test is *evaluated* here when one of UniMonitor's
controls declares its ``ms_zt_tests`` id; otherwise it is reported as ``not_run``
rather than assumed to pass.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "reference" / "zerotrustassessment" / "src" / "powershell" / "tests"
DEFAULT_OUTPUT = ROOT / "unimonitor" / "zerotrust" / "microsoft_tests.py"

_ATTRIBUTE = re.compile(r"\[ZtTest\((.*?)\)\]", re.DOTALL)
# The value is read by _literal_at rather than by the pattern: matching a quoted
# string with a repeated inner group backtracks super-linearly on unterminated
# input, and no PowerShell-literal regex avoids that.
_FIELD = re.compile(r"(\w+)\s*=\s*")


def _literal_at(text: str, index: int) -> str:
    """Read one PowerShell literal starting at *index*: '...', (...) or a number."""
    while index < len(text) and text[index].isspace():
        index += 1
    start = index
    if index < len(text) and text[index] == "'":
        index += 1
        while index < len(text):
            if text[index] == "'":
                # A doubled quote is an escaped apostrophe inside the string.
                if index + 1 < len(text) and text[index + 1] == "'":
                    index += 2
                    continue
                return text[start : index + 1]
            index += 1
        return text[start:]
    if index < len(text) and text[index] == "(":
        depth = 0
        while index < len(text):
            if text[index] == "(":
                depth += 1
            elif text[index] == ")":
                depth -= 1
                if depth == 0:
                    return text[start : index + 1]
            index += 1
        return text[start:]
    while index < len(text) and text[index] not in ",)":
        index += 1
    return text[start:index].strip()


def _fields(text: str) -> list[tuple[str, str]]:
    """(name, raw value) for every ``Name = value`` in a [ZtTest(...)] block."""
    return [(match.group(1), _literal_at(text, match.end())) for match in _FIELD.finditer(text)]


# Upstream pillars whose spelling differs from UniMonitor's pillar ids.
_PILLARS = {
    "identity": "identity",
    "devices": "devices",
    "network": "network",
    "data": "data",
    "infrastructure": "infrastructure",
    "secops": "secops",
    "ai": "ai",
}

_SEVERITIES = {"high": "high", "medium": "medium", "low": "low"}


def _values(raw: str) -> list[str]:
    """Split a PowerShell literal (quoted string or tuple) into plain values.

    Commas inside a quoted title are part of the title, not separators.
    """
    text = raw.strip()
    if text.startswith("(") and text.endswith(")"):
        text = text[1:-1].strip()
    parts: list[str] = []
    current = ""
    quoted = False
    for character in text:
        if character == "'":
            quoted = not quoted
            current += character
        elif character == "," and not quoted:
            parts.append(current)
            current = ""
        else:
            current += character
    parts.append(current)
    return [part.strip().strip("'").replace("''", "'") for part in parts if part.strip().strip("'")]


def _parse(path: Path) -> dict[str, str] | None:
    attributes = _ATTRIBUTE.search(path.read_text(encoding="utf-8-sig"))
    if attributes is None:
        return None
    fields = {name: _values(raw) for name, raw in _fields(attributes.group(1))}

    def first(name: str) -> str:
        values = fields.get(name) or []
        return values[0] if values else ""

    test_id = first("TestId")
    title = first("Title")
    if not test_id or not title:
        return None

    pillar = _PILLARS.get(first("Pillar").lower(), "")
    severity = _SEVERITIES.get(first("RiskLevel").lower(), "medium")
    licences = fields.get("MinimumLicense") or []
    return {
        "id": test_id,
        "title": title,
        "pillar": pillar,
        "category": first("Category"),
        "severity": severity,
        "license": " / ".join(licences),
    }


def collect(source: Path) -> list[dict[str, str]]:
    tests: dict[str, dict[str, str]] = {}
    for path in sorted(source.glob("Test-Assessment.*.ps1")):
        parsed = _parse(path)
        if parsed is not None:
            tests[parsed["id"]] = parsed
    return [tests[key] for key in sorted(tests, key=lambda value: (len(value), value))]


def render(tests: list[dict[str, str]]) -> str:
    rows = "".join(
        "    (" + ", ".join(json.dumps(test[field]) for field in ("id", "title", "pillar", "category", "severity", "license")) + "),\n"
        for test in tests
    )
    return (
        "# ruff: noqa: E501\n"
        "# One row per test. Upstream titles and licence lists are long, so lines overrun.\n"
        '"""The Microsoft Zero Trust Assessment test catalogue (generated).\n\n'
        "Each row is ``(test id, title, pillar, category, severity, minimum licence)``,\n"
        "read from the upstream PowerShell tests. Regenerate with\n"
        "``python scripts/import_zt_tests.py`` after refreshing the reference clone;\n"
        "do not edit by hand.\n"
        '"""\n\n'
        "from __future__ import annotations\n\n"
        'UPSTREAM = "https://github.com/microsoft/zerotrustassessment"\n\n'
        "ROWS: tuple[tuple[str, str, str, str, str, str], ...] = (\n"
        f"{rows}"
        ")\n\n"
        f"TEST_COUNT = {len(tests)}\n"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE, help="upstream tests directory")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="catalogue module to write")
    args = parser.parse_args(argv)

    if not args.source.is_dir():
        print(f"No upstream tests at {args.source}. Run scripts/update-reference-repos.sh first.", file=sys.stderr)
        return 1

    tests = collect(args.source)
    if not tests:
        print(f"No [ZtTest(...)] metadata found under {args.source}.", file=sys.stderr)
        return 1

    args.output.write_text(render(tests), encoding="utf-8")
    print(f"Wrote {len(tests)} tests to {args.output.relative_to(ROOT) if args.output.is_relative_to(ROOT) else args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
