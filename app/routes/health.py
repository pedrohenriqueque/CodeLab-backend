"""Liveness HTTP (sem acesso ao banco nem Judge0)."""

from fastapi import APIRouter

from ..schemas.base import ApiSchema

router = APIRouter(tags=["infraestrutura"])


class HealthResponse(ApiSchema):
    status: str


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok")
