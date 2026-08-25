r"""
seed.py — Popula o banco com dados mock realistas para o CodeLab.

Como rodar:
    .\.venv\Scripts\python.exe seed.py

O script:
1. Apaga todos os dados existentes (na ordem certa para FKs).
2. Insere usuários, atividades, funções, casos de teste e submissões.
"""

import asyncio
import json
from datetime import datetime, timezone, timedelta

from sqlalchemy import text

from app.db.session import engine, async_session, init_db, Base
from app.db.models.usuario import Usuario
from app.db.models.atividade import Atividade
from app.db.models.funcao import Funcao
from app.db.models.caso_teste import CasoTeste
from app.db.models.submissao import Submissao
from app.core.security import get_password_hash

# ─────────────────────────────────────────────
# UUIDs fixos para consistência total
# ─────────────────────────────────────────────
U_PROF  = "a1000000-0000-0000-0000-000000000001"
U_PEDRO = "a2000000-0000-0000-0000-000000000002"
U_JOAO  = "a2000000-0000-0000-0000-000000000003"

ATV_001 = "b1000000-0000-0000-0000-000000000001"
ATV_002 = "b1000000-0000-0000-0000-000000000002"
ATV_003 = "b1000000-0000-0000-0000-000000000003"

F_SOMA  = "c1000000-0000-0000-0000-000000000001"
F_PAR   = "c1000000-0000-0000-0000-000000000002"
F_MAIOR = "c1000000-0000-0000-0000-000000000003"
F_MEDIA = "c1000000-0000-0000-0000-000000000004"
F_MAXEL = "c1000000-0000-0000-0000-000000000005"
F_FIB   = "c1000000-0000-0000-0000-000000000006"

now = datetime.now(timezone.utc)


# ─────────────────────────────────────────────
# CÓDIGO C MOCK (realista mas simples)
# ─────────────────────────────────────────────

CODIGO_SOMA_CORRETO = """\
int soma_ate_n(int n) {
    int soma = 0;
    for (int i = 1; i <= n; i++) {
        soma += i;
    }
    return soma;
}"""

CODIGO_PAR_PARCIAL = """\
int e_par(int n) {
    /* BUG: trata 0 como ímpar */
    if (n == 0) return 0;
    return (n % 2 == 0) ? 1 : 0;
}"""

CODIGO_PAR_ERRADO = """\
int e_par(int n) {
    /* Totalmente errado: sempre retorna 1 */
    return 1;
}"""

CODIGO_MEDIA_ERRO_COMPILACAO = """\
float media_array(int v[], int n) {
    float soma = 0
    for (int i = 0; i < n; i++) {
        soma += v[i];
    }
    return soma / n;
}"""

CODIGO_MAIOR_CORRETO = """\
int maior_de_tres(int a, int b, int c) {
    int maior = a;
    if (b > maior) maior = b;
    if (c > maior) maior = c;
    return maior;
}"""

CODIGO_SOMA_PARCIAL = """\
int soma_ate_n(int n) {
    /* BUG: começa em 2 em vez de 1 */
    int soma = 0;
    for (int i = 2; i <= n; i++) {
        soma += i;
    }
    return soma;
}"""

CODIGO_MAIOR_ELEM_PENDENTE = """\
int maior_elemento(int v[], int n) {
    int maior = v[0];
    for (int i = 1; i < n; i++) {
        if (v[i] > maior) maior = v[i];
    }
    return maior;
}"""


# ─────────────────────────────────────────────
# RESULTADO_JSON helpers
# ─────────────────────────────────────────────

def resultado_avaliado(casos: list[dict], nota: float, pontos_max: float) -> dict:
    return {
        "nota": nota,
        "pontosMaximo": pontos_max,
        "totalCasos": len(casos),
        "casosPassados": sum(1 for c in casos if c["status"] == "PASS"),
        "tempoMs": 42,
        "memoriaKb": 512,
        "erroCompilacao": None,
        "erroExecucao": None,
        "casos": casos,
    }


