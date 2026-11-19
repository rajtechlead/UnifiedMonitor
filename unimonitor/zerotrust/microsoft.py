"""The Microsoft Zero Trust test catalogue.

Microsoft's Zero Trust Assessment runs 364 PowerShell tests. The rows live in
:mod:`unimonitor.zerotrust.microsoft_tests`, generated from the upstream test
metadata by ``scripts/import_zt_tests.py``. This module gives them names and
resolves each test's pillar.

A test is evaluated from UniMonitor's own evidence only when a control declares
its id in ``ms_zt_tests``; everything else is reported as ``not_run``, because a
test this install cannot execute must not be scored as a pass.
"""

from __future__ import annotations

from dataclasses import dataclass

from unimonitor.zerotrust import microsoft_tests
from unimonitor.zerotrust.normalise import pillar_for_text


@dataclass(frozen=True, slots=True)
class MicrosoftTest:
    """One upstream Zero Trust test, as metadata."""

    id: str
    title: str
    pillar: str
    category: str
    severity: str
    license: str


def _pillar(row_pillar: str, title: str, category: str) -> str:
    """Upstream pillar, or the best guess from the text when it declares none."""
    if row_pillar:
        return row_pillar
    return pillar_for_text(f"{title} {category}") or "identity"


TESTS: tuple[MicrosoftTest, ...] = tuple(
    MicrosoftTest(
        id=test_id,
        title=title,
        pillar=_pillar(pillar, title, category),
        category=category,
        severity=severity,
        license=licence,
    )
    for test_id, title, pillar, category, severity, licence in microsoft_tests.ROWS
)

TESTS_BY_ID: dict[str, MicrosoftTest] = {test.id: test for test in TESTS}

TEST_IDS = frozenset(TESTS_BY_ID)
