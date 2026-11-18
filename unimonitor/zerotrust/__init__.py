"""Zero Trust assessment: import Microsoft's PowerShell results, score every platform.

The Microsoft Zero Trust Assessment is a PowerShell module that writes an HTML
report plus a JSON export. Running it needs an interactive admin sign-in and
Windows, so it runs on the administrator's machine and the export is imported
here; AWS, Google Cloud and Google Workspace checks are evaluated from the
evidence UniMonitor already collects.
"""

from unimonitor.zerotrust.normalise import (
    PLATFORMS,
    normalise_checks,
    pillar_for_text,
    summarise,
)

__all__ = ["PLATFORMS", "normalise_checks", "pillar_for_text", "summarise"]
