"""Control library endpoints."""

from __future__ import annotations

from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from unimonitor.auth.dependencies import get_current_user

logger = structlog.get_logger(__name__)
router = APIRouter()


# ── Schemas ──────────────────────────────────────────────────


class ComplianceMapping(BaseModel):
    framework: str
    control_id: str
    control_name: str


class ControlResponse(BaseModel):
    id: str
    external_id: str
    name: str
    description: str
    category: str
    service: str
    severity: str
    is_active: bool
    framework_mappings: list[ComplianceMapping] = []
    remediation_steps: list[str] = []
    references: list[str] = []
    tags: list[str] = []

    model_config = {"from_attributes": True}


class FrameworkControlSummary(BaseModel):
    id: str
    external_id: str
    name: str
    category: str
    severity: str


class FrameworkResponse(BaseModel):
    id: str
    name: str
    version: str
    description: str
    total_controls: int
    controls: list[FrameworkControlSummary] = []


class PaginatedControls(BaseModel):
    items: list[ControlResponse]
    total: int
    page: int
    page_size: int
    pages: int


# ── Supported frameworks registry ────────────────────────────

SUPPORTED_FRAMEWORKS = [
    {"id": "iso27001-2022", "name": "ISO 27001:2022", "version": "2022"},
    {"id": "iso42001", "name": "ISO 42001", "version": "2023"},
    {"id": "nist-csf-2", "name": "NIST CSF 2.0", "version": "2.0"},
    {"id": "nist-800-53-r5", "name": "NIST 800-53 Rev 5", "version": "Rev 5"},
    {"id": "cis-controls-v8", "name": "CIS Controls v8", "version": "v8"},
    {"id": "microsoft-zero-trust", "name": "Microsoft Zero Trust", "version": "2024"},
    {"id": "cis-m365", "name": "CIS Microsoft 365 Benchmark", "version": "v3.1"},
    {"id": "soc2", "name": "SOC 2", "version": "2017"},
    {"id": "pci-dss-4", "name": "PCI-DSS 4.0", "version": "4.0"},
    {"id": "hipaa", "name": "HIPAA", "version": "2024"},
    {"id": "gdpr", "name": "GDPR", "version": "2018"},
    {"id": "cpcsc", "name": "CPCSC", "version": "2024"},
    {"id": "cmmc-2", "name": "CMMC 2.0", "version": "2.0"},
]


# ── Endpoints ────────────────────────────────────────────────


@router.get("", response_model=PaginatedControls)
async def list_controls(
    current_user: Annotated[Any, Depends(get_current_user)],
    category: str | None = Query(default=None),
    service: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    framework: str | None = Query(default=None),
    search: str | None = Query(default=None),
    is_active: bool | None = Query(default=True),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
) -> PaginatedControls:
    """List all controls with filtering and pagination."""
    from unimonitor.db.base import async_session_factory
    from unimonitor.grc.control_loader import ControlLibrary

    async with async_session_factory() as session:
        library = ControlLibrary(session)
        controls, total = await library.list_controls(
            category=category,
            service=service,
            severity=severity,
            framework=framework,
            search=search,
            is_active=is_active,
            page=page,
            page_size=page_size,
        )

    pages = max(1, (total + page_size - 1) // page_size)
    return PaginatedControls(
        items=[ControlResponse.model_validate(c) for c in controls],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get("/frameworks", response_model=list[dict])
async def list_frameworks(
    current_user: Annotated[Any, Depends(get_current_user)],
) -> list[dict]:
    """List all supported compliance frameworks."""
    return SUPPORTED_FRAMEWORKS


@router.get("/frameworks/{framework_id}", response_model=FrameworkResponse)
async def get_framework(
    framework_id: str,
    current_user: Annotated[Any, Depends(get_current_user)],
) -> FrameworkResponse:
    """Get a specific framework with all its controls."""
    framework_info = next((f for f in SUPPORTED_FRAMEWORKS if f["id"] == framework_id), None)
    if not framework_info:
        raise HTTPException(status_code=404, detail=f"Framework '{framework_id}' not found")

    from unimonitor.db.base import async_session_factory
    from unimonitor.grc.control_loader import ControlLibrary

    async with async_session_factory() as session:
        library = ControlLibrary(session)
        controls = await library.get_controls_for_framework(framework_id)

    return FrameworkResponse(
        id=framework_info["id"],
        name=framework_info["name"],
        version=framework_info["version"],
        description=f"{framework_info['name']} compliance framework controls",
        total_controls=len(controls),
        controls=[
            FrameworkControlSummary(
                id=c.id,
                external_id=c.external_id,
                name=c.name,
                category=c.category,
                severity=c.severity,
            )
            for c in controls
        ],
    )


@router.get("/{control_id}", response_model=ControlResponse)
async def get_control(
    control_id: str,
    current_user: Annotated[Any, Depends(get_current_user)],
) -> ControlResponse:
    """Get a specific control by ID."""
    from unimonitor.db.base import async_session_factory
    from unimonitor.grc.control_loader import ControlLibrary

    async with async_session_factory() as session:
        library = ControlLibrary(session)
        control = await library.get_control_by_id(control_id)
        if not control:
            raise HTTPException(status_code=404, detail="Control not found")

    return ControlResponse.model_validate(control)
