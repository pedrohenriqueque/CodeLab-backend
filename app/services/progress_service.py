from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from ..core.exceptions import CodelabException
from ..models.usuario import PerfilUsuario, Usuario
from ..repositories.activity_function_repository import ActivityFunctionRepository
from ..repositories.submission_repository import SubmissionRepository
from .activity_service import obter_atividade
from .submission_service import resultado_liberado


def calcular_progresso_funcao(funcao, tentativas: list, atividade) -> dict:
    """Regra compartilhada pelo detalhe e resumo de atividades, sem consultas."""
    ignorados = {"FALHA_TECNICA", "ERRO_COMPILACAO"} if atividade.tipo == "PROVA" else {"FALHA_TECNICA"}

    def recebida_em(item):
        data = getattr(item, "recebida_em", None) or datetime.min.replace(tzinfo=timezone.utc)
        return data if data.tzinfo else data.replace(tzinfo=timezone.utc)

    itens = sorted((t for t in tentativas if t.status not in ignorados),
                   key=lambda t: (recebida_em(t), str(t.uuid)), reverse=True)
    ultima = itens[0].uuid if itens else None
    melhor_item = max((t for t in itens if t.nota is not None), key=lambda t: Decimal(t.nota), default=None)
    melhor = Decimal(melhor_item.nota) if melhor_item is not None else None
    liberar = resultado_liberado(atividade)
    return {
        "funcao_atividade_uuid": funcao.uuid,
        "enviada": bool(itens),
        "avaliada": any(t.status == "AVALIADA" for t in itens),
        "aprovada": (melhor is not None and melhor >= Decimal(funcao.nota_maxima)) if liberar else None,
        "melhor_nota": melhor if liberar else None,
        "total_tentativas": len(itens),
        "melhor_tentativa_uuid": melhor_item.uuid if liberar and melhor_item is not None else ultima,
        "ultima_tentativa_uuid": ultima,
    }


async def consultar_progresso(activity_id: UUID, aluno: Usuario, db: AsyncSession) -> list[dict]:
    if aluno.perfil != PerfilUsuario.ALUNO:
        raise CodelabException("Operação não permitida para este perfil.", 403)
    atividade = await obter_atividade(activity_id, aluno, db)
    funcoes = await ActivityFunctionRepository(db).list_functions(atividade.uuid)
    tentativas = await SubmissionRepository(db).list_for_student_functions(aluno.uuid, [f.uuid for f in funcoes])
    por_funcao = defaultdict(list)
    for tentativa in tentativas:
        por_funcao[tentativa.funcao_atividade_uuid].append(tentativa)
    return [calcular_progresso_funcao(f, por_funcao[f.uuid], atividade) for f in funcoes]