def resultado_erro_compilacao(stderr: str) -> dict:
    return {
        "nota": 0,
        "pontosMaximo": 0,
        "totalCasos": 0,
        "casosPassados": 0,
        "tempoMs": 0,
        "memoriaKb": 0,
        "erroCompilacao": stderr,
        "erroExecucao": None,
        "casos": [],
    }


# ─────────────────────────────────────────────
# SEED PRINCIPAL
# ─────────────────────────────────────────────

async def limpar_banco(session):
    """Apaga todos os dados na ordem correta (FKs)."""
    print("[*] Limpando banco...")
    await session.execute(text("DELETE FROM submissoes"))
    await session.execute(text("DELETE FROM casos_teste"))
    await session.execute(text("DELETE FROM funcoes"))
    await session.execute(text("DELETE FROM atividades"))
    await session.execute(text("DELETE FROM usuarios"))
    await session.commit()
    print("   [ok] Banco limpo.\n")


async def seed_usuarios(session):
    print("[*] Inserindo usuarios...")
    # Gera hash bcrypt valido para garantir login funcional.
    FAKE_HASH = get_password_hash("123456")

    usuarios = [
        Usuario(
            uuid=U_PROF,
            nome="Ana Souza",
            email="ana.souza@universidade.br",
            matricula=None,
            tipo="professor",
            senha_hash=FAKE_HASH,
        ),
        Usuario(
            uuid=U_PEDRO,
            nome="Pedro Lacerda",
            email="pedro.lacerda@aluno.universidade.br",
            matricula="20231001",
            tipo="aluno",
            senha_hash=FAKE_HASH,
        ),
        Usuario(
            uuid=U_JOAO,
            nome="João Silva",
            email="joao.silva@aluno.universidade.br",
            matricula="20231002",
            tipo="aluno",
            senha_hash=FAKE_HASH,
        ),
    ]
    session.add_all(usuarios)
    await session.commit()
    print(f"   [ok] {len(usuarios)} usuarios inseridos.\n")


async def seed_atividades(session):
    print("[*] Inserindo atividades...")
    atividades = [
        Atividade(
            uuid=ATV_001,
            professor_uuid=U_PROF,
            titulo="Lista 1 – Introdução a Loops e Condicionais",
            descricao="Atividade com funções simples envolvendo loops, condicionais e operações aritméticas em C.",
            pontuacao_maxima=30,
            data_abertura=now - timedelta(days=7),
            data_fechamento=now + timedelta(days=7),
            status="publicado",
        ),
        Atividade(
            uuid=ATV_002,
            professor_uuid=U_PROF,
            titulo="Lista 2 – Arrays e Funções",
            descricao="Atividade sobre manipulação de arrays e funções com parâmetros.",
            pontuacao_maxima=40,
            data_abertura=now - timedelta(days=1),
            data_fechamento=now + timedelta(days=14),
            status="publicado",
        ),
        Atividade(
            uuid=ATV_003,
            professor_uuid=U_PROF,
            titulo="Prova 1 – Avaliação Parcial",
            descricao="Primeira avaliação parcial da disciplina, com foco em problemas integradores.",
            pontuacao_maxima=30,
            data_abertura=now - timedelta(hours=2),
            data_fechamento=now + timedelta(days=1),
            status="publicado",
            tipo="prova",
            duracao_minutos=90,
            bloquear_paste=True,
            notas_liberadas=False,
        ),
    ]
    session.add_all(atividades)
    await session.commit()
    print(f"   [ok] {len(atividades)} atividades inseridas.\n")


