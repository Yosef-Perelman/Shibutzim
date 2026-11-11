from typing import Annotated

from fastapi import APIRouter, Query

from app.deps import CurrentUser, SessionDep
from app.schemas.shift_template import ShiftTemplateCreate, ShiftTemplateOut, ShiftTemplateUpdate
from app.services import shift_template_service

router = APIRouter(prefix="/api/shift-templates", tags=["shift-templates"])


@router.get("")
def list_shift_templates(
    user: CurrentUser,
    session: SessionDep,
    active_only: Annotated[bool, Query(description="Hide deactivated templates")] = False,
) -> list[ShiftTemplateOut]:
    templates = shift_template_service.list_shift_templates(session, user, active_only=active_only)
    return [ShiftTemplateOut.model_validate(template) for template in templates]


@router.post("", status_code=201)
def create_shift_template(
    body: ShiftTemplateCreate, user: CurrentUser, session: SessionDep
) -> ShiftTemplateOut:
    template = shift_template_service.create_shift_template(session, user, **body.model_dump())
    return ShiftTemplateOut.model_validate(template)


@router.patch("/{template_id}")
def update_shift_template(
    template_id: int, body: ShiftTemplateUpdate, user: CurrentUser, session: SessionDep
) -> ShiftTemplateOut:
    changes = body.model_dump(exclude_unset=True)
    template = shift_template_service.update_shift_template(
        session, user, template_id, changes=changes
    )
    return ShiftTemplateOut.model_validate(template)
