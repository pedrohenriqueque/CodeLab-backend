from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, distinct
from sqlalchemy.orm import selectinload
from datetime import datetime, timezone, timedelta
from typing import Any

from app.api.dependencies import get_db, get_current_user
from app.db.models import Submissao, Atividade, Funcao, Usuario

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


@router.get("/aluno")
async def get_dashboard_aluno(
    session: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
) -> dict[str, Any]:
    """Retorna dados do painel do aluno autenticado."""
    aluno_uuid = current_user.uuid
    agora = datetime.now(timezone.utc)

    # ── Atividades publicadas com funções ──────────────────────────────────
    result_atividades = await session.execute(
        select(Atividade)
        .options(selectinload(Atividade.funcoes))
        .where(Atividade.status == "publicado")
        .order_by(Atividade.data_fechamento.asc().nulls_last())
    )
    atividades_publicadas = result_atividades.scalars().all()

    # ── Submissões do aluno (ordenadas por data desc) ──────────────────────
    result_subs = await session.execute(
        select(Submissao)
        .where(Submissao.aluno_uuid == aluno_uuid)
        .order_by(Submissao.data_submissao.desc())
    )
    submissoes = result_subs.scalars().all()

    # Progresso por função: melhor nota + contagem
    progresso_por_funcao: dict[str, dict] = {}
    for sub in submissoes:
        f_uuid = sub.funcao_uuid
        nota = float(sub.nota) if sub.nota is not None else 0.0
        if f_uuid not in progresso_por_funcao:
            progresso_por_funcao[f_uuid] = {"melhor_nota": nota, "tentativas": 1}
        else:
            progresso_por_funcao[f_uuid]["tentativas"] += 1
            if nota > progresso_por_funcao[f_uuid]["melhor_nota"]:
                progresso_por_funcao[f_uuid]["melhor_nota"] = nota

    total_tentativas = len(submissoes)
    melhor_nota_geral = (
        max((v["melhor_nota"] for v in progresso_por_funcao.values()), default=0.0)
    )

    # ── Montar lista de atividades em andamento ────────────────────────────
    atividades_em_andamento = []
    for atv in atividades_publicadas:
        # Verificar se ainda está dentro do prazo
        df = atv.data_fechamento
        if df:
            if df.tzinfo is None:
                df = df.replace(tzinfo=timezone.utc)
            if df < agora:
                continue  # já encerrada

        total_funcoes = len(atv.funcoes)
        total_pontos = sum(float(f.pontos or 0) for f in atv.funcoes)

        pontos_obtidos = 0.0
        funcoes_completas = 0
        for f in atv.funcoes:
            prog = progresso_por_funcao.get(f.uuid)
            if prog:
                pontos_obtidos += prog["melhor_nota"]
                if prog["melhor_nota"] >= float(f.pontos or 0):
                    funcoes_completas += 1

        dias_restantes = None
        data_fechamento_iso = None
        if atv.data_fechamento:
            df2 = atv.data_fechamento
            if df2.tzinfo is None:
                df2 = df2.replace(tzinfo=timezone.utc)
            data_fechamento_iso = df2.isoformat()
            dias_restantes = (df2 - agora).days

        data_abertura_iso = None
        if atv.data_abertura:
            da = atv.data_abertura
            if da.tzinfo is None:
                da = da.replace(tzinfo=timezone.utc)
            data_abertura_iso = da.isoformat()

        atividades_em_andamento.append({
            "uuid": atv.uuid,
            "titulo": atv.titulo,
            "descricao": atv.descricao,
            "total_funcoes": total_funcoes,
            "funcoes_completas": funcoes_completas,
            "pontos_obtidos": round(pontos_obtidos, 2),
            "total_pontos": round(total_pontos, 2),
            "data_abertura": data_abertura_iso,
            "data_fechamento": data_fechamento_iso,
            "dias_restantes": dias_restantes,
            "progresso_percent": round(
                (funcoes_completas / total_funcoes * 100) if total_funcoes > 0 else 0, 1
            ),
        })

    # Próximos prazos (top 3 com deadline futura)
    proximos_prazos = sorted(
        [a for a in atividades_em_andamento if a["dias_restantes"] is not None],
        key=lambda x: x["dias_restantes"],
    )[:3]

    # ── Últimas tentativas (5 submissões mais recentes com contexto) ───────
    ultimas_tentativas = []
    seen_subs = submissoes[:5]
    for sub in seen_subs:
        result_funcao = await session.execute(
            select(Funcao).where(Funcao.uuid == sub.funcao_uuid)
        )
        funcao = result_funcao.scalar_one_or_none()
        if funcao:
            result_atv = await session.execute(
                select(Atividade).where(Atividade.uuid == funcao.atividade_uuid)
            )
            atv_obj = result_atv.scalar_one_or_none()
            ultimas_tentativas.append({
                "uuid": sub.uuid,
                "funcao_nome": funcao.nome_funcao,
                "atividade_titulo": atv_obj.titulo if atv_obj else "—",
                "nota": float(sub.nota) if sub.nota is not None else None,
                "pontos_max": float(funcao.pontos) if funcao.pontos else 0.0,
                "status": sub.status,
                "data": sub.data_submissao.isoformat(),
            })

    return {
        "atividades_em_andamento": atividades_em_andamento[:3],
        "proximos_prazos": proximos_prazos,
        "ultimas_tentativas": ultimas_tentativas,
        "resumo": {
            "total_atividades": len(atividades_publicadas),
            "melhor_nota": round(melhor_nota_geral, 1),
            "total_tentativas": total_tentativas,
        },
    }


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

    # Buscar todas as atividades com funções e submissões
    result_atividades = await session.execute(
        select(Atividade)
        .options(selectinload(Atividade.funcoes))
        .order_by(Atividade.created_at.desc())
    )
    atividades = result_atividades.scalars().all()

    # Contagens de status
    atividades_ativas = sum(1 for a in atividades if a.status == "publicado")
    rascunhos = sum(1 for a in atividades if a.status == "rascunho")

    # Submissões desta semana (últimos 7 dias)
    agora = datetime.now(timezone.utc)
    inicio_semana = agora - timedelta(days=7)
    result_semana = await session.execute(
        select(func.count(Submissao.uuid)).where(
            Submissao.data_submissao >= inicio_semana
        )
    )
    submissoes_semana = result_semana.scalar() or 0

    # Média geral da turma (nota média de todas as submissões avaliadas)
    result_avg = await session.execute(
        select(func.avg(Submissao.nota)).where(Submissao.status == "avaliado")
    )
    media_notas = result_avg.scalar() or 0.0

    # Calcular pontuação máxima média para normalizar a nota (se aplicável)
    # Retornar diretamente a média bruta das notas avaliadas
    media_geral = round(float(media_notas), 1)

    # Atividades recentes (últimas 4) com detalhes
    atividades_recentes = []
    for atividade in atividades[:4]:
        funcoes_uuids = [f.uuid for f in atividade.funcoes]

        # Total de submissões para esta atividade
        if funcoes_uuids:
            result_subs = await session.execute(
                select(func.count(Submissao.uuid)).where(
                    Submissao.funcao_uuid.in_(funcoes_uuids)
                )
            )
            total_submissoes_atv = result_subs.scalar() or 0
        else:
            total_submissoes_atv = 0

        # Calcular dias até o fechamento
        dias_para_fechar = None
        data_ref = atividade.data_fechamento
        if data_ref:
            if data_ref.tzinfo is None:
                data_ref = data_ref.replace(tzinfo=timezone.utc)
            delta = data_ref - agora
            dias_para_fechar = delta.days

        atividades_recentes.append({
            "uuid": atividade.uuid,
            "titulo": atividade.titulo,
            "status": atividade.status,
            "data_fechamento": atividade.data_fechamento.isoformat() if atividade.data_fechamento else None,
            "dias_para_fechar": dias_para_fechar,
            "total_submissoes": total_submissoes_atv,
            "total_funcoes": len(funcoes_uuids),
        })

    # Desempenho semanal: média de notas agrupadas por semana (últimas 4 semanas)
    desempenho_semanal = []
    for i in range(3, -1, -1):
        inicio = agora - timedelta(weeks=i + 1)
        fim = agora - timedelta(weeks=i)
        result_sem = await session.execute(
            select(func.avg(Submissao.nota)).where(
                Submissao.status == "avaliado",
                Submissao.data_submissao >= inicio,
                Submissao.data_submissao < fim,
            )
        )
        media_sem = result_sem.scalar()
        desempenho_semanal.append({
            "semana": f"Sem {4 - i}",
            "media": round(float(media_sem), 1) if media_sem is not None else None,
        })

    return {
        "atividades_ativas": atividades_ativas,
        "rascunhos": rascunhos,
        "submissoes_semana": submissoes_semana,
        "media_geral_turma": media_geral,
        "atividades_recentes": atividades_recentes,
        "desempenho_semanal": desempenho_semanal,
        # Campos legados mantidos para compatibilidade
        "total_alunos_ativos": 0,
        "total_submissoes": 0,
        "taxa_aprovacao_media": media_geral,
        "atividades_engajamento": [],
    }
