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
    is_prova = atividade.tipo == "PROVA"
    abertas = is_prova and not is_encerrada
    def get_recebida_em(item):
        dt = getattr(item, "recebida_em", None)
        if dt is None:
            return datetime.min.replace(tzinfo=timezone.utc)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt

    progresso = []
    for funcao in funcoes:
        itens = [item for item in tentativas if item.funcao_atividade_uuid == funcao.uuid]
        itens.sort(key=get_recebida_em, reverse=True)

        if is_prova:
            # Em prova, erros de compilação e falhas técnicas não contam como submissão
            itens_contabilizados = [
                item for item in itens if item.status not in {"FALHA_TECNICA", "ERRO_COMPILACAO"}
            ]
        else:
            itens_contabilizados = [
                item for item in itens if item.status != "FALHA_TECNICA"
            ]

        ultima_tentativa_uuid = itens_contabilizados[0].uuid if itens_contabilizados else None

        itens_com_nota = [item for item in itens_contabilizados if item.nota is not None]
        melhor_item = max(itens_com_nota, key=lambda x: Decimal(x.nota), default=None) if itens_com_nota else None
        melhor_tentativa_uuid = melhor_item.uuid if melhor_item else ultima_tentativa_uuid

        notas = [Decimal(item.nota) for item in itens_contabilizados if item.nota is not None]
        melhor = max(notas, default=None)
        progresso.append({
            "funcao_atividade_uuid": funcao.uuid,
            "enviada": bool(itens_contabilizados),
            "avaliada": any(item.status == "AVALIADA" for item in itens_contabilizados),
            "aprovada": None if abertas else (melhor is not None and melhor >= Decimal(funcao.nota_maxima)),
            "melhor_nota": None if abertas else melhor,
            "total_tentativas": len(itens_contabilizados),
            "melhor_tentativa_uuid": melhor_tentativa_uuid,
            "ultima_tentativa_uuid": ultima_tentativa_uuid,
        })
    return progresso
