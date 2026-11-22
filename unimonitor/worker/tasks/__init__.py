"""Celery tasks.

Re-exported here so callers can ``from unimonitor.worker.tasks import ...``;
the API used this import path but the package only had a docstring, so report
generation silently fell into its "Celery unavailable" branch every time.
"""

from unimonitor.worker.tasks.assessment import run_assessment_task
from unimonitor.worker.tasks.remediation import generate_ai_remediation_task
from unimonitor.worker.tasks.reporting import generate_report_task

__all__ = ["generate_ai_remediation_task", "generate_report_task", "run_assessment_task"]
