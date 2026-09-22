from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..config.database import get_db
from ..dependencies.authentication import get_current_user
from ..models.caso_teste import CasoTeste
from ..models.usuario import Usuario
from ..schemas.caso_teste import AtualizarCasoTesteRequest, CasoTesteResponse, CriarCasoTesteRequest
from ..services.test_case_service import atualizar_caso, criar_caso, listar_casos, remover_caso

router = APIRouter(tags=["Casos de teste"])

def to_response(caso: CasoTeste) -> CasoTesteResponse:
    return CasoTesteResponse(uuid=caso.uuid, entradas=caso.entradas, retorno_esperado=caso.retorno_esperado, visibilidade=caso.visibilidade, descricao=caso.descricao)

@router.post("/funcoes/{function_id}/casos", response_model=CasoTesteResponse, status_code=status.HTTP_201_CREATED)
async def create_test_case(function_id: UUID, dados: CriarCasoTesteRequest, professor: Usuario = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> CasoTesteResponse:
    return to_response(await criar_caso(function_id, dados, professor, db))

@router.get("/funcoes/{function_id}/casos", response_model=list[CasoTesteResponse])
async def list_test_cases(function_id: UUID, professor: Usuario = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> list[CasoTesteResponse]:
    return [to_response(item) for item in await listar_casos(function_id, professor, db)]

@router.patch("/casos/{case_id}", response_model=CasoTesteResponse)
async def update_test_case(case_id: UUID, dados: AtualizarCasoTesteRequest, professor: Usuario = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> CasoTesteResponse:
    return to_response(await atualizar_caso(case_id, dados, professor, db))

@router.delete("/casos/{case_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_test_case(case_id: UUID, professor: Usuario = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> Response:
    await remover_caso(case_id, professor, db)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
