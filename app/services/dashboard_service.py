"""Projeções do início por turma, sem código-fonte ou dados de casos."""
from collections import defaultdict
from datetime import datetime, timezone

from sqlalchemy import select

from ..core.exceptions import CodelabException, NotFoundError
from ..models.funcao_atividade import FuncaoAtividade
from ..models.tentativa import Tentativa
from ..models.usuario import PerfilUsuario
from ..repositories.class_repository import ClassRepository
from ..repositories.activity_repository import ActivityRepository
from ..repositories.enrollment_repository import EnrollmentRepository
from .submission_service import resultado_liberado


def projetar_dashboard(turma, atividades, funcoes, tentativas, alunos, usuario, agora):
    professor = usuario.perfil == PerfilUsuario.PROFESSOR
    atividades = [a for a in atividades if professor or a.status != 'RASCUNHO']
    por_atividade = {a.uuid: a for a in atividades}
    por_funcao = {f.uuid: f for f in funcoes if f.atividade_uuid in por_atividade}
    nomes = {a.uuid: a.nome for a in alunos}
    tentativas = [t for t in tentativas if t.funcao_atividade_uuid in por_funcao
                  and (t.aluno_uuid in nomes if professor else t.aluno_uuid == usuario.uuid)]
    envios = defaultdict(set)
    for tentativa in tentativas:
        atividade_id = por_funcao[tentativa.funcao_atividade_uuid].atividade_uuid
        envios[(atividade_id, tentativa.aluno_uuid)].add(tentativa.funcao_atividade_uuid)
    itens = []
    for atividade in atividades:
        total = sum(f.atividade_uuid == atividade.uuid for f in por_funcao.values())
        situacao = ('RASCUNHO' if atividade.status == 'RASCUNHO' else
                    'ENCERRADA' if atividade.status == 'ENCERRADA' or agora >= atividade.fim_em else
                    'AGENDADA' if agora < atividade.inicio_em else 'ABERTA')
        conjuntos = [ids for (aid, _), ids in envios.items() if aid == atividade.uuid]
        itens.append(dict(uuid=atividade.uuid, titulo=atividade.titulo, tipo=atividade.tipo,
                          situacao=situacao, fim_em=atividade.fim_em, total_funcoes=total,
                          funcoes_enviadas=len(envios.get((atividade.uuid, usuario.uuid), set())),
                          alunos_iniciaram=len(conjuntos) if professor else 0,
                          alunos_enviaram_todas=sum(len(ids) == total for ids in conjuntos) if professor and total else 0))
    itens.sort(key=lambda a: (a['situacao'] != 'ABERTA', a['fim_em'], str(a['uuid'])))
    recentes = []
    for tentativa in sorted(tentativas, key=lambda t: (t.recebida_em, str(t.uuid)), reverse=True)[:5]:
        funcao = por_funcao[tentativa.funcao_atividade_uuid]
        atividade = por_atividade[funcao.atividade_uuid]
        liberar = professor or resultado_liberado(atividade, agora)
        recentes.append(dict(uuid=tentativa.uuid, atividade_uuid=atividade.uuid,
                             atividade_titulo=atividade.titulo, funcao_uuid=funcao.uuid,
                             funcao_nome=funcao.nome, aluno_nome=nomes.get(tentativa.aluno_uuid) if professor else None,
                             recebida_em=tentativa.recebida_em,
                             status=tentativa.status if liberar else 'ENVIO_REGISTRADO',
                             nota=tentativa.nota if liberar and tentativa.status in {'AVALIADA', 'ERRO_COMPILACAO'} else None,
                             nota_maxima=funcao.nota_maxima if liberar else None))
    return dict(turma_uuid=turma.uuid, turma_nome=turma.nome,
                codigo=turma.codigo if professor else None, total_alunos=len(alunos) if professor else None,
                atividades_abertas=sum(a['situacao'] == 'ABERTA' for a in itens),
                atividades_iniciadas=len({aid for aid, _ in envios}),
                funcoes_enviadas=sum(len(ids) for ids in envios.values()), atividades=itens, recentes=recentes)


async def consultar_dashboard(turma_id, usuario, perfil, db):
    if usuario.perfil != perfil:
        raise CodelabException('Operação não permitida para este perfil.', 403)
    turma = await ClassRepository(db).get_by_uuid(turma_id)
    if turma is None:
        raise NotFoundError('Turma')
    matriculas = EnrollmentRepository(db)
    autorizado = (turma.professor_uuid == usuario.uuid if perfil == PerfilUsuario.PROFESSOR
                  else await matriculas.exists(turma_id, usuario.uuid))
    if not autorizado:
        raise CodelabException('Você não tem acesso a esta turma.', 403)
    atividades = await ActivityRepository(db).list_by_class_ids([turma_id])
    if perfil == PerfilUsuario.ALUNO:
        atividades = [a for a in atividades if a.status != 'RASCUNHO']
    ids = [a.uuid for a in atividades]
    funcoes = list(await db.scalars(select(FuncaoAtividade).where(FuncaoAtividade.atividade_uuid.in_(ids)))) if ids else []
    # Carregar apenas colunas necessárias; nunca o código-fonte das tentativas.
    consulta = select(Tentativa.uuid, Tentativa.funcao_atividade_uuid, Tentativa.aluno_uuid,
                      Tentativa.recebida_em, Tentativa.status, Tentativa.nota).where(
                          Tentativa.funcao_atividade_uuid.in_([f.uuid for f in funcoes]))
    if perfil == PerfilUsuario.ALUNO:
        consulta = consulta.where(Tentativa.aluno_uuid == usuario.uuid)
    tentativas = (await db.execute(consulta)).all() if funcoes else []
    alunos = await matriculas.list_students(turma_id) if perfil == PerfilUsuario.PROFESSOR else []
    return projetar_dashboard(turma, atividades, funcoes, tentativas, alunos, usuario, datetime.now(timezone.utc))
