from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..config.database import get_db
from ..dependencies.authentication import get_current_user
from ..models.funcao import FuncaoBiblioteca
from ..models.usuario import Usuario
from ..schemas.funcao import AtualizarFuncaoRequest, CriarFuncaoRequest, FuncaoResponse, ParametroFuncao
from ..services.function_service import atualizar_funcao, criar_funcao, duplicar_funcao, listar_funcoes, obter_funcao, remover_funcao

router = APIRouter(prefix="/funcoes", tags=["Biblioteca de funções"])


def to_response(funcao: FuncaoBiblioteca, professor_nome: str | None = None, total_casos_teste: int = 0) -> FuncaoResponse:
    return FuncaoResponse(
        uuid=funcao.uuid, nome=funcao.nome, enunciado=funcao.enunciado,
        tipo_retorno=funcao.tipo_retorno,
        parametros=[ParametroFuncao(**parametro) for parametro in funcao.parametros],
        dificuldade=funcao.dificuldade, compartilhada=funcao.compartilhada,
        professor_uuid=funcao.professor_uuid,
        professor_nome=professor_nome or funcao.professor.nome,
        total_casos_teste=total_casos_teste,
    )


@router.post("", response_model=FuncaoResponse, status_code=status.HTTP_201_CREATED)
async def create_function(dados: CriarFuncaoRequest, professor: Usuario = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> FuncaoResponse:
    return to_response(await criar_funcao(dados, professor, db), professor.nome)


@router.get("", response_model=list[FuncaoResponse])
async def list_functions(professor: Usuario = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> list[FuncaoResponse]:
    return [to_response(funcao, total_casos_teste=total) for funcao, total in await listar_funcoes(professor, db)]


@router.get("/{function_id}", response_model=FuncaoResponse)
async def get_function(function_id: UUID, professor: Usuario = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> FuncaoResponse:
    return to_response(await obter_funcao(function_id, professor, db))


@router.patch("/{function_id}", response_model=FuncaoResponse)
async def update_function(function_id: UUID, dados: AtualizarFuncaoRequest, professor: Usuario = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> FuncaoResponse:
    return to_response(await atualizar_funcao(function_id, dados, professor, db))


@router.delete("/{function_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_function(function_id: UUID, professor: Usuario = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> Response:
    await remover_funcao(function_id, professor, db)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{function_id}/duplicar", response_model=FuncaoResponse, status_code=status.HTTP_201_CREATED)
async def duplicate_function(function_id: UUID, professor: Usuario = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> FuncaoResponse:
    return to_response(await duplicar_funcao(function_id, professor, db), professor.nome)