async def seed_funcoes(session):
    print("[*] Inserindo funcoes...")
    funcoes = [
        # ── Atividade 1 ──────────────────────────────
        Funcao(
            uuid=F_SOMA,
            atividade_uuid=ATV_001,
            nome_funcao="soma_ate_n",
            pontos=10,
            ordem=1,
            descricao="Recebe um inteiro positivo n e retorna a soma de 1 até n. Ex.: n=4 → 1+2+3+4=10.",
            dificuldade="facil",
            max_tentativas=3,
            dicas=["Você precisa usar um laço de repetição.", "Tente usar o laço for ou while.", "A estrutura for (int i = 1; i <= n; i++) é ideal para isso."],
            parametros=[{"nome": "n", "tipo": "int", "descricao": "limite superior da soma (n >= 1)"}],
            retorno={"tipo": "int", "descricao": "soma dos inteiros de 1 até n"},
        ),
        Funcao(
            uuid=F_PAR,
            atividade_uuid=ATV_001,
            nome_funcao="e_par",
            pontos=10,
            ordem=2,
            dificuldade="facil",
            descricao="Retorna 1 se o número for par e 0 se for ímpar.",
            parametros=[{"nome": "n", "tipo": "int", "descricao": "inteiro para verificar paridade"}],
            retorno={"tipo": "int", "descricao": "1 se n for par, 0 caso contrário"},
        ),
        Funcao(
            uuid=F_MAIOR,
            atividade_uuid=ATV_001,
            nome_funcao="maior_de_tres",
            pontos=10,
            ordem=3,
            descricao="Recebe três inteiros e retorna o maior deles.",
            parametros=[
                {"nome": "a", "tipo": "int"},
                {"nome": "b", "tipo": "int"},
                {"nome": "c", "tipo": "int"},
            ],
            retorno={"tipo": "int", "descricao": "maior valor entre a, b e c"},
        ),
        # ── Atividade 2 ──────────────────────────────
        Funcao(
            uuid=F_MEDIA,
            atividade_uuid=ATV_002,
            nome_funcao="media_array",
            pontos=20,
            ordem=1,
            descricao="Recebe um array de inteiros e seu tamanho, e retorna a média aritmética como float.",
            parametros=[
                {"nome": "v", "tipo": "int[]", "descricao": "vetor de inteiros"},
                {"nome": "n", "tipo": "int", "descricao": "tamanho do vetor"},
            ],
            retorno={"tipo": "float", "descricao": "média aritmética dos valores"},
        ),
        Funcao(
            uuid=F_MAXEL,
            atividade_uuid=ATV_002,
            nome_funcao="maior_elemento",
            pontos=20,
            ordem=2,
            descricao="Recebe um array de inteiros e seu tamanho, e retorna o maior elemento.",
            parametros=[
                {"nome": "v", "tipo": "int[]"},
                {"nome": "n", "tipo": "int"},
            ],
            retorno={"tipo": "int", "descricao": "maior valor do vetor"},
        ),
        # ── Atividade 3 (Prova) ─────────────────────
        Funcao(
            uuid=F_FIB,
            atividade_uuid=ATV_003,
            nome_funcao="fibonacci_n",
            pontos=30,
            ordem=1,
            dificuldade="medio",
            max_tentativas=1,
            descricao="Retorna o n-esimo termo da sequencia de Fibonacci (n >= 0).",
            parametros=[
                {"nome": "n", "tipo": "int", "descricao": "indice do termo"},
            ],
            retorno={"tipo": "int", "descricao": "valor do termo n"},
            dicas=[],
        ),
    ]
    session.add_all(funcoes)
    await session.commit()
    print(f"   [ok] {len(funcoes)} funcoes inseridas.\n")


