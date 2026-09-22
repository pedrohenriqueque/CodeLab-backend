"""Prepara dados de demonstração no banco de desenvolvimento."""

import argparse
import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from .app.config.database import make_engine, make_session_factory
from .app.config.settings import Settings, get_settings
from .app.core.security import get_password_hash
from .app.models.atividade import Atividade
from .app.models.caso_teste import CasoTeste
from .app.models.funcao import FuncaoBiblioteca
from .app.models.funcao_atividade import CasoTesteAtividade, FuncaoAtividade
from .app.models.tentativa import ResultadoCasoTentativa, Tentativa
from .app.models.turma import MatriculaTurma, Turma
from .app.models.usuario import PerfilUsuario, Usuario


DEMO_PASSWORD = "123456"
USERS = (
    ("Administrador CodeLab", "admin@codelab.local", None, PerfilUsuario.ADMIN),
    ("Ana Souza", "ana.souza@universidade.br", None, PerfilUsuario.PROFESSOR),
    ("Bruno Lima", "bruno.lima@universidade.br", None, PerfilUsuario.PROFESSOR),
    ("Pedro Lacerda", "pedro.lacerda@aluno.universidade.br", "ALU001", PerfilUsuario.ALUNO),
    ("Marina Alves", "marina.alves@aluno.universidade.br", "ALU002", PerfilUsuario.ALUNO),
    ("Carla Mendes", "carla.mendes@universidade.br", None, PerfilUsuario.PROFESSOR),
    ("Lucas Rocha", "lucas.rocha@aluno.universidade.br", "ALU003", PerfilUsuario.ALUNO),
    ("Julia Campos", "julia.campos@aluno.universidade.br", "ALU004", PerfilUsuario.ALUNO),
    ("Rafael Nunes", "rafael.nunes@aluno.universidade.br", "ALU005", PerfilUsuario.ALUNO),
    ("Beatriz Lima", "beatriz.lima@aluno.universidade.br", "ALU006", PerfilUsuario.ALUNO),
)

