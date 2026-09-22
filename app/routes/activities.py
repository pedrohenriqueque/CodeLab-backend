from collections import defaultdict
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..config.database import get_db
from ..dependencies.authentication import get_current_user
from ..models.atividade import Atividade
from ..models.usuario import Usuario
from ..schemas.atividade import AtividadeResponse, AtualizarAtividadeRequest, CriarAtividadeRequest
from ..schemas.funcao import ParametroFuncao
from ..schemas.funcao_atividade import (
    AssociarFuncaoAtividadeRequest,
    CasoTesteAtividadeResponse,
    FuncaoAtividadeResponse,
    ReordenarFuncoesAtividadeRequest,
)
from ..services.activity_service import (
    associar_funcao,
    atualizar_atividade,
    criar_atividade,
    listar_atividades,
    listar_funcoes_internas,
    obter_atividade,
    publicar_atividade,
    remover_funcao_interna,
    reordenar_funcoes_internas,
    encerrar_atividade,
)

router = APIRouter(prefix="/atividades", tags=["Atividades"])


def out(atividade: Atividade) -> AtividadeResponse:
    return AtividadeResponse(
        uuid=atividade.uuid,
        turma_uuid=atividade.turma_uuid,
        titulo=atividade.titulo,
        descricao=atividade.descricao,
        inicio_em=atividade.inicio_em,
        fim_em=atividade.fim_em,
        status=atividade.status,
        tipo=atividade.tipo,
        permitir_multiplas_submissoes=atividade.permitir_multiplas_submissoes,
        max_tentativas_por_funcao=atividade.max_tentativas_por_funcao,
        mostrar_ocultos_apos_fechamento=atividade.mostrar_ocultos_apos_fechamento,
    )


def function_out(funcao, casos) -> FuncaoAtividadeResponse:
    return FuncaoAtividadeResponse(
        uuid=funcao.uuid,
        nome=funcao.nome,
        enunciado=funcao.enunciado,
        tipo_retorno=funcao.tipo_retorno,
        parametros=[ParametroFuncao(**parametro) for parametro in funcao.parametros],
        dificuldade=funcao.dificuldade,
        nota_maxima=funcao.nota_maxima,
        ordem=funcao.ordem,
        casos_teste=[
            CasoTesteAtividadeResponse(
                uuid=caso.uuid,
                entradas=caso.entradas,
                retorno_esperado=caso.retorno_esperado,
                visibilidade=caso.visibilidade,
                descricao=caso.descricao,
            )
            for caso in casos
        ],
    )


@router.get("", response_model=list[AtividadeResponse])
async def list_activities(
    professor: Usuario = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[AtividadeResponse]:
    return [out(item) for item in await listar_atividades(professor, db)]


@router.post("", response_model=AtividadeResponse, status_code=status.HTTP_201_CREATED)
async def create_activity(
    dados: CriarAtividadeRequest,
    professor: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AtividadeResponse:
    return out(await criar_atividade(dados, professor, db))


@router.get("/{activity_id}", response_model=AtividadeResponse)
async def get_activity(
    activity_id: UUID,
    professor: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AtividadeResponse:
    return out(await obter_atividade(activity_id, professor, db))


@router.patch("/{activity_id}", response_model=AtividadeResponse)
async def update_activity(
    activity_id: UUID,
    dados: AtualizarAtividadeRequest,
    professor: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AtividadeResponse:
    return out(await atualizar_atividade(activity_id, dados, professor, db))


@router.post("/{activity_id}/publicar", response_model=AtividadeResponse)
async def publish_activity(
    activity_id: UUID,
    professor: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AtividadeResponse:
    return out(await publicar_atividade(activity_id, professor, db))


@router.post("/{activity_id}/encerrar", response_model=AtividadeResponse)
async def close_activity(
    activity_id: UUID,
    professor: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AtividadeResponse:
    return out(await encerrar_atividade(activity_id, professor, db))


@router.post("/{activity_id}/funcoes", response_model=FuncaoAtividadeResponse, status_code=status.HTTP_201_CREATED)
async def associate_function(
    activity_id: UUID,
    dados: AssociarFuncaoAtividadeRequest,
    professor: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FuncaoAtividadeResponse:
    funcao, casos = await associar_funcao(activity_id, dados, professor, db)
    return function_out(funcao, casos)


@router.get("/{activity_id}/funcoes", response_model=list[FuncaoAtividadeResponse])
async def list_activity_functions(
    activity_id: UUID,
    professor: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[FuncaoAtividadeResponse]:
    funcoes, casos = await listar_funcoes_internas(activity_id, professor, db)
    casos_por_funcao = defaultdict(list)
    for caso in casos:
        casos_por_funcao[caso.funcao_atividade_uuid].append(caso)
    # Casos e valores esperados são exclusivos do processo de avaliação.
    mostrar_casos = professor.perfil != "ALUNO"
    return [
        function_out(funcao, casos_por_funcao[funcao.uuid] if mostrar_casos else [])
        for funcao in funcoes
    ]


@router.put("/{activity_id}/funcoes/ordem", response_model=list[FuncaoAtividadeResponse])
async def reorder_activity_functions(
    activity_id: UUID,
    dados: ReordenarFuncoesAtividadeRequest,
    professor: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[FuncaoAtividadeResponse]:
    await reordenar_funcoes_internas(activity_id, dados, professor, db)
    funcoes, casos = await listar_funcoes_internas(activity_id, professor, db)
    casos_por_funcao = defaultdict(list)
    for caso in casos:
        casos_por_funcao[caso.funcao_atividade_uuid].append(caso)
    return [function_out(funcao, casos_por_funcao[funcao.uuid]) for funcao in funcoes]


@router.delete("/{activity_id}/funcoes/{activity_function_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_activity_function(
    activity_id: UUID,
    activity_function_id: UUID,
    professor: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await remover_funcao_interna(activity_id, activity_function_id, professor, db)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
