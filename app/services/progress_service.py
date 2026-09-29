from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from ..core.exceptions import CodelabException
from ..models.usuario import PerfilUsuario, Usuario
from ..repositories.activity_function_repository import ActivityFunctionRepository
from ..repositories.submission_repository import SubmissionRepository
from .activity_service import obter_atividade


async def consultar_progresso(activity_id: UUID, aluno: Usuario, db: AsyncSession) -> list[dict]:
    if aluno.perfil != PerfilUsuario.ALUNO:
        raise CodelabException("Operação não permitida para este perfil.", 403)
    atividade = await obter_atividade(activity_id, aluno, db)
    funcoes = await ActivityFunctionRepository(db).list_functions(atividade.uuid)
    tentativas = await SubmissionRepository(db).list_by_student(aluno.uuid)
    from datetime import datetime, timezone
    agora = datetime.now(timezone.utc)
    fim_em_utc = (
        atividade.fim_em
        if (atividade.fim_em and atividade.fim_em.tzinfo)
        else (atividade.fim_em.replace(tzinfo=timezone.utc) if atividade.fim_em else None)
    )
    is_encerrada = atividade.status == "ENCERRADA" or (fim_em_utc is not None and agora >= fim_em_utc)
    abertas = atividade.tipo == "PROVA" and not is_encerrada
    progresso = []
    for funcao in funcoes:
        itens = [item for item in tentativas if item.funcao_atividade_uuid == funcao.uuid]
        notas = [Decimal(item.nota) for item in itens if item.nota is not None]
        melhor = max(notas, default=None)
        progresso.append({
            "funcao_atividade_uuid": funcao.uuid,
            "enviada": bool(itens),
            "avaliada": any(item.status in {"AVALIADA", "ERRO_COMPILACAO"} for item in itens),
            "aprovada": None if abertas else (melhor is not None and melhor >= Decimal(funcao.nota_maxima)),
            "melhor_nota": None if abertas else melhor,
            "total_tentativas": len(itens),
        })
    return progresso
