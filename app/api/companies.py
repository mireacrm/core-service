import uuid

from fastapi import APIRouter, Depends, status
from mireacrm_common.deps import get_publisher, get_session
from mireacrm_common.events import EventPublisher
from sqlalchemy.ext.asyncio import AsyncSession

from app import commands, domain
from app.api import schemas

router = APIRouter(tags=["organization"])


@router.post("/companies", response_model=schemas.CompanyOut, status_code=status.HTTP_201_CREATED)
async def create_company(
    payload: commands.CompanyCreate, session: AsyncSession = Depends(get_session)
):
    return await domain.create_company(session, payload)


@router.post(
    "/companies/{company_id}/branches",
    response_model=schemas.BranchOut,
    status_code=status.HTTP_201_CREATED,
)
async def open_branch(
    company_id: uuid.UUID,
    payload: commands.BranchCreate,
    session: AsyncSession = Depends(get_session),
    publisher: EventPublisher = Depends(get_publisher),
):
    return await domain.open_branch(session, company_id, payload, publisher)