async def seed_casos_teste(session):
    print("[*] Inserindo casos de teste...")
    casos = [
        # ── soma_ate_n ───────────────────────────────
        CasoTeste(
            uuid="d1000000-0000-0000-0000-000000000001",
            funcao_uuid=F_SOMA, numero=1,
            inputs={"n": 1},
            output_esperado={"retorno": 1},
            descricao="n=1 → soma = 1",
        ),
        CasoTeste(
            uuid="d1000000-0000-0000-0000-000000000002",
            funcao_uuid=F_SOMA, numero=2,
            inputs={"n": 4},
            output_esperado={"retorno": 10},
            descricao="n=4 → 1+2+3+4 = 10",
        ),
        CasoTeste(
            uuid="d1000000-0000-0000-0000-000000000003",
            funcao_uuid=F_SOMA, numero=3,
            inputs={"n": 10},
            output_esperado={"retorno": 55},
            descricao="n=10 → soma Gauss = 55",
        ),
        # ── e_par ────────────────────────────────────
        CasoTeste(
            uuid="d2000000-0000-0000-0000-000000000001",
            funcao_uuid=F_PAR, numero=1,
            inputs={"n": 2},
            output_esperado={"retorno": 1},
            descricao="2 é par → 1",
        ),
        CasoTeste(
            uuid="d2000000-0000-0000-0000-000000000002",
            funcao_uuid=F_PAR, numero=2,
            inputs={"n": 7},
            output_esperado={"retorno": 0},
            descricao="7 é ímpar → 0",
        ),
        CasoTeste(
            uuid="d2000000-0000-0000-0000-000000000003",
            funcao_uuid=F_PAR, numero=3,
            inputs={"n": 0},
            output_esperado={"retorno": 1},
            descricao="0 é par → 1",
        ),
        # ── maior_de_tres ────────────────────────────
        CasoTeste(
            uuid="d3000000-0000-0000-0000-000000000001",
            funcao_uuid=F_MAIOR, numero=1,
            inputs={"a": 3, "b": 7, "c": 5},
            output_esperado={"retorno": 7},
            descricao="Maior de 3, 7, 5 → 7",
        ),
        CasoTeste(
            uuid="d3000000-0000-0000-0000-000000000002",
            funcao_uuid=F_MAIOR, numero=2,
            inputs={"a": 10, "b": 10, "c": 5},
            output_esperado={"retorno": 10},
            descricao="Maior de 10, 10, 5 → 10 (empate)",
        ),
        CasoTeste(
            uuid="d3000000-0000-0000-0000-000000000003",
            funcao_uuid=F_MAIOR, numero=3,
            inputs={"a": -1, "b": -5, "c": -3},
            output_esperado={"retorno": -1},
            descricao="Todos negativos: maior é -1",
        ),
        # ── media_array ──────────────────────────────
        CasoTeste(
            uuid="d4000000-0000-0000-0000-000000000001",
            funcao_uuid=F_MEDIA, numero=1,
            inputs={"v": [2, 4, 6], "n": 3},
            output_esperado={"retorno": 4.0},
            descricao="Média de [2,4,6] = 4.0",
        ),
        CasoTeste(
            uuid="d4000000-0000-0000-0000-000000000002",
            funcao_uuid=F_MEDIA, numero=2,
            inputs={"v": [1, 2, 3, 4, 5], "n": 5},
            output_esperado={"retorno": 3.0},
            descricao="Média de [1..5] = 3.0",
        ),
        # ── maior_elemento ───────────────────────────
        CasoTeste(
            uuid="d5000000-0000-0000-0000-000000000001",
            funcao_uuid=F_MAXEL, numero=1,
            inputs={"v": [3, 9, 1, 7, 2], "n": 5},
            output_esperado={"retorno": 9},
            descricao="Maior de [3,9,1,7,2] = 9",
        ),
        CasoTeste(
            uuid="d5000000-0000-0000-0000-000000000002",
            funcao_uuid=F_MAXEL, numero=2,
            inputs={"v": [5, 5, 5], "n": 3},
            output_esperado={"retorno": 5},
            descricao="Todos iguais → 5",
        ),
        # ── fibonacci_n (prova) ─────────────────────
        CasoTeste(
            uuid="d6000000-0000-0000-0000-000000000001",
            funcao_uuid=F_FIB, numero=1,
            inputs={"n": 0},
            output_esperado={"retorno": 0},
            descricao="Fib(0) = 0",
        ),
        CasoTeste(
            uuid="d6000000-0000-0000-0000-000000000002",
            funcao_uuid=F_FIB, numero=2,
            inputs={"n": 1},
            output_esperado={"retorno": 1},
            descricao="Fib(1) = 1",
        ),
        CasoTeste(
            uuid="d6000000-0000-0000-0000-000000000003",
            funcao_uuid=F_FIB, numero=3,
            inputs={"n": 8},
            output_esperado={"retorno": 21},
            descricao="Fib(8) = 21",
        ),
    ]
    session.add_all(casos)
    await session.commit()
    print(f"   [ok] {len(casos)} casos de teste inseridos.\n")


