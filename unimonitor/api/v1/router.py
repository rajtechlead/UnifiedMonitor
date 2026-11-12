"""Master API v1 router — assembles all sub-routers."""

from __future__ import annotations

from fastapi import APIRouter

from unimonitor.api.v1.assessments import router as assessments_router
from unimonitor.api.v1.auth import router as auth_router
from unimonitor.api.v1.controls import router as controls_router
from unimonitor.api.v1.dashboard import router as dashboard_router
from unimonitor.api.v1.findings import router as findings_router
from unimonitor.api.v1.grc import router as grc_router
from unimonitor.api.v1.monitoring import router as monitoring_router
from unimonitor.api.v1.notifications import router as notifications_router
from unimonitor.api.v1.reports import router as reports_router
from unimonitor.api.v1.tenants import router as tenants_router

api_v1_router = APIRouter()

api_v1_router.include_router(auth_router, prefix="/auth", tags=["Authentication"])
api_v1_router.include_router(tenants_router, prefix="/tenants", tags=["Tenants"])
api_v1_router.include_router(assessments_router, prefix="/assessments", tags=["Assessments"])
api_v1_router.include_router(findings_router, prefix="/findings", tags=["Findings"])
api_v1_router.include_router(controls_router, prefix="/controls", tags=["Controls"])
api_v1_router.include_router(dashboard_router, prefix="/dashboard", tags=["Dashboard"])
api_v1_router.include_router(reports_router, prefix="/reports", tags=["Reports"])
api_v1_router.include_router(grc_router, prefix="/grc", tags=["GRC"])
api_v1_router.include_router(monitoring_router, prefix="/monitoring", tags=["Monitoring"])
api_v1_router.include_router(notifications_router, prefix="/notifications", tags=["Notifications"])