# As duas soluções produzem, respectivamente, 1/2 e 2/2 casos aprovados.
ATTEMPT_CODES = {
    "somar": (
        "int somar(int a, int b) { return a > 0 ? a + b : 0; }",
        "int somar(int a, int b) { return a + b; }",
    ),
    "dobro": (
        "int dobro(int valor) { return valor > 0 ? valor * 2 : 0; }",
        "int dobro(int valor) { return valor * 2; }",
    ),
    "mediaDois": (
        "double mediaDois(double a, double b) { return a > 0 ? (a + b) / 2 : 1; }",
        "double mediaDois(double a, double b) { return (a + b) / 2; }",
    ),
}
ATTEMPT_CASES = {
    "somar": (([1, 2], 3), ([-5, 8], 3)),
    "dobro": (([4], 8), ([-3], -6)),
    "mediaDois": (([2.0, 4.0], 3.0), ([-2.0, 2.0], 0.0)),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Insere dados de demonstração no banco configurado.")
    parser.add_argument("--environment", required=True, choices=("development", "production"))
    parser.add_argument("--confirm", required=True)
    return parser.parse_args()


def validate_seed_target(settings: Settings, environment: str, confirmation: str) -> None:
    if environment not in {"development", "production"} or settings.environment != environment:
        raise ValueError("O ambiente informado deve corresponder a CODELAB_V2_ENVIRONMENT.")
    expected = f"SEED:{environment}:codelab_v2"
    if confirmation != expected:
        raise ValueError(f"Confirmação inválida. Use --confirm {expected}")


async def get_or_create_user(
    session: AsyncSession, nome: str, email: str, matricula: str | None, perfil: PerfilUsuario,
) -> Usuario:
    conditions = [Usuario.email == email]
    if matricula is not None:
        conditions.append(Usuario.matricula == matricula)
    matches = list(await session.scalars(select(Usuario).where(or_(*conditions))))
    if len(matches) > 1 or (matches and (matches[0].email != email or matches[0].perfil != perfil)):
        raise ValueError(f"Usuário de demonstração em conflito: {email}")
    if matches:
        user = matches[0]
        if matricula is not None and user.matricula != matricula:
            raise ValueError(f"Matrícula de demonstração em conflito: {email}")
        return user
    user = Usuario(nome=nome, email=email, matricula=matricula, perfil=perfil,
                   senha_hash=get_password_hash(DEMO_PASSWORD))
    session.add(user)
    await session.flush()
    return user


async def get_or_create_class(session: AsyncSession, professor: Usuario, nome: str, codigo: str) -> Turma:
    turma = await session.scalar(select(Turma).where(Turma.codigo == codigo))
    if turma is not None:
        if turma.professor_uuid != professor.uuid or turma.nome != nome:
            raise ValueError(f"Código de turma de demonstração em conflito: {codigo}")
        return turma
    turma = Turma(nome=nome, codigo=codigo, ativa=True, professor_uuid=professor.uuid)
    session.add(turma)
    await session.flush()
    return turma


async def ensure_enrollment(session: AsyncSession, turma: Turma, aluno: Usuario) -> None:
    existing = await session.scalar(select(MatriculaTurma).where(
        MatriculaTurma.turma_uuid == turma.uuid, MatriculaTurma.aluno_uuid == aluno.uuid
    ))
    if existing is None:
        session.add(MatriculaTurma(turma_uuid=turma.uuid, aluno_uuid=aluno.uuid))


async def get_or_create_function(
    session: AsyncSession, professor: Usuario, nome: str, enunciado: str,
    retorno: str, parametros: list[dict[str, str]], dificuldade: str,
    casos: list[tuple[list[object], object, str]],
) -> FuncaoBiblioteca:
    funcao = await session.scalar(select(FuncaoBiblioteca).where(
        FuncaoBiblioteca.professor_uuid == professor.uuid, FuncaoBiblioteca.nome == nome
    ))
    if funcao is None:
        funcao = FuncaoBiblioteca(
            professor_uuid=professor.uuid, nome=nome, enunciado=enunciado,
            tipo_retorno=retorno, parametros=parametros, dificuldade=dificuldade, compartilhada=True,
        )
        session.add(funcao)
        await session.flush()
    elif funcao.tipo_retorno != retorno or funcao.parametros != parametros:
        raise ValueError(f"Assinatura da função de demonstração em conflito: {nome}")

    existing = await session.scalar(select(CasoTeste.uuid).where(CasoTeste.funcao_uuid == funcao.uuid).limit(1))
    if existing is None:
        session.add_all(CasoTeste(
            funcao_uuid=funcao.uuid, entradas=entradas, retorno_esperado=esperado,
            visibilidade="VISIVEL", descricao=descricao,
        ) for entradas, esperado, descricao in casos)
    return funcao


async def create_demo_activity(
    session: AsyncSession, turma: Turma, titulo: str, descricao: str,
    funcoes: list[FuncaoBiblioteca], status: str, tipo: str = "EXERCICIO",
) -> Atividade:
    atividade = await session.scalar(select(Atividade).where(
        Atividade.turma_uuid == turma.uuid, Atividade.titulo == titulo
    ))
    if atividade is not None:
        if atividade.tipo != tipo:
            raise ValueError(f"Tipo da atividade de demonstração em conflito: {titulo}")
        return atividade

    now = datetime.now(timezone.utc)
    atividade = Atividade(
        turma_uuid=turma.uuid, titulo=titulo, descricao=descricao,
        inicio_em=now - timedelta(days=1), fim_em=now + timedelta(days=14),
        status=status, tipo=tipo, permitir_multiplas_submissoes=tipo == "EXERCICIO",
    )
    session.add(atividade)
    await session.flush()
    for ordem, origem in enumerate(funcoes, start=1):
        interna = FuncaoAtividade(
            atividade_uuid=atividade.uuid, nome=origem.nome, enunciado=origem.enunciado,
            tipo_retorno=origem.tipo_retorno, parametros=origem.parametros,
            dificuldade=origem.dificuldade, nota_maxima=Decimal("10") / len(funcoes), ordem=ordem,
        )
        session.add(interna)
        await session.flush()
        casos = await session.scalars(select(CasoTeste).where(CasoTeste.funcao_uuid == origem.uuid))
        session.add_all(CasoTesteAtividade(
            funcao_atividade_uuid=interna.uuid, entradas=caso.entradas,
            retorno_esperado=caso.retorno_esperado, visibilidade=caso.visibilidade,
            descricao=caso.descricao,
        ) for caso in casos)
    return atividade


async def ensure_demo_attempts(session: AsyncSession, atividade: Atividade, aluno: Usuario) -> None:
    """Preserva envios existentes e cria um histórico ilustrativo apenas onde estiver vazio."""
    funcoes = list(await session.scalars(select(FuncaoAtividade).where(
        FuncaoAtividade.atividade_uuid == atividade.uuid
    ).order_by(FuncaoAtividade.ordem)))
    now = datetime.now(timezone.utc)
    for position, funcao in enumerate(funcoes, start=1):
        existing = await session.scalar(select(Tentativa.uuid).where(
            Tentativa.funcao_atividade_uuid == funcao.uuid, Tentativa.aluno_uuid == aluno.uuid
        ).limit(1))
        if existing is not None:
            continue
        cases = list(await session.scalars(select(CasoTesteAtividade).where(
            CasoTesteAtividade.funcao_atividade_uuid == funcao.uuid
        ).order_by(CasoTesteAtividade.uuid)))
        if not cases:
            continue
        expected_cases = ATTEMPT_CASES.get(funcao.nome)
        if expected_cases is None or len(cases) != 2 or any(
            not any(case.entradas == inputs and case.retorno_esperado == expected
                    for case in cases)
            for inputs, expected in expected_cases
        ):
            raise ValueError(f"Casos da função de demonstração incompatíveis com os envios: {funcao.nome}")

        partial_code, complete_code = ATTEMPT_CODES[funcao.nome]
        partial = Tentativa(
            funcao_atividade_uuid=funcao.uuid, aluno_uuid=aluno.uuid, codigo_fonte=partial_code,
            recebida_em=now - timedelta(hours=position * 3),
            avaliada_em=now - timedelta(hours=position * 3), status="AVALIADA",
            total_casos=2, casos_aprovados=1,
            nota=(Decimal(funcao.nota_maxima) / 2).quantize(Decimal("0.01")),
        )
        complete = Tentativa(
            funcao_atividade_uuid=funcao.uuid, aluno_uuid=aluno.uuid, codigo_fonte=complete_code,
            recebida_em=now - timedelta(hours=position * 2),
            avaliada_em=now - timedelta(hours=position * 2), status="AVALIADA",
            total_casos=2, casos_aprovados=2, nota=Decimal(funcao.nota_maxima),
        )
        session.add_all((partial, complete))
        await session.flush()
        for case in cases:
            session.add_all((
                ResultadoCasoTentativa(
                    tentativa_uuid=partial.uuid, caso_teste_atividade_uuid=case.uuid,
                    aprovado=case.entradas == expected_cases[0][0],
                ),
                ResultadoCasoTentativa(
                    tentativa_uuid=complete.uuid, caso_teste_atividade_uuid=case.uuid,
                    aprovado=True,
                ),
            ))


async def seed(settings: Settings) -> None:
    if settings.environment not in {"development", "production"}:
        raise ValueError("O seed só pode ser executado em development ou production.")
    engine = make_engine(settings)
    try:
        factory = make_session_factory(engine)
        async with factory() as session, session.begin():
            users = {data[1]: await get_or_create_user(session, *data) for data in USERS}
            ana = users["ana.souza@universidade.br"]
            bruno = users["bruno.lima@universidade.br"]
            carla = users["carla.mendes@universidade.br"]
            pedro = users["pedro.lacerda@aluno.universidade.br"]
            marina = users["marina.alves@aluno.universidade.br"]
            lucas = users["lucas.rocha@aluno.universidade.br"]
            julia = users["julia.campos@aluno.universidade.br"]
            rafael = users["rafael.nunes@aluno.universidade.br"]
            beatriz = users["beatriz.lima@aluno.universidade.br"]

            algoritmos = await get_or_create_class(session, ana, "Algoritmos I - 2026", "ALG2026A")
            estruturas = await get_or_create_class(session, bruno, "Estruturas de Dados", "ED2026B")
            programacao = await get_or_create_class(session, carla, "Programação I - Noite", "PROG2026C")
            for aluno in (pedro, marina, lucas, julia):
                await ensure_enrollment(session, algoritmos, aluno)
            for aluno in (pedro, rafael, beatriz):
                await ensure_enrollment(session, estruturas, aluno)
            for aluno in (julia, lucas, beatriz):
                await ensure_enrollment(session, programacao, aluno)

            somar = await get_or_create_function(
                session, ana, "somar", "Implemente uma função que retorne a soma de dois números inteiros.",
                "int", [{"nome": "a", "tipo": "int"}, {"nome": "b", "tipo": "int"}], "FACIL",
                [([1, 2], 3, "Soma positiva"), ([-5, 8], 3, "Soma com negativo")],
            )
            maior = await get_or_create_function(
                session, ana, "maiorElemento", "Retorne o maior elemento presente no vetor recebido.",
                "int", [{"nome": "valores", "tipo": "int[]"}], "MEDIO",
                [([[1, 4, 2]], 4, "Vetor misto"), ([[9]], 9, "Vetor unitário")],
            )
            par = await get_or_create_function(
                session, bruno, "ehPar", "Retorne true quando o número for par e false nos demais casos.",
                "bool", [{"nome": "numero", "tipo": "int"}], "FACIL",
                [([2], True, "Número par"), ([7], False, "Número ímpar")],
            )
            dobro = await get_or_create_function(
                session, ana, "dobro", "Retorne o dobro do valor inteiro recebido.",
                "int", [{"nome": "valor", "tipo": "int"}], "FACIL",
                [([4], 8, "Positivo"), ([-3], -6, "Negativo")],
            )
            positivo = await get_or_create_function(
                session, ana, "contarPositivos", "Conte os valores positivos de um vetor.",
                "int", [{"nome": "valores", "tipo": "int[]"}], "MEDIO",
                [([[1, -2, 3]], 2, "Mistos"), ([[-1, -4]], 0, "Nenhum positivo")],
            )
            media = await get_or_create_function(
                session, carla, "mediaDois", "Calcule a média de dois valores reais.",
                "double", [{"nome": "a", "tipo": "double"}, {"nome": "b", "tipo": "double"}], "FACIL",
                [([2.0, 4.0], 3.0, "Média simples"), ([-2.0, 2.0], 0.0, "Média zero")],
            )

            basicas = await create_demo_activity(session, algoritmos, "Funções básicas", "Pratique funções, parâmetros e retornos.", [somar], "PUBLICADA")
            await create_demo_activity(session, algoritmos, "Vetores", "Atividade em rascunho para organização da turma.", [maior], "RASCUNHO")
            operacoes = await create_demo_activity(session, algoritmos, "Operações aritméticas", "Pratique retorno, comparação e composição de funções.", [somar, dobro], "PUBLICADA")
            await create_demo_activity(session, algoritmos, "Desafio de vetores", "Atividade encerrada para consulta de resultados.", [maior, positivo], "ENCERRADA")
            await create_demo_activity(session, estruturas, "Revisão de condicionais", "Uma prova aberta para a turma de Estruturas de Dados.", [par], "PUBLICADA", "PROVA")
            fundamentos = await create_demo_activity(session, programacao, "Fundamentos de funções", "Exercício de média e retorno decimal.", [media], "PUBLICADA")
            for atividade, aluno in (
                (basicas, pedro), (operacoes, pedro), (operacoes, marina), (fundamentos, julia),
            ):
                await ensure_demo_attempts(session, atividade, aluno)
    finally:
        await engine.dispose()


def main() -> int:
    args = parse_args()
    settings = get_settings()
    try:
        validate_seed_target(settings, args.environment, args.confirm)
    except ValueError as exc:
        raise SystemExit(str(exc)) from None
    asyncio.run(seed(settings))
    print("Dados de demonstração disponíveis. Senha das novas contas: 123456")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
