"""Master API v1 router — assembles all sub-routers."""

from __future__ import annotations

from fastapi import APIRouter

from unimonitor.api.v1.ai import router as ai_router
from unimonitor.api.v1.alerts import router as alerts_router
from unimonitor.api.v1.assessments import router as assessments_router
from unimonitor.api.v1.audit_portal import router as audit_portal_router
from unimonitor.api.v1.auth import router as auth_router
from unimonitor.api.v1.controls import router as controls_router
from unimonitor.api.v1.dashboard import router as dashboard_router
from unimonitor.api.v1.findings import router as findings_router
from unimonitor.api.v1.grc import router as grc_router
from unimonitor.api.v1.integrations import router as integrations_router
from unimonitor.api.v1.monitoring import router as monitoring_router
from unimonitor.api.v1.notifications import router as notifications_router
from unimonitor.api.v1.onboarding import router as onboarding_router
from unimonitor.api.v1.posture import router as posture_router
from unimonitor.api.v1.reports import router as reports_router
from unimonitor.api.v1.search import router as search_router
from unimonitor.api.v1.settings import router as settings_router
from unimonitor.api.v1.tenants import router as tenants_router
from unimonitor.api.v1.users import router as users_router
from unimonitor.api.v1.zerotrust import router as zerotrust_router

api_v1_router = APIRouter()

api_v1_router.include_router(auth_router, prefix="/auth", tags=["Authentication"])
api_v1_router.include_router(ai_router, prefix="/ai", tags=["AI"])
api_v1_router.include_router(alerts_router, prefix="/alerts", tags=["Alerts"])
api_v1_router.include_router(tenants_router, prefix="/tenants", tags=["Tenants"])
api_v1_router.include_router(users_router, prefix="/users", tags=["Users"])
api_v1_router.include_router(assessments_router, prefix="/assessments", tags=["Assessments"])
api_v1_router.include_router(findings_router, prefix="/findings", tags=["Findings"])
api_v1_router.include_router(controls_router, prefix="/controls", tags=["Controls"])
api_v1_router.include_router(dashboard_router, prefix="/dashboard", tags=["Dashboard"])
api_v1_router.include_router(reports_router, prefix="/reports", tags=["Reports"])
api_v1_router.include_router(grc_router, prefix="/grc", tags=["GRC"])
api_v1_router.include_router(audit_portal_router, prefix="/grc", tags=["Auditor Portal"])
api_v1_router.include_router(integrations_router, prefix="/integrations", tags=["Integrations"])
api_v1_router.include_router(monitoring_router, prefix="/monitoring", tags=["Monitoring"])
api_v1_router.include_router(notifications_router, prefix="/notifications", tags=["Notifications"])
api_v1_router.include_router(posture_router, prefix="/posture", tags=["Posture"])
api_v1_router.include_router(onboarding_router, prefix="/onboarding", tags=["Setup"])
api_v1_router.include_router(search_router, prefix="/search", tags=["Search"])
api_v1_router.include_router(settings_router, prefix="/settings", tags=["Settings"])
api_v1_router.include_router(zerotrust_router, prefix="/zerotrust", tags=["Zero Trust Assessment"])

__all__ = ["api_v1_router"]