async def seed_submissoes(session):
    print("[*] Inserindo submissoes...")

    submissoes = [

        # ── 1. Pedro, soma_ate_n — PERFEITO ──────────────────────────────────
        Submissao(
            uuid="e1000000-0000-0000-0000-000000000001",
            funcao_uuid=F_SOMA,
            aluno_uuid=U_PEDRO,
            codigo_submetido=CODIGO_SOMA_CORRETO,
            data_submissao=now - timedelta(hours=5),
            tentativa_numero=1,
            status="avaliado",
            nota=10.0,
            resultado_json=resultado_avaliado(
                casos=[
                    {"numero": 1, "status": "PASS", "expected": 1,  "got": 1},
                    {"numero": 2, "status": "PASS", "expected": 10, "got": 10},
                    {"numero": 3, "status": "PASS", "expected": 55, "got": 55},
                ],
                nota=10.0, pontos_max=10.0,
            ),
        ),

        # ── 2. Pedro, e_par — PARCIAL (0 tratado como ímpar) ─────────────────
        Submissao(
            uuid="e1000000-0000-0000-0000-000000000002",
            funcao_uuid=F_PAR,
            aluno_uuid=U_PEDRO,
            codigo_submetido=CODIGO_PAR_PARCIAL,
            data_submissao=now - timedelta(hours=4),
            tentativa_numero=1,
            status="avaliado",
            nota=6.67,
            resultado_json=resultado_avaliado(
                casos=[
                    {"numero": 1, "status": "PASS", "expected": 1, "got": 1},
                    {"numero": 2, "status": "PASS", "expected": 0, "got": 0},
                    {"numero": 3, "status": "FAIL", "expected": 1, "got": 0},
                ],
                nota=6.67, pontos_max=10.0,
            ),
        ),

        # ── 3. João, e_par — FALHA TOTAL ─────────────────────────────────────
        Submissao(
            uuid="e2000000-0000-0000-0000-000000000001",
            funcao_uuid=F_PAR,
            aluno_uuid=U_JOAO,
            codigo_submetido=CODIGO_PAR_ERRADO,
            data_submissao=now - timedelta(hours=3),
            tentativa_numero=1,
            status="avaliado",
            nota=0.0,
            resultado_json=resultado_avaliado(
                casos=[
                    {"numero": 1, "status": "PASS", "expected": 1, "got": 1},
                    {"numero": 2, "status": "FAIL", "expected": 0, "got": 1},
                    {"numero": 3, "status": "PASS", "expected": 1, "got": 1},
                ],
                nota=0.0, pontos_max=10.0,
            ),
        ),

        # ── 4. João, media_array — ERRO DE COMPILAÇÃO ─────────────────────────
        Submissao(
            uuid="e2000000-0000-0000-0000-000000000002",
            funcao_uuid=F_MEDIA,
            aluno_uuid=U_JOAO,
            codigo_submetido=CODIGO_MEDIA_ERRO_COMPILACAO,
            data_submissao=now - timedelta(hours=2),
            tentativa_numero=1,
            status="erro",
            nota=0.0,
            resultado_json=resultado_erro_compilacao(
                stderr=(
                    "seed_media.c:3:20: error: expected ';' before 'for'\n"
                    "     float soma = 0\n"
                    "                    ^\n"
                    "seed_media.c:4:5: error: 'for' undeclared (first use in this function)\n"
                    "     for (int i = 0; i < n; i++) {\n"
                    "     ^~~"
                )
            ),
        ),

        # ── 5. Pedro, maior_de_tres — PERFEITO ───────────────────────────────
        Submissao(
            uuid="e1000000-0000-0000-0000-000000000003",
            funcao_uuid=F_MAIOR,
            aluno_uuid=U_PEDRO,
            codigo_submetido=CODIGO_MAIOR_CORRETO,
            data_submissao=now - timedelta(hours=1),
            tentativa_numero=1,
            status="avaliado",
            nota=10.0,
            resultado_json=resultado_avaliado(
                casos=[
                    {"numero": 1, "status": "PASS", "expected": 7,  "got": 7},
                    {"numero": 2, "status": "PASS", "expected": 10, "got": 10},
                    {"numero": 3, "status": "PASS", "expected": -1, "got": -1},
                ],
                nota=10.0, pontos_max=10.0,
            ),
        ),

        # ── 6. João, soma_ate_n — PARCIAL (começa em 2) ───────────────────────
        Submissao(
            uuid="e2000000-0000-0000-0000-000000000003",
            funcao_uuid=F_SOMA,
            aluno_uuid=U_JOAO,
            codigo_submetido=CODIGO_SOMA_PARCIAL,
            data_submissao=now - timedelta(minutes=90),
            tentativa_numero=1,
            status="avaliado",
            nota=3.33,
            resultado_json=resultado_avaliado(
                casos=[
                    {"numero": 1, "status": "FAIL", "expected": 1,  "got": 0},
                    {"numero": 2, "status": "FAIL", "expected": 10, "got": 9},
                    {"numero": 3, "status": "PASS", "expected": 55, "got": 54},
                ],
                nota=3.33, pontos_max=10.0,
            ),
        ),

        # ── 7. Pedro, maior_elemento — PENDENTE ──────────────────────────────
        Submissao(
            uuid="e1000000-0000-0000-0000-000000000004",
            funcao_uuid=F_MAXEL,
            aluno_uuid=U_PEDRO,
            codigo_submetido=CODIGO_MAIOR_ELEM_PENDENTE,
            data_submissao=now - timedelta(minutes=5),
            tentativa_numero=1,
            status="pendente",
            nota=None,
            resultado_json=None,
        ),
    ]

    session.add_all(submissoes)
    await session.commit()
    print(f"   [ok] {len(submissoes)} submissoes inseridas.\n")


