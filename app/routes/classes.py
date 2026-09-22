"""Contratos HTTP para turmas e matrículas."""

from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..config.database import get_db
from ..dependencies.authentication import get_current_user
from ..models.turma import Turma
from ..models.usuario import PerfilUsuario, Usuario
from ..schemas.turma import AlunoTurmaResponse, AtualizarTurmaRequest, CriarTurmaRequest, IngressarTurmaRequest, ResultadosTurmaResponse, TurmaResponse
from ..services.class_service import atualizar_turma, consultar_resultados_turma, criar_turma, ingressar_na_turma, listar_alunos_com_metricas, listar_turmas, remover_aluno_turma

router = APIRouter(prefix="/turmas", tags=["Turmas"])


def to_response(turma: Turma, usuario: Usuario) -> TurmaResponse:
    return TurmaResponse(
        uuid=turma.uuid,
        nome=turma.nome,
        ativa=turma.ativa,
        professor_uuid=turma.professor_uuid,
        codigo=turma.codigo,
        total_alunos=getattr(turma, "total_alunos", 0),
        total_atividades=getattr(turma, "total_atividades", 0),
        inicio_aulas=getattr(turma, "inicio_aulas", None),
    )


@router.post("", response_model=TurmaResponse, response_model_exclude_none=True, status_code=status.HTTP_201_CREATED)
async def create_class(dados: CriarTurmaRequest, professor: Usuario = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> TurmaResponse:
    return to_response(await criar_turma(dados, professor, db), professor)


@router.get("", response_model=list[TurmaResponse], response_model_exclude_none=True)
async def list_classes(usuario: Usuario = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> list[TurmaResponse]:
    return [to_response(turma, usuario) for turma in await listar_turmas(usuario, db)]


@router.patch("/{turma_id}", response_model=TurmaResponse, response_model_exclude_none=True)
async def update_class(turma_id: UUID, dados: AtualizarTurmaRequest, professor: Usuario = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> TurmaResponse:
    return to_response(await atualizar_turma(turma_id, dados, professor, db), professor)


@router.post("/ingressos", response_model=TurmaResponse, response_model_exclude_none=True, status_code=status.HTTP_201_CREATED)
async def enroll_in_class(dados: IngressarTurmaRequest, aluno: Usuario = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> TurmaResponse:
    return to_response(await ingressar_na_turma(dados, aluno, db), aluno)


@router.get("/{turma_id}/alunos", response_model=list[AlunoTurmaResponse])
async def list_class_students(turma_id: UUID, professor: Usuario = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> list[AlunoTurmaResponse]:
    alunos = await listar_alunos_com_metricas(turma_id, professor, db)
    return [AlunoTurmaResponse(**aluno) for aluno in alunos]


@router.get("/{turma_id}/resultados", response_model=ResultadosTurmaResponse)
async def get_class_results(turma_id: UUID, professor: Usuario = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> ResultadosTurmaResponse:
    return ResultadosTurmaResponse(**await consultar_resultados_turma(turma_id, professor, db))


@router.delete("/{turma_id}/alunos/{aluno_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_class_student(
    turma_id: UUID,
    aluno_id: UUID,
    professor: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await remover_aluno_turma(turma_id, aluno_id, professor, db)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
