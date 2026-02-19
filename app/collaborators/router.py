"""Collaborators API routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.collaborators.schemas import (
    CollaboratorCreate,
    CollaboratorInvitationCreate,
    CollaboratorInvitationResponse,
    CollaboratorResponse,
    TenantSearchResult,
)
from app.collaborators.service import CollaboratorService
from app.dependencies import CurrentAdmin, get_db

router = APIRouter()


def get_service(
    db: Annotated[Session, Depends(get_db)],
    current_user: CurrentAdmin,
) -> CollaboratorService:
    return CollaboratorService(db, str(current_user.tenant_id), str(current_user.id))


@router.get("", response_model=list[CollaboratorResponse])
async def list_collaborators(
    service: Annotated[CollaboratorService, Depends(get_service)],
):
    return service.list_collaborators()


@router.post("", response_model=CollaboratorResponse, status_code=status.HTTP_201_CREATED)
async def add_collaborator(
    data: CollaboratorCreate,
    service: Annotated[CollaboratorService, Depends(get_service)],
):
    try:
        return service.add_collaborator(data.collaborator_tenant_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{collaborator_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_collaborator(
    collaborator_id: str,
    service: Annotated[CollaboratorService, Depends(get_service)],
):
    if not service.remove_collaborator(collaborator_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collaborator not found")


@router.get("/search-tenants", response_model=list[TenantSearchResult])
async def search_tenants(
    service: Annotated[CollaboratorService, Depends(get_service)],
    q: str = Query("", min_length=1),
    limit: int = Query(10, ge=1, le=50),
):
    return service.search_tenants(q, limit)


# --- Invitation endpoints ---


@router.post(
    "/invitations",
    response_model=CollaboratorInvitationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_collaborator_invitation(
    data: CollaboratorInvitationCreate,
    request: Request,
    service: Annotated[CollaboratorService, Depends(get_service)],
):
    base_url = str(request.base_url).rstrip("/")
    try:
        return service.create_invitation(data.email, base_url)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/invitations", response_model=list[CollaboratorInvitationResponse])
async def list_collaborator_invitations(
    service: Annotated[CollaboratorService, Depends(get_service)],
):
    return service.list_invitations()


@router.post("/invitations/{invitation_id}/cancel", status_code=status.HTTP_200_OK)
async def cancel_collaborator_invitation(
    invitation_id: str,
    service: Annotated[CollaboratorService, Depends(get_service)],
):
    if not service.cancel_invitation(invitation_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found")
    return {"ok": True}


@router.post("/invitations/{invitation_id}/resend", status_code=status.HTTP_200_OK)
async def resend_collaborator_invitation(
    invitation_id: str,
    request: Request,
    service: Annotated[CollaboratorService, Depends(get_service)],
):
    base_url = str(request.base_url).rstrip("/")
    if not service.resend_invitation(invitation_id, base_url):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found")
    return {"ok": True}
