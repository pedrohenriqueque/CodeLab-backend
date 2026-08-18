from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, distinct
from sqlalchemy.orm import selectinload
from typing import Any

from app.api.dependencies import get_db, get_current_user
from app.db.models import Submissao, Atividade, Funcao, Usuario

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])

@router.get("/estatisticas")
async def get_estatisticas(
    session: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
) -> dict[str, Any]:
    """Retorna estatísticas gerais para o painel do professor."""
    if current_user.tipo != "professor":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso restrito a professores"
        )
    
    # Total de alunos cadastrados com submissões
    result_alunos = await session.execute(
        select(func.count(distinct(Submissao.aluno_uuid))).where(Submissao.aluno_uuid.isnot(None))
    )
    total_alunos = result_alunos.scalar() or 0

    # Total de submissões na plataforma
    result_submissoes = await session.execute(select(func.count(Submissao.uuid)))
    total_submissoes = result_submissoes.scalar() or 0

    # Taxa de aprovação média global (simples)
    # Consideramos "aprovado" se a nota for maior que 0 para simplificar, ou apenas a média das notas.
    # Vamos calcular a média da nota percentual (nota / pontos_maximos).
    # Aqui vamos usar uma aproximação: média das notas das submissões avaliadas.
    result_avg = await session.execute(
        select(func.avg(Submissao.nota)).where(Submissao.status == "avaliado")
    )
    media_notas = result_avg.scalar() or 0.0

    # Resumo e engajamento das atividades
    result_atividades = await session.execute(
        select(Atividade).options(selectinload(Atividade.funcoes))
    )
    atividades = result_atividades.scalars().all()
    
    atividades_resumo = []
    for atividade in atividades:
        funcoes_uuids = [f.uuid for f in atividade.funcoes]
        if funcoes_uuids:
            result_subs = await session.execute(
                select(func.count(Submissao.uuid)).where(Submissao.funcao_uuid.in_(funcoes_uuids))
            )
            subs_count = result_subs.scalar() or 0
        else:
            subs_count = 0
            
        atividades_resumo.append({
            "atividade_uuid": atividade.uuid,
            "titulo": atividade.titulo,
            "total_submissoes": subs_count,
            "total_funcoes": len(funcoes_uuids)
        })

    # Sort atividades by engajamento (total_submissoes) desc
    atividades_resumo.sort(key=lambda x: x["total_submissoes"], reverse=True)

    return {
        "total_alunos_ativos": total_alunos,
        "total_submissoes": total_submissoes,
        "taxa_aprovacao_media": float(media_notas),
        "atividades_engajamento": atividades_resumo
    }
