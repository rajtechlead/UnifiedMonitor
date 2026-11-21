"""Tenant management endpoints."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, SecretStr

from unimonitor.auth.dependencies import get_current_user, require_role

logger = structlog.get_logger(__name__)
router = APIRouter()


# ── Pydantic schemas ─────────────────────────────────────────


class TenantCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=256)
    display_name: str = Field(..., min_length=1, max_length=256)
    entra_tenant_id: str = Field(..., description="Azure AD / Entra ID tenant GUID")
    client_id: str = Field(..., description="App registration client ID")
    client_secret: SecretStr = Field(..., description="App registration client secret")
    description: str | None = None
    is_msp_client: bool = False


class TenantUpdate(BaseModel):
    display_name: str | None = None
    client_id: str | None = None
    client_secret: SecretStr | None = None
    description: str | None = None
    is_active: bool | None = None


class TenantResponse(BaseModel):
    id: str
    name: str
    display_name: str | None = None
    entra_tenant_id: str | None = None
    client_id: str | None = None
    description: str | None = None
    is_active: bool
    is_msp_client: bool = False
    created_at: datetime | None = None
    last_collection_at: datetime | None = None
    last_collection_status: str | None = None

    model_config = {"from_attributes": True}


class TenantHealthResponse(BaseModel):
    tenant_id: str
    last_collection_at: datetime | None
    last_collection_status: str | None
    last_collection_error: str | None
    total_runs_24h: int
    failed_runs_24h: int
    graph_accessible: bool


class ConnectionTestResponse(BaseModel):
    success: bool
    tenant_name: str | None = None
    licensed_products: list[str] = []
    permissions_granted: list[str] = []
    permissions_missing: list[str] = []
    error: str | None = None


class PaginatedTenants(BaseModel):
    items: list[TenantResponse]
    total: int
    page: int
    page_size: int
    pages: int


class TenantRollupRow(BaseModel):
    tenant_id: str
    name: str
    display_name: str | None = None
    is_active: bool
    last_collection_at: datetime | None = None
    last_collection_status: str | None = None
    security_score: float
    compliance_score: float
    risk_score: float
    open_findings: int
    critical: int
    high: int
    medium: int
    suppressed: int
    coverage_pct: float
    weakest_framework_id: str | None = None
    weakest_framework_name: str | None = None
    weakest_framework_pct: float | None = None


class TenantRollupTotals(BaseModel):
    tenants: int
    mean_security_score: float
    mean_compliance_score: float
    open_findings: int
    critical: int
    high: int
    coverage_pct: float
    collection_failures: int


class TenantRollupResponse(BaseModel):
    tenants: list[TenantRollupRow]
    totals: TenantRollupTotals
    generated_at: datetime


# ── Endpoints ────────────────────────────────────────────────


@router.get("")
async def list_tenants(
    current_user: Annotated[Any, Depends(require_role("admin"))],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    search: str | None = Query(default=None),
    is_active: bool | None = Query(default=None),
) -> PaginatedTenants:
    """List all tenants (admin only)."""
    from unimonitor.db.base import async_session_factory
    from unimonitor.db.repositories.tenant_repo import TenantRepository

    async with async_session_factory() as session:
        repo = TenantRepository(session)
        tenants, total = await repo.list_paginated(
            page=page,
            page_size=page_size,
            search=search,
            is_active=is_active,
        )

    pages = max(1, (total + page_size - 1) // page_size)
    return PaginatedTenants(
        items=[TenantResponse.model_validate(t) for t in tenants],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_tenant(
    body: TenantCreate,
    current_user: Annotated[Any, Depends(require_role("admin"))],
) -> TenantResponse:
    """Create a new tenant."""
    from unimonitor.db.base import async_session_factory
    from unimonitor.db.repositories.tenant_repo import TenantRepository

    async with async_session_factory() as session:
        repo = TenantRepository(session)
        existing = await repo.get_by_entra_id(body.entra_tenant_id)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Tenant with Entra ID {body.entra_tenant_id} already exists",
            )
        tenant = await repo.create(
            name=body.name,
            display_name=body.display_name,
            entra_tenant_id=body.entra_tenant_id,
            client_id=body.client_id,
            client_secret=body.client_secret.get_secret_value(),
            description=body.description,
            is_msp_client=body.is_msp_client,
        )

    logger.info("tenant_created", tenant_id=tenant.id, name=tenant.name, by=current_user.id)
    return TenantResponse.model_validate(tenant)


@router.get("/rollup")
async def tenant_rollup(
    current_user: Annotated[Any, Depends(require_role("admin"))],
    include_coverage: bool = Query(default=True, description="Compute framework coverage per tenant"),
) -> TenantRollupResponse:
    """MSP rollup: one comparable row per tenant, plus managed totals.

    Every tenant gets its latest completed score, open exposure by severity and —
    when *include_coverage* is set — the framework drifting furthest from target.
    This is the cross-tenant view an MSP needs; the rest of the product is
    deliberately single-tenant.
    """
    from unimonitor.db.base import async_session_factory
    from unimonitor.grc.scoring import compute_framework_coverage

    async with async_session_factory() as session:
        from sqlalchemy import func, select

        from unimonitor.api.v1.controls import SUPPORTED_FRAMEWORKS
        from unimonitor.db.models.finding import Finding
        from unimonitor.db.repositories.assessment_repo import AssessmentRepository
        from unimonitor.db.repositories.tenant_repo import TenantRepository

        tenants, _ = await TenantRepository(session).list_paginated(page=1, page_size=200, is_active=True)

        open_rows = (
            await session.execute(
                select(Finding.tenant_id, Finding.severity, func.count(Finding.id))
                .where(
                    Finding.is_suppressed.is_(False),
                    Finding.state.in_(["not_implemented", "partially_implemented"]),
                )
                .group_by(Finding.tenant_id, Finding.severity)
            )
        ).all()
        open_by_tenant: dict[str, dict[str, int]] = {}
        for tenant_id, severity, count in open_rows:
            open_by_tenant.setdefault(tenant_id, {})[severity] = count

        suppressed_rows = (
            await session.execute(
                select(Finding.tenant_id, func.count(Finding.id)).where(Finding.is_suppressed.is_(True)).group_by(Finding.tenant_id)
            )
        ).all()
        suppressed_by_tenant = dict(suppressed_rows)

        framework_names = {fw["id"]: fw["name"] for fw in SUPPORTED_FRAMEWORKS}
        assessment_repo = AssessmentRepository(session)
        rows: list[TenantRollupRow] = []
        for tenant in tenants:
            latest = await assessment_repo.get_latest_completed_run(tenant_id=tenant.id)
            severities = open_by_tenant.get(tenant.id, {})
            security_score = (latest.security_score or 0.0) if latest else 0.0
            compliance_score = (latest.compliance_score or 0.0) if latest else 0.0
            risk_score = (latest.risk_score or 0.0) if latest else 0.0

            coverage_pct = 0.0
            weakest_id: str | None = None
            weakest_pct: float | None = None
            if include_coverage:
                coverages = await compute_framework_coverage(session, tenant_id=tenant.id)
                scored = [(fw_id, cov) for fw_id, cov in coverages.items() if cov.get("controls_total")]
                if scored:
                    coverage_pct = round(sum(cov["coverage_pct"] for _, cov in scored) / len(scored), 2)
                    weakest_id, weakest = min(scored, key=lambda item: item[1]["coverage_pct"])
                    weakest_pct = weakest["coverage_pct"]

            rows.append(
                TenantRollupRow(
                    tenant_id=tenant.id,
                    name=tenant.name,
                    display_name=tenant.display_name,
                    is_active=tenant.is_active,
                    last_collection_at=getattr(tenant, "last_collection_at", None),
                    last_collection_status=getattr(tenant, "last_collection_status", None),
                    security_score=security_score,
                    compliance_score=compliance_score,
                    risk_score=risk_score,
                    open_findings=sum(severities.values()),
                    critical=severities.get("critical", 0),
                    high=severities.get("high", 0),
                    medium=severities.get("medium", 0),
                    suppressed=suppressed_by_tenant.get(tenant.id, 0),
                    coverage_pct=coverage_pct,
                    weakest_framework_id=weakest_id,
                    weakest_framework_name=framework_names.get(weakest_id, weakest_id) if weakest_id else None,
                    weakest_framework_pct=weakest_pct,
                )
            )

    reported = [row for row in rows if row.security_score > 0 or row.open_findings]
    return TenantRollupResponse(
        tenants=sorted(rows, key=lambda row: (row.critical, row.high, row.open_findings), reverse=True),
        totals=TenantRollupTotals(
            tenants=len(rows),
            mean_security_score=round(sum(row.security_score for row in rows) / len(rows), 2) if rows else 0.0,
            mean_compliance_score=round(sum(row.compliance_score for row in rows) / len(rows), 2) if rows else 0.0,
            open_findings=sum(row.open_findings for row in rows),
            critical=sum(row.critical for row in rows),
            high=sum(row.high for row in rows),
            coverage_pct=round(sum(row.coverage_pct for row in reported) / len(reported), 2) if reported else 0.0,
            collection_failures=sum(1 for row in rows if row.last_collection_status == "failed"),
        ),
        generated_at=datetime.now(UTC),
    )


@router.get("/{tenant_id}")
async def get_tenant(
    tenant_id: str,
    current_user: Annotated[Any, Depends(get_current_user)],
) -> TenantResponse:
    """Get tenant by ID."""
    from unimonitor.db.base import async_session_factory
    from unimonitor.db.repositories.tenant_repo import TenantRepository

    async with async_session_factory() as session:
        repo = TenantRepository(session)
        tenant = await repo.get_by_id(tenant_id)
        if not tenant:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    return TenantResponse.model_validate(tenant)


@router.put("/{tenant_id}")
async def update_tenant(
    tenant_id: str,
    body: TenantUpdate,
    current_user: Annotated[Any, Depends(require_role("admin"))],
) -> TenantResponse:
    """Update tenant configuration."""
    from unimonitor.db.base import async_session_factory
    from unimonitor.db.repositories.tenant_repo import TenantRepository

    async with async_session_factory() as session:
        repo = TenantRepository(session)
        tenant = await repo.get_by_id(tenant_id)
        if not tenant:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

        updates = body.model_dump(exclude_none=True)
        if "client_secret" in updates:
            updates["client_secret"] = updates["client_secret"].get_secret_value()

        tenant = await repo.update(tenant_id, **updates)

    logger.info("tenant_updated", tenant_id=tenant_id, by=current_user.id)
    return TenantResponse.model_validate(tenant)


@router.delete("/{tenant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tenant(
    tenant_id: str,
    current_user: Annotated[Any, Depends(require_role("admin"))],
) -> None:
    """Soft-delete a tenant."""
    from unimonitor.db.base import async_session_factory
    from unimonitor.db.repositories.tenant_repo import TenantRepository

    async with async_session_factory() as session:
        repo = TenantRepository(session)
        tenant = await repo.get_by_id(tenant_id)
        if not tenant:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
        await repo.soft_delete(tenant_id)

    logger.info("tenant_deleted", tenant_id=tenant_id, by=current_user.id)


@router.post("/{tenant_id}/test-connection")
async def test_connection(
    tenant_id: str,
    current_user: Annotated[Any, Depends(require_role("admin"))],
) -> ConnectionTestResponse:
    """Test Graph API connectivity for a tenant."""
    from unimonitor.db.base import async_session_factory
    from unimonitor.db.repositories.tenant_repo import TenantRepository
    from unimonitor.graph.client import GraphClient

    async with async_session_factory() as session:
        repo = TenantRepository(session)
        tenant = await repo.get_by_id(tenant_id)
        if not tenant:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    # Required Graph API permissions for UniMonitor

    try:
        async with GraphClient(
            tenant_id=tenant.entra_tenant_id,
            client_id=tenant.client_id,
            client_secret=tenant.client_secret,
            cache_ttl=0,
        ) as client:
            # Test basic connectivity
            org_resp = await client.get("/organization")
            if not org_resp.success:
                return ConnectionTestResponse(
                    success=False,
                    error=org_resp.error_message or "Failed to reach Graph API",
                )

            org_data = org_resp.data
            if isinstance(org_data, list) and org_data:
                org_data = org_data[0]

            tenant_name = org_data.get("displayName", "Unknown") if isinstance(org_data, dict) else "Unknown"
            plans = org_data.get("assignedPlans", []) if isinstance(org_data, dict) else []
            licensed_products = list({p.get("service", "") for p in plans if p.get("capabilityStatus") == "Enabled"})

            # Test permission scopes via /v1.0/oauth2PermissionGrants or just probe endpoints
            permissions_granted = []
            permissions_missing = []
            probe_map = {
                "Organization.Read.All": "/organization",
                "Directory.Read.All": "/users?$top=1",
                "Policy.Read.All": "/policies/conditionalAccessPolicies?$top=1",
                "SecurityEvents.Read.All": "/security/alerts_v2?$top=1",
                "IdentityRiskyUser.Read.All": "/identityProtection/riskyUsers?$top=1",
                "DeviceManagementManagedDevices.Read.All": "/deviceManagement/managedDevices?$top=1",
                "Reports.Read.All": "/reports/getOffice365ActiveUserDetail(period='D7')",
            }

            for scope, endpoint in probe_map.items():
                try:
                    r = await client.get(endpoint, use_cache=False)
                    if r.success:
                        permissions_granted.append(scope)
                    else:
                        permissions_missing.append(scope)
                except Exception:
                    permissions_missing.append(scope)

            return ConnectionTestResponse(
                success=True,
                tenant_name=tenant_name,
                licensed_products=sorted(licensed_products),
                permissions_granted=permissions_granted,
                permissions_missing=permissions_missing,
            )

    except Exception as exc:
        logger.error("connection_test_failed", tenant_id=tenant_id, error=str(exc))
        return ConnectionTestResponse(success=False, error=str(exc))


@router.get("/{tenant_id}/health")
async def tenant_health(
    tenant_id: str,
    current_user: Annotated[Any, Depends(get_current_user)],
) -> TenantHealthResponse:
    """Return last collection health status for a tenant."""

    from unimonitor.db.base import async_session_factory
    from unimonitor.db.repositories.tenant_repo import TenantRepository

    async with async_session_factory() as session:
        repo = TenantRepository(session)
        tenant = await repo.get_by_id(tenant_id)
        if not tenant:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
        stats = await repo.get_collection_stats(tenant_id, hours=24)

    return TenantHealthResponse(
        tenant_id=tenant_id,
        last_collection_at=getattr(tenant, "last_collection_at", None),
        last_collection_status=getattr(tenant, "last_collection_status", None),
        last_collection_error=getattr(tenant, "last_collection_error", None),
        total_runs_24h=stats.get("total_runs", 0),
        failed_runs_24h=stats.get("failed_runs", 0),
        graph_accessible=stats.get("graph_accessible", False),
    )
