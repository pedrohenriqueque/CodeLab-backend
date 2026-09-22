"""Cria dados idempotentes para demonstrar os fluxos locais do CodeLab."""

import argparse
import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import or_, select

from .app.config.database import make_engine, make_session_factory
from .app.config.settings import get_settings
from .app.core.security import get_password_hash
from .app.models.atividade import Atividade
from .app.models.caso_teste import CasoTeste
from .app.models.funcao import FuncaoBiblioteca
from .app.models.funcao_atividade import CasoTesteAtividade, FuncaoAtividade
from .app.models.turma import MatriculaTurma, Turma
from .app.models.tentativa import ResultadoCasoTentativa, Tentativa
from .app.models.usuario import PerfilUsuario, Usuario

PASSWORD = "123456"
USERS = (
    ("Administrador CodeLab", "admin@codelab.local", "ADMIN001", PerfilUsuario.ADMIN),
    ("Ana Souza", "ana.souza@universidade.br", "PROF001", PerfilUsuario.PROFESSOR),
    ("Bruno Lima", "bruno.lima@universidade.br", "PROF002", PerfilUsuario.PROFESSOR),
    ("Pedro Lacerda", "pedro.lacerda@aluno.universidade.br", "ALU001", PerfilUsuario.ALUNO),
    ("Marina Alves", "marina.alves@aluno.universidade.br", "ALU002", PerfilUsuario.ALUNO),
    ("Carla Mendes", "carla.mendes@universidade.br", "PROF003", PerfilUsuario.PROFESSOR),
    ("Lucas Rocha", "lucas.rocha@aluno.universidade.br", "ALU003", PerfilUsuario.ALUNO),
    ("Julia Campos", "julia.campos@aluno.universidade.br", "ALU004", PerfilUsuario.ALUNO),
    ("Rafael Nunes", "rafael.nunes@aluno.universidade.br", "ALU005", PerfilUsuario.ALUNO),
    ("Beatriz Lima", "beatriz.lima@aluno.universidade.br", "ALU006", PerfilUsuario.ALUNO),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Insere dados de demonstração no banco de desenvolvimento.")
    parser.add_argument("--environment", default="development", choices=("development",))
    parser.add_argument("--confirm", required=True)
    return parser.parse_args()


async def get_or_create_user(session, nome: str, email: str, matricula: str, perfil: PerfilUsuario) -> Usuario:
    user = await session.scalar(select(Usuario).where(or_(Usuario.email == email, Usuario.matricula == matricula)))
    if user is None:
        user = Usuario(nome=nome, email=email, matricula=matricula, perfil=perfil, senha_hash=get_password_hash(PASSWORD))
        session.add(user)
        await session.flush()
    return user


async def get_or_create_class(session, professor: Usuario, nome: str, codigo: str) -> Turma:
    turma = await session.scalar(select(Turma).where(Turma.codigo == codigo))
    if turma is None:
        turma = Turma(nome=nome, codigo=codigo, ativa=True, professor_uuid=professor.uuid)
        session.add(turma)
        await session.flush()
    return turma


async def ensure_enrollment(session, turma: Turma, aluno: Usuario) -> None:
    enrollment = await session.scalar(
        select(MatriculaTurma).where(MatriculaTurma.turma_uuid == turma.uuid, MatriculaTurma.aluno_uuid == aluno.uuid)
    )
    if enrollment is None:
        session.add(MatriculaTurma(turma_uuid=turma.uuid, aluno_uuid=aluno.uuid))


async def get_or_create_function(session, professor: Usuario, nome: str, enunciado: str, retorno: str, parametros: list[dict], dificuldade: str, casos: list[tuple[list[object], object, str]]) -> FuncaoBiblioteca:
    funcao = await session.scalar(select(FuncaoBiblioteca).where(FuncaoBiblioteca.professor_uuid == professor.uuid, FuncaoBiblioteca.nome == nome))
    if funcao is None:
        funcao = FuncaoBiblioteca(professor_uuid=professor.uuid, nome=nome, enunciado=enunciado, tipo_retorno=retorno, parametros=parametros, dificuldade=dificuldade, compartilhada=True)
        session.add(funcao)
        await session.flush()
    existing = await session.scalars(select(CasoTeste).where(CasoTeste.funcao_uuid == funcao.uuid))
    if not list(existing):
        for entradas, retorno_esperado, descricao in casos:
            session.add(CasoTeste(funcao_uuid=funcao.uuid, entradas=entradas, retorno_esperado=retorno_esperado, visibilidade="VISIVEL", descricao=descricao))
    return funcao


async def create_demo_activity(session, turma: Turma, titulo: str, descricao: str, funcoes: list[FuncaoBiblioteca], status: str, tipo: str = "EXERCICIO") -> Atividade:
    atividade = await session.scalar(select(Atividade).where(Atividade.turma_uuid == turma.uuid, Atividade.titulo == titulo))
    if atividade is not None:
        atividade.tipo = tipo
        return atividade
    now = datetime.now(timezone.utc)
    atividade = Atividade(turma_uuid=turma.uuid, titulo=titulo, descricao=descricao, inicio_em=now - timedelta(days=1), fim_em=now + timedelta(days=14), status=status, tipo=tipo)
    session.add(atividade)
    await session.flush()
    for ordem, origem in enumerate(funcoes, start=1):
        interna = FuncaoAtividade(atividade_uuid=atividade.uuid, nome=origem.nome, enunciado=origem.enunciado, tipo_retorno=origem.tipo_retorno, parametros=origem.parametros, dificuldade=origem.dificuldade, nota_maxima=Decimal("10") / len(funcoes), ordem=ordem)
        session.add(interna)
        await session.flush()
        casos = await session.scalars(select(CasoTeste).where(CasoTeste.funcao_uuid == origem.uuid))
        for caso in casos:
            session.add(CasoTesteAtividade(funcao_atividade_uuid=interna.uuid, entradas=caso.entradas, retorno_esperado=caso.retorno_esperado, visibilidade=caso.visibilidade, descricao=caso.descricao))
    return atividade


async def ensure_demo_attempts(session, atividade: Atividade, aluno: Usuario) -> None:
    """Cria tentativas prontas para demonstrar histórico, melhor nota e progresso."""
    funcoes = list(await session.scalars(select(FuncaoAtividade).where(FuncaoAtividade.atividade_uuid == atividade.uuid).order_by(FuncaoAtividade.ordem)))
    if not funcoes:
        return
    now = datetime.now(timezone.utc)
    for position, funcao in enumerate(funcoes, start=1):
        existing = await session.scalar(select(Tentativa).where(Tentativa.funcao_atividade_uuid == funcao.uuid, Tentativa.aluno_uuid == aluno.uuid))
        if existing is not None:
            continue
        casos = list(await session.scalars(select(CasoTesteAtividade).where(CasoTesteAtividade.funcao_atividade_uuid == funcao.uuid)))
        if not casos:
            continue
        parcial_nota = (Decimal(funcao.nota_maxima) * Decimal(1) / Decimal(len(casos))).quantize(Decimal("0.01"))
        parcial = Tentativa(funcao_atividade_uuid=funcao.uuid, aluno_uuid=aluno.uuid, codigo_fonte=f"/* primeira tentativa de {funcao.nome} */", recebida_em=now - timedelta(hours=position * 3), avaliada_em=now - timedelta(hours=position * 3), status="AVALIADA", total_casos=len(casos), casos_aprovados=1, nota=parcial_nota)
        completa = Tentativa(funcao_atividade_uuid=funcao.uuid, aluno_uuid=aluno.uuid, codigo_fonte=f"/* solução completa de {funcao.nome} */", recebida_em=now - timedelta(hours=position * 2), avaliada_em=now - timedelta(hours=position * 2), status="AVALIADA", total_casos=len(casos), casos_aprovados=len(casos), nota=Decimal(funcao.nota_maxima))
        session.add_all([parcial, completa])
        await session.flush()
        for index, caso in enumerate(casos):
            session.add(ResultadoCasoTentativa(tentativa_uuid=parcial.uuid, caso_teste_atividade_uuid=caso.uuid, aprovado=index == 0))
            session.add(ResultadoCasoTentativa(tentativa_uuid=completa.uuid, caso_teste_atividade_uuid=caso.uuid, aprovado=True))


async def seed() -> None:
    settings = get_settings()
    engine = make_engine(settings)
    try:
        factory = make_session_factory(engine)
        async with factory() as session:
            users = {email: await get_or_create_user(session, *data) for data in USERS for email in [data[1]]}
            ana, bruno, carla = users["ana.souza@universidade.br"], users["bruno.lima@universidade.br"], users["carla.mendes@universidade.br"]
            pedro, marina, lucas, julia, rafael, beatriz = (users[email] for email in ("pedro.lacerda@aluno.universidade.br", "marina.alves@aluno.universidade.br", "lucas.rocha@aluno.universidade.br", "julia.campos@aluno.universidade.br", "rafael.nunes@aluno.universidade.br", "beatriz.lima@aluno.universidade.br"))
            algoritmos = await get_or_create_class(session, ana, "Algoritmos I - 2026", "ALG2026A")
            estruturas = await get_or_create_class(session, bruno, "Estruturas de Dados", "ED2026B")
            programacao = await get_or_create_class(session, carla, "Programação I - Noite", "PROG2026C")
            for aluno in (pedro, marina, lucas, julia): await ensure_enrollment(session, algoritmos, aluno)
            for aluno in (pedro, rafael, beatriz): await ensure_enrollment(session, estruturas, aluno)
            for aluno in (julia, lucas, beatriz): await ensure_enrollment(session, programacao, aluno)
            somar = await get_or_create_function(session, ana, "somar", "Implemente uma função que retorne a soma de dois números inteiros.", "int", [{"nome": "a", "tipo": "int"}, {"nome": "b", "tipo": "int"}], "FACIL", [([1, 2], 3, "Soma positiva"), ([-5, 8], 3, "Soma com negativo")])
            maior = await get_or_create_function(session, ana, "maiorElemento", "Retorne o maior elemento presente no vetor recebido.", "int", [{"nome": "valores", "tipo": "int[]"}], "MEDIO", [([[1, 4, 2]], 4, "Vetor misto"), ([[9]], 9, "Vetor unitário")])
            par = await get_or_create_function(session, bruno, "ehPar", "Retorne true quando o número for par e false nos demais casos.", "bool", [{"nome": "numero", "tipo": "int"}], "FACIL", [([2], True, "Número par"), ([7], False, "Número ímpar")])
            dobro = await get_or_create_function(session, ana, "dobro", "Retorne o dobro do valor inteiro recebido.", "int", [{"nome": "valor", "tipo": "int"}], "FACIL", [([4], 8, "Positivo"), ([-3], -6, "Negativo")])
            positivo = await get_or_create_function(session, ana, "contarPositivos", "Conte os valores positivos de um vetor.", "int", [{"nome": "valores", "tipo": "int[]"}], "MEDIO", [([[1, -2, 3]], 2, "Mistos"), ([[-1, -4]], 0, "Nenhum positivo")])
            media = await get_or_create_function(session, carla, "mediaDois", "Calcule a média de dois valores reais.", "double", [{"nome": "a", "tipo": "double"}, {"nome": "b", "tipo": "double"}], "FACIL", [([2.0, 4.0], 3.0, "Média simples"), ([-2.0, 2.0], 0.0, "Média zero")])
            basicas = await create_demo_activity(session, algoritmos, "Funções básicas", "Pratique funções, parâmetros e retornos.", [somar], "PUBLICADA")
            await create_demo_activity(session, algoritmos, "Vetores", "Atividade em rascunho para organização da turma.", [maior], "RASCUNHO")
            operacoes = await create_demo_activity(session, algoritmos, "Operações aritméticas", "Pratique retorno, comparação e composição de funções.", [somar, dobro], "PUBLICADA")
            await create_demo_activity(session, algoritmos, "Desafio de vetores", "Atividade encerrada para consulta de resultados.", [maior, positivo], "ENCERRADA")
            await create_demo_activity(session, estruturas, "Revisão de condicionais", "Uma prova aberta para a turma de Estruturas de Dados.", [par], "PUBLICADA", "PROVA")
            fundamentos = await create_demo_activity(session, programacao, "Fundamentos de funções", "Exercício de média e retorno decimal.", [media], "PUBLICADA")
            await ensure_demo_attempts(session, basicas, pedro)
            await ensure_demo_attempts(session, operacoes, pedro)
            await ensure_demo_attempts(session, operacoes, marina)
            await ensure_demo_attempts(session, fundamentos, julia)
            await session.commit()
    finally:
        await engine.dispose()


def main() -> int:
    args = parse_args()
    expected = f"SEED:{args.environment}:codelab_v2"
    if args.confirm != expected:
        raise SystemExit(f"Confirmação inválida. Use --confirm {expected}")
    asyncio.run(seed())
    print("Dados de demonstração disponíveis. Senha das contas: 123456")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
