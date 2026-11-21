"""Control library endpoints."""

from __future__ import annotations

from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from unimonitor.auth.dependencies import get_current_user
from unimonitor.grc.frameworks import get_framework as get_framework_meta
from unimonitor.grc.frameworks import list_frameworks as registry_frameworks

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

# Single source of truth: the FRAMEWORKS registry carries each framework's
# slug, display name and version, so this list can never drift from it.
SUPPORTED_FRAMEWORKS = [
    {"id": meta.slug, "name": meta.name, "version": meta.version, "mapping_note": meta.mapping_note} for meta in registry_frameworks()
]


def _control_response(control: Any) -> ControlResponse:
    """Serialise a YAML control, expanding every framework reference."""
    from unimonitor.grc.frameworks import framework_id_for_key

    mappings: list[ComplianceMapping] = []
    for framework_key, references in control.compliance_mapping.items():
        framework = framework_id_for_key(framework_key) or framework_key.replace("_", "-")
        refs = references if isinstance(references, (list, tuple)) else [references]
        mappings.extend(ComplianceMapping(framework=framework, control_id=control.id, control_name=str(reference)) for reference in refs)
    return ControlResponse(
        id=control.id,
        external_id=control.id,
        name=control.title,
        description=control.description,
        category=control.category,
        service=control.service,
        severity=control.severity.lower(),
        is_active=True,
        framework_mappings=mappings,
        remediation_steps=list(control.remediation_steps),
        references=[],
        tags=[],
    )


# ── Endpoints ────────────────────────────────────────────────


@router.get("")
async def list_controls(
    current_user: Annotated[Any, Depends(get_current_user)],
    category: Annotated[str | None, Query()] = None,
    service: Annotated[str | None, Query()] = None,
    severity: Annotated[str | None, Query()] = None,
    framework: Annotated[str | None, Query()] = None,
    search: Annotated[str | None, Query()] = None,
    is_active: Annotated[bool | None, Query()] = True,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
) -> PaginatedControls:
    """List all controls with filtering and pagination."""
    from unimonitor.grc.control_loader import ControlLoader, controls_for_framework

    controls = sorted(ControlLoader().load_all(), key=lambda item: item.id)
    if category:
        controls = [item for item in controls if item.category == category]
    if service:
        controls = [item for item in controls if item.service == service]
    if severity:
        controls = [item for item in controls if item.severity.lower() == severity.lower()]
    if framework:
        controls = sorted(controls_for_framework(framework), key=lambda item: item.id)
    if search:
        needle = search.lower()
        controls = [item for item in controls if needle in item.id.lower() or needle in item.title.lower() or needle in item.description.lower()]

    total = len(controls)
    start = (page - 1) * page_size
    window = controls[start : start + page_size]
    pages = max(1, (total + page_size - 1) // page_size)
    return PaginatedControls(
        items=[_control_response(item) for item in window],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get("/frameworks")
async def list_frameworks(
    current_user: Annotated[Any, Depends(get_current_user)],
) -> list[dict]:
    """List all supported compliance frameworks."""
    return SUPPORTED_FRAMEWORKS


@router.get("/frameworks/{framework_id}", responses={404: {"description": "Not found"}})
async def get_framework(
    framework_id: str,
    current_user: Annotated[Any, Depends(get_current_user)],
) -> FrameworkResponse:
    """Get a specific framework with all its controls."""
    framework_info = get_framework_meta(framework_id)
    if not framework_info:
        raise HTTPException(status_code=404, detail=f"Framework '{framework_id}' not found")

    from unimonitor.grc.control_loader import controls_for_framework

    controls = sorted(controls_for_framework(framework_info.slug), key=lambda item: item.id)

    return FrameworkResponse(
        id=framework_info.slug,
        name=framework_info.name,
        version=framework_info.version,
        description=framework_info.description,
        total_controls=len(controls),
        controls=[
            FrameworkControlSummary(
                id=control.id,
                external_id=control.id,
                name=control.title,
                category=control.category,
                severity=control.severity.lower(),
            )
            for control in controls
        ],
    )


@router.get("/{control_id}", responses={404: {"description": "Not found"}})
async def get_control(
    control_id: str,
    current_user: Annotated[Any, Depends(get_current_user)],
) -> ControlResponse:
    """Get a specific control by ID."""
    from unimonitor.grc.control_loader import ControlLoader

    control = next((item for item in ControlLoader().load_all() if item.id.lower() == control_id.lower()), None)
    if control is None:
        raise HTTPException(status_code=404, detail="Control not found")

    return _control_response(control)