async def main():
    print("=" * 55)
    print("  CodeLab - Seed de dados mock")
    print("=" * 55 + "\n")

    # Recria todas as tabelas para sincronizar novas colunas
    print("[*] Sincronizando tabelas com o banco de dados...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    print("   [ok] Tabelas recriadas e sincronizadas com sucesso.\n")

    async with async_session() as session:
        await seed_usuarios(session)
        await seed_atividades(session)
        await seed_funcoes(session)
        await seed_casos_teste(session)
        await seed_submissoes(session)

    print("=" * 55)
    print("  [ok] Seed concluido com sucesso!")
    print("=" * 55)
    print()
    print("Credenciais de acesso (senha: 123456):")
    print("  Professor : ana.souza@universidade.br")
    print("  Aluno 1   : pedro.lacerda@aluno.universidade.br")
    print("  Aluno 2   : joao.silva@aluno.universidade.br")
    print()
    print("UUIDs fixos:")
    print(f"  prof       -> {U_PROF}")
    print(f"  pedro      -> {U_PEDRO}")
    print(f"  joao       -> {U_JOAO}")
    print(f"  atividade1 -> {ATV_001}")
    print(f"  atividade2 -> {ATV_002}")
    print(f"  atividade3 -> {ATV_003}")


if __name__ == "__main__":
    asyncio.run(main())
