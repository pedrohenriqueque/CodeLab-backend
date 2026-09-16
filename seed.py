r"""
seed.py — Popula o banco de dados do CodeLab com uma massa de dados completa, realista e consistente.

Compatível com o modelo de domínio atual:
  - Usuários (Professores e Alunos com senha '123456')
  - Biblioteca Central de Funções C (RN01, RN02, RN04, RN05)
  - Casos de Teste Canônicos por Função (output_esperado com chave 'valor')
  - Atividades (Listas de Exercícios, Prova cronometrada e Rascunho)
  - Associação N:N Atividade-Função com pesos, dificuldades e ordem (RN07)
  - Configuração Contextual de Casos de Teste (casos visíveis e ocultos, RN15)
  - Submissões com código C real, múltiplos status e histórico preservado (RN12)
  - Entregas Finais consolidadas de atividades (RN14)

Como rodar:
    .\.venv\Scripts\python.exe seed.py
"""

import asyncio
from datetime import datetime, timezone, timedelta

from sqlalchemy import text

from app.db.session import engine, async_session, init_db
from app.db.models import (
    Usuario,
    Atividade,
    Funcao,
    CasoTeste,
    AtividadeFuncao,
    AtividadeFuncaoCasoTeste,
    Submissao,
    EntregaAtividade,
)
from app.core.security import get_password_hash

# ─────────────────────────────────────────────
# UUIDs FIXOS PARA REPRODUTIBILIDADE E TESTES
# ─────────────────────────────────────────────

# Usuários
U_PROF_ANA    = "a1000000-0000-0000-0000-000000000001"
U_PROF_CARLOS = "a1000000-0000-0000-0000-000000000002"
U_ALUNO_PEDRO = "a2000000-0000-0000-0000-000000000001"
U_ALUNO_JOAO  = "a2000000-0000-0000-0000-000000000002"
U_ALUNO_BEA   = "a2000000-0000-0000-0000-000000000003"
U_ALUNO_LUCAS = "a2000000-0000-0000-0000-000000000004"

# Atividades
ATV_001 = "b1000000-0000-0000-0000-000000000001"  # Lista 1 - Loops e Condicionais
ATV_002 = "b1000000-0000-0000-0000-000000000002"  # Lista 2 - Vetores e Algoritmos
ATV_003 = "b1000000-0000-0000-0000-000000000003"  # Prova 1 - Avaliação Cronometrada
ATV_004 = "b1000000-0000-0000-0000-000000000004"  # Lista 3 - Rascunho Professor

# Funções da Biblioteca Central
F_SOMA   = "c1000000-0000-0000-0000-000000000001"
F_PAR    = "c1000000-0000-0000-0000-000000000002"
F_MAIOR3 = "c1000000-0000-0000-0000-000000000003"
F_POT    = "c1000000-0000-0000-0000-000000000004"
F_FAT    = "c1000000-0000-0000-0000-000000000005"
F_MEDIA  = "c1000000-0000-0000-0000-000000000006"
F_MAXEL  = "c1000000-0000-0000-0000-000000000007"
F_CONTAR = "c1000000-0000-0000-0000-000000000008"
F_FIB    = "c1000000-0000-0000-0000-000000000009"
F_MDC    = "c1000000-0000-0000-0000-000000000010"

# Timestamp base
now = datetime.now(timezone.utc)

# ─────────────────────────────────────────────
# CÓDIGOS C PARA SUBMISSÕES MOCK
# ─────────────────────────────────────────────

C_SOMA_CORRETO = """\
int soma_ate_n(int n) {
    int soma = 0;
    for (int i = 1; i <= n; i++) {
        soma += i;
    }
    return soma;
}"""

C_SOMA_PARCIAL = """\
int soma_ate_n(int n) {
    // Começa em 2 gerando off-by-one
    int soma = 0;
    for (int i = 2; i <= n; i++) {
        soma += i;
    }
    return soma;
}"""

C_PAR_CORRETO = """\
int e_par(int n) {
    return (n % 2 == 0) ? 1 : 0;
}"""

C_PAR_FALHA_ZERO = """\
int e_par(int n) {
    // Trata 0 erroneamente como ímpar
    if (n == 0) return 0;
    return (n % 2 == 0) ? 1 : 0;
}"""

C_PAR_ERRO_SINTAXE = """\
int e_par(int n) {
    if (n % 2 == 0)
        return 1
    return 0;
}"""

C_MAIOR3_CORRETO = """\
int maior_de_tres(int a, int b, int c) {
    int maior = a;
    if (b > maior) maior = b;
    if (c > maior) maior = c;
    return maior;
}"""

C_POT_CORRETO = """\
int potencia(int base, int exp) {
    int res = 1;
    for (int i = 0; i < exp; i++) {
        res *= base;
    }
    return res;
}"""

C_MEDIA_CORRETO = """\
float media_array(int v[], int n) {
    float soma = 0.0f;
    for (int i = 0; i < n; i++) {
        soma += v[i];
    }
    return soma / n;
}"""

C_MEDIA_DIVISAO_INT = """\
float media_array(int v[], int n) {
    // Erro comum: divisão inteira antes do cast para float
    int soma = 0;
    for (int i = 0; i < n; i++) {
        soma += v[i];
    }
    return soma / n;
}"""

C_MAXEL_CORRETO = """\
int maior_elemento(int v[], int n) {
    int maior = v[0];
    for (int i = 1; i < n; i++) {
        if (v[i] > maior) maior = v[i];
    }
    return maior;
}"""

C_FATORIAL_CORRETO = """\
int fatorial(int n) {
    if (n <= 1) return 1;
    return n * fatorial(n - 1);
}"""


def build_resultado_avaliado(casos: list[dict], nota: float, pontos_max: float) -> dict:
    total = len(casos)
    passados = sum(1 for c in casos if c.get("status") == "PASS")
    return {
        "nota": nota,
        "pontosMaximo": pontos_max,
        "totalCasos": total,
        "casosPassados": passados,
        "tempoMs": 35,
        "memoriaKb": 620,
        "erroCompilacao": None,
        "erroExecucao": None,
        "casos": casos,
    }


def build_resultado_erro(stderr: str) -> dict:
    return {
        "nota": 0.0,
        "pontosMaximo": 0.0,
        "totalCasos": 0,
        "casosPassados": 0,
        "tempoMs": 0,
        "memoriaKb": 0,
        "erroCompilacao": stderr,
        "erroExecucao": None,
        "casos": [],
    }


# ─────────────────────────────────────────────
# ETAPAS DO SEED
# ─────────────────────────────────────────────

async def limpar_banco(session):
    """Limpa todas as tabelas do projeto garantindo integridade de FKs."""
    print("[1/8] Limpando dados do banco...")
    try:
        await session.execute(text(
            "TRUNCATE TABLE entregas_atividades, submissoes, "
            "atividades_funcoes_casos_teste, atividades_funcoes, "
            "casos_teste, funcoes, atividades, usuarios "
            "RESTART IDENTITY CASCADE;"
        ))
        await session.commit()
    except Exception:
        await session.rollback()
        # Fallback para DELETE ordenado caso TRUNCATE CASCADE não seja suportado/permitido
        await session.execute(text("DELETE FROM entregas_atividades;"))
        await session.execute(text("DELETE FROM submissoes;"))
        await session.execute(text("DELETE FROM atividades_funcoes_casos_teste;"))
        await session.execute(text("DELETE FROM atividades_funcoes;"))
        await session.execute(text("DELETE FROM casos_teste;"))
        await session.execute(text("DELETE FROM funcoes;"))
        await session.execute(text("DELETE FROM atividades;"))
        await session.execute(text("DELETE FROM usuarios;"))
        await session.commit()

    print("      [ok] Banco limpo com sucesso.\n")


async def seed_usuarios(session):
    """Insere professores e alunos com senha padrão '123456'."""
    print("[2/8] Inserindo usuarios...")
    SENHA_HASH = get_password_hash("123456")

    usuarios = [
        # Professores
        Usuario(
            uuid=U_PROF_ANA,
            nome="Profa. Dra. Ana Souza",
            email="ana.souza@universidade.br",
            matricula="DOC-1001",
            tipo="professor",
            senha_hash=SENHA_HASH,
        ),
        Usuario(
            uuid=U_PROF_CARLOS,
            nome="Prof. Dr. Carlos Menezes",
            email="carlos.menezes@universidade.br",
            matricula="DOC-1002",
            tipo="professor",
            senha_hash=SENHA_HASH,
        ),
        # Alunos
        Usuario(
            uuid=U_ALUNO_PEDRO,
            nome="Pedro Lacerda",
            email="pedro.lacerda@aluno.universidade.br",
            matricula="20231001",
            tipo="aluno",
            senha_hash=SENHA_HASH,
        ),
        Usuario(
            uuid=U_ALUNO_JOAO,
            nome="João Silva",
            email="joao.silva@aluno.universidade.br",
            matricula="20231002",
            tipo="aluno",
            senha_hash=SENHA_HASH,
        ),
        Usuario(
            uuid=U_ALUNO_BEA,
            nome="Beatriz Lima",
            email="beatriz.lima@aluno.universidade.br",
            matricula="20231003",
            tipo="aluno",
            senha_hash=SENHA_HASH,
        ),
        Usuario(
            uuid=U_ALUNO_LUCAS,
            nome="Lucas Fernandes",
            email="lucas.fernandes@aluno.universidade.br",
            matricula="20231004",
            tipo="aluno",
            senha_hash=SENHA_HASH,
        ),
    ]
    session.add_all(usuarios)
    await session.commit()
    print(f"      [ok] {len(usuarios)} usuarios inseridos (2 professores, 4 alunos).\n")


async def seed_funcoes_biblioteca(session):
    """Insere o catálogo de funções C na Biblioteca Central (independente de atividades)."""
    print("[3/8] Inserindo funcoes na Biblioteca Central...")
    funcoes = [
        Funcao(
            uuid=F_SOMA,
            nome_funcao="soma_ate_n",
            dificuldade_padrao="facil",
            descricao="Recebe um inteiro positivo n e calcula a soma de todos os números de 1 até n (1 + 2 + ... + n).",
            parametros=[{"nome": "n", "tipo": "int", "descricao": "Limite superior positivo"}],
            retorno={"tipo": "int", "descricao": "Soma acumulada de 1 até n"},
            max_tentativas=5,
            dicas=[
                "Utilize um laço de repetição (for ou while).",
                "Inicialize a variável acumuladora com 0 antes do laço.",
                "Cuidado para incluir o próprio n na soma (i <= n).",
            ],
        ),
        Funcao(
            uuid=F_PAR,
            nome_funcao="e_par",
            dificuldade_padrao="facil",
            descricao="Verifica se um número inteiro n é par. Retorna 1 se for par e 0 se for ímpar.",
            parametros=[{"nome": "n", "tipo": "int", "descricao": "Número inteiro"}],
            retorno={"tipo": "int", "descricao": "1 se par, 0 se ímpar"},
            max_tentativas=3,
            dicas=[
                "O operador de resto da divisão em C é %.",
                "Lembre-se que zero também é um número par.",
            ],
        ),
        Funcao(
            uuid=F_MAIOR3,
            nome_funcao="maior_de_tres",
            dificuldade_padrao="facil",
            descricao="Recebe três números inteiros e retorna o maior valor entre eles.",
            parametros=[
                {"nome": "a", "tipo": "int"},
                {"nome": "b", "tipo": "int"},
                {"nome": "c", "tipo": "int"},
            ],
            retorno={"tipo": "int", "descricao": "Maior elemento entre a, b e c"},
            max_tentativas=5,
            dicas=[
                "Assuma inicialmente que 'a' é o maior.",
                "Compare em seguida com 'b' e depois com 'c', atualizando se necessário.",
            ],
        ),
        Funcao(
            uuid=F_POT,
            nome_funcao="potencia",
            dificuldade_padrao="facil",
            descricao="Calcula a potência de uma base inteira elevada a um expoente inteiro não-negativo (base^exp).",
            parametros=[
                {"nome": "base", "tipo": "int", "descricao": "Base da exponenciação"},
                {"nome": "exp", "tipo": "int", "descricao": "Expoente (exp >= 0)"},
            ],
            retorno={"tipo": "int", "descricao": "Resultado da potência"},
            max_tentativas=5,
            dicas=["Qualquer número elevado a zero resulta em 1."],
        ),
        Funcao(
            uuid=F_FAT,
            nome_funcao="fatorial",
            dificuldade_padrao="facil",
            descricao="Calcula o fatorial de um inteiro não-negativo n (n!). Considere 0! = 1.",
            parametros=[{"nome": "n", "tipo": "int", "descricao": "Inteiro não-negativo"}],
            retorno={"tipo": "int", "descricao": "Resultado de n!"},
            max_tentativas=5,
            dicas=[
                "Pode ser resolvido com recursão simples ou com um loop for.",
                "Não esqueça que 0! = 1.",
            ],
        ),
        Funcao(
            uuid=F_MEDIA,
            nome_funcao="media_array",
            dificuldade_padrao="medio",
            descricao="Recebe um vetor de inteiros v e o seu tamanho n, retornando a média aritmética em ponto flutuante (float).",
            parametros=[
                {"nome": "v", "tipo": "int[]", "descricao": "Vetor de inteiros"},
                {"nome": "n", "tipo": "int", "descricao": "Tamanho do vetor (n > 0)"},
            ],
            retorno={"tipo": "float", "descricao": "Média aritmética dos elementos"},
            max_tentativas=5,
            dicas=[
                "Cuidado com a divisão inteira em C: faça cast ou declare o acumulador como float.",
            ],
        ),
        Funcao(
            uuid=F_MAXEL,
            nome_funcao="maior_elemento",
            dificuldade_padrao="medio",
            descricao="Encontra e retorna o maior valor dentro de um vetor de inteiros de tamanho n (n >= 1).",
            parametros=[
                {"nome": "v", "tipo": "int[]", "descricao": "Vetor de inteiros"},
                {"nome": "n", "tipo": "int", "descricao": "Tamanho do vetor"},
            ],
            retorno={"tipo": "int", "descricao": "Maior elemento encontrado"},
            max_tentativas=5,
            dicas=["Inicialize a variável de maior valor com o primeiro elemento v[0]."],
        ),
        Funcao(
            uuid=F_CONTAR,
            nome_funcao="contar_ocorrencias",
            dificuldade_padrao="medio",
            descricao="Conta quantas vezes um determinado valor 'alvo' ocorre dentro de um vetor de inteiros de tamanho n.",
            parametros=[
                {"nome": "v", "tipo": "int[]", "descricao": "Vetor de inteiros"},
                {"nome": "n", "tipo": "int", "descricao": "Tamanho do vetor"},
                {"nome": "alvo", "tipo": "int", "descricao": "Valor a ser contabilizado"},
            ],
            retorno={"tipo": "int", "descricao": "Número de ocorrências do alvo no vetor"},
            max_tentativas=5,
            dicas=["Percorra o vetor comparando cada v[i] com alvo e incremente um contador."],
        ),
        Funcao(
            uuid=F_FIB,
            nome_funcao="fibonacci_n",
            dificuldade_padrao="medio",
            descricao="Retorna o n-ésimo termo da sequência de Fibonacci (Fib(0)=0, Fib(1)=1, Fib(2)=1, Fib(3)=2, ...).",
            parametros=[{"nome": "n", "tipo": "int", "descricao": "Índice do termo (n >= 0)"}],
            retorno={"tipo": "int", "descricao": "Valor do termo n da sequência"},
            max_tentativas=3,
            dicas=[
                "Os dois primeiros termos são base: n=0 -> 0, n=1 -> 1.",
                "Uma abordagem iterativa é mais eficiente que a recursiva simples.",
            ],
        ),
        Funcao(
            uuid=F_MDC,
            nome_funcao="mdc",
            dificuldade_padrao="medio",
            descricao="Calcula o Máximo Divisor Comum (MDC) entre dois inteiros positivos utilizando o Algoritmo de Euclides.",
            parametros=[
                {"nome": "a", "tipo": "int", "descricao": "Primeiro inteiro positivo"},
                {"nome": "b", "tipo": "int", "descricao": "Segundo inteiro positivo"},
            ],
            retorno={"tipo": "int", "descricao": "MDC de a e b"},
            max_tentativas=5,
            dicas=["Enquanto b != 0, faça o resto temp = a % b; a = b; b = temp;"],
        ),
    ]
    session.add_all(funcoes)
    await session.commit()
    print(f"      [ok] {len(funcoes)} funcoes inseridas na Biblioteca Central.\n")


async def seed_casos_teste(session):
    """Insere casos de teste canônicos para cada função na biblioteca."""
    print("[4/8] Inserindo casos de teste canonicos...")
    casos = [
        # soma_ate_n
        CasoTeste(uuid="d1010000-0000-0000-0000-000000000001", funcao_uuid=F_SOMA, numero=1,
                  inputs={"n": 1}, output_esperado={"valor": 1}, descricao="n=1 (caso base mínimo)"),
        CasoTeste(uuid="d1010000-0000-0000-0000-000000000002", funcao_uuid=F_SOMA, numero=2,
                  inputs={"n": 4}, output_esperado={"valor": 10}, descricao="n=4 (1+2+3+4=10)"),
        CasoTeste(uuid="d1010000-0000-0000-0000-000000000003", funcao_uuid=F_SOMA, numero=3,
                  inputs={"n": 10}, output_esperado={"valor": 55}, descricao="n=10 (soma de Gauss = 55)"),
        CasoTeste(uuid="d1010000-0000-0000-0000-000000000004", funcao_uuid=F_SOMA, numero=4,
                  inputs={"n": 50}, output_esperado={"valor": 1275}, descricao="n=50 (caso de estresse médio)"),

        # e_par
        CasoTeste(uuid="d1020000-0000-0000-0000-000000000001", funcao_uuid=F_PAR, numero=1,
                  inputs={"n": 2}, output_esperado={"valor": 1}, descricao="2 é par"),
        CasoTeste(uuid="d1020000-0000-0000-0000-000000000002", funcao_uuid=F_PAR, numero=2,
                  inputs={"n": 7}, output_esperado={"valor": 0}, descricao="7 é ímpar"),
        CasoTeste(uuid="d1020000-0000-0000-0000-000000000003", funcao_uuid=F_PAR, numero=3,
                  inputs={"n": 0}, output_esperado={"valor": 1}, descricao="0 é par (caso de borda)"),
        CasoTeste(uuid="d1020000-0000-0000-0000-000000000004", funcao_uuid=F_PAR, numero=4,
                  inputs={"n": -4}, output_esperado={"valor": 1}, descricao="-4 é par (número negativo)"),

        # maior_de_tres
        CasoTeste(uuid="d1030000-0000-0000-0000-000000000001", funcao_uuid=F_MAIOR3, numero=1,
                  inputs={"a": 3, "b": 7, "c": 5}, output_esperado={"valor": 7}, descricao="Maior no meio (b)"),
        CasoTeste(uuid="d1030000-0000-0000-0000-000000000002", funcao_uuid=F_MAIOR3, numero=2,
                  inputs={"a": 10, "b": 10, "c": 4}, output_esperado={"valor": 10}, descricao="Empate entre a e b"),
        CasoTeste(uuid="d1030000-0000-0000-0000-000000000003", funcao_uuid=F_MAIOR3, numero=3,
                  inputs={"a": -8, "b": -3, "c": -12}, output_esperado={"valor": -3}, descricao="Todos negativos"),
        CasoTeste(uuid="d1030000-0000-0000-0000-000000000004", funcao_uuid=F_MAIOR3, numero=4,
                  inputs={"a": 42, "b": 42, "c": 42}, output_esperado={"valor": 42}, descricao="Todos iguais"),

        # potencia
        CasoTeste(uuid="d1040000-0000-0000-0000-000000000001", funcao_uuid=F_POT, numero=1,
                  inputs={"base": 2, "exp": 3}, output_esperado={"valor": 8}, descricao="2^3 = 8"),
        CasoTeste(uuid="d1040000-0000-0000-0000-000000000002", funcao_uuid=F_POT, numero=2,
                  inputs={"base": 5, "exp": 0}, output_esperado={"valor": 1}, descricao="5^0 = 1 (expoente zero)"),
        CasoTeste(uuid="d1040000-0000-0000-0000-000000000003", funcao_uuid=F_POT, numero=3,
                  inputs={"base": 3, "exp": 4}, output_esperado={"valor": 81}, descricao="3^4 = 81"),

        # fatorial
        CasoTeste(uuid="d1050000-0000-0000-0000-000000000001", funcao_uuid=F_FAT, numero=1,
                  inputs={"n": 0}, output_esperado={"valor": 1}, descricao="0! = 1"),
        CasoTeste(uuid="d1050000-0000-0000-0000-000000000002", funcao_uuid=F_FAT, numero=2,
                  inputs={"n": 1}, output_esperado={"valor": 1}, descricao="1! = 1"),
        CasoTeste(uuid="d1050000-0000-0000-0000-000000000003", funcao_uuid=F_FAT, numero=3,
                  inputs={"n": 5}, output_esperado={"valor": 120}, descricao="5! = 120"),
        CasoTeste(uuid="d1050000-0000-0000-0000-000000000004", funcao_uuid=F_FAT, numero=4,
                  inputs={"n": 7}, output_esperado={"valor": 5040}, descricao="7! = 5040"),

        # media_array
        CasoTeste(uuid="d1060000-0000-0000-0000-000000000001", funcao_uuid=F_MEDIA, numero=1,
                  inputs={"v": [2, 4, 6], "n": 3}, output_esperado={"valor": 4.0}, descricao="Média de [2, 4, 6] = 4.0"),
        CasoTeste(uuid="d1060000-0000-0000-0000-000000000002", funcao_uuid=F_MEDIA, numero=2,
                  inputs={"v": [1, 2, 3, 4, 5], "n": 5}, output_esperado={"valor": 3.0}, descricao="Média de [1..5] = 3.0"),
        CasoTeste(uuid="d1060000-0000-0000-0000-000000000003", funcao_uuid=F_MEDIA, numero=3,
                  inputs={"v": [10, 15], "n": 2}, output_esperado={"valor": 12.5}, descricao="Média decimal 12.5"),

        # maior_elemento
        CasoTeste(uuid="d1070000-0000-0000-0000-000000000001", funcao_uuid=F_MAXEL, numero=1,
                  inputs={"v": [3, 9, 1, 7, 2], "n": 5}, output_esperado={"valor": 9}, descricao="Maior elemento = 9"),
        CasoTeste(uuid="d1070000-0000-0000-0000-000000000002", funcao_uuid=F_MAXEL, numero=2,
                  inputs={"v": [-5, -1, -9], "n": 3}, output_esperado={"valor": -1}, descricao="Negativos: maior = -1"),
        CasoTeste(uuid="d1070000-0000-0000-0000-000000000003", funcao_uuid=F_MAXEL, numero=3,
                  inputs={"v": [4, 4, 4], "n": 3}, output_esperado={"valor": 4}, descricao="Todos iguais"),

        # contar_ocorrencias
        CasoTeste(uuid="d1080000-0000-0000-0000-000000000001", funcao_uuid=F_CONTAR, numero=1,
                  inputs={"v": [1, 2, 3, 2, 2, 4], "n": 6, "alvo": 2}, output_esperado={"valor": 3}, descricao="O elemento 2 aparece 3 vezes"),
        CasoTeste(uuid="d1080000-0000-0000-0000-000000000002", funcao_uuid=F_CONTAR, numero=2,
                  inputs={"v": [5, 6, 7], "n": 3, "alvo": 9}, output_esperado={"valor": 0}, descricao="Elemento não presente no vetor"),
        CasoTeste(uuid="d1080000-0000-0000-0000-000000000003", funcao_uuid=F_CONTAR, numero=3,
                  inputs={"v": [8, 8, 8, 8], "n": 4, "alvo": 8}, output_esperado={"valor": 4}, descricao="Todos os elementos são o alvo"),

        # fibonacci_n
        CasoTeste(uuid="d1090000-0000-0000-0000-000000000001", funcao_uuid=F_FIB, numero=1,
                  inputs={"n": 0}, output_esperado={"valor": 0}, descricao="Fib(0) = 0"),
        CasoTeste(uuid="d1090000-0000-0000-0000-000000000002", funcao_uuid=F_FIB, numero=2,
                  inputs={"n": 1}, output_esperado={"valor": 1}, descricao="Fib(1) = 1"),
        CasoTeste(uuid="d1090000-0000-0000-0000-000000000003", funcao_uuid=F_FIB, numero=3,
                  inputs={"n": 6}, output_esperado={"valor": 8}, descricao="Fib(6) = 8"),
        CasoTeste(uuid="d1090000-0000-0000-0000-000000000004", funcao_uuid=F_FIB, numero=4,
                  inputs={"n": 9}, output_esperado={"valor": 34}, descricao="Fib(9) = 34"),

        # mdc
        CasoTeste(uuid="d1100000-0000-0000-0000-000000000001", funcao_uuid=F_MDC, numero=1,
                  inputs={"a": 48, "b": 18}, output_esperado={"valor": 6}, descricao="MDC(48, 18) = 6"),
        CasoTeste(uuid="d1100000-0000-0000-0000-000000000002", funcao_uuid=F_MDC, numero=2,
                  inputs={"a": 101, "b": 103}, output_esperado={"valor": 1}, descricao="MDC(101, 103) = 1 (primos entre si)"),
        CasoTeste(uuid="d1100000-0000-0000-0000-000000000003", funcao_uuid=F_MDC, numero=3,
                  inputs={"a": 20, "b": 5}, output_esperado={"valor": 5}, descricao="MDC(20, 5) = 5"),
    ]
    session.add_all(casos)
    await session.commit()
    print(f"      [ok] {len(casos)} casos de teste canonicos inseridos.\n")


async def seed_atividades(session):
    """Insere atividades curriculares com diferentes perfis e configurações."""
    print("[5/8] Inserindo atividades...")
    atividades = [
        Atividade(
            uuid=ATV_001,
            professor_uuid=U_PROF_ANA,
            titulo="Lista 1 – Sintaxe Básica, Laços e Condicionais",
            descricao="Primeira lista prática de programação em C. Exercícios fundamentais sobre loops, paridade e condicionais.",
            pontuacao_maxima=100.0,
            data_abertura=now - timedelta(days=7),
            data_fechamento=now + timedelta(days=14),
            status="publicado",
            tipo="exercicio",
            notas_liberadas=True,
            bloquear_paste=False,
        ),
        Atividade(
            uuid=ATV_002,
            professor_uuid=U_PROF_ANA,
            titulo="Lista 2 – Vetores e Manipulação de Dados em C",
            descricao="Atividade com foco em alocação estática, cálculo de médias e busca em arrays unidimensionais.",
            pontuacao_maxima=100.0,
            data_abertura=now - timedelta(days=2),
            data_fechamento=now + timedelta(days=10),
            status="publicado",
            tipo="exercicio",
            notas_liberadas=True,
            bloquear_paste=False,
        ),
        Atividade(
            uuid=ATV_003,
            professor_uuid=U_PROF_ANA,
            titulo="Prova 1 – Avaliação Parcial de Algoritmos",
            descricao="Primeira avaliação individual da disciplina. Tempo cronometrado e restrição de área de transferência ativa.",
            pontuacao_maxima=100.0,
            data_abertura=now - timedelta(hours=1),
            data_fechamento=now + timedelta(hours=2),
            status="publicado",
            tipo="prova",
            duracao_minutos=90,
            bloquear_paste=True,
            notas_liberadas=False,
        ),
        Atividade(
            uuid=ATV_004,
            professor_uuid=U_PROF_CARLOS,
            titulo="Lista 3 – Divisão e Conquista e Recursão (Em Elaboração)",
            descricao="Rascunho de atividade com foco em algoritmos euclidianos e sequências numéricas.",
            pontuacao_maxima=100.0,
            data_abertura=None,
            data_fechamento=None,
            status="rascunho",
            tipo="exercicio",
            notas_liberadas=False,
            bloquear_paste=False,
        ),
    ]
    session.add_all(atividades)
    await session.commit()
    print(f"      [ok] {len(atividades)} atividades inseridas.\n")


async def seed_associacoes_atividades_funcoes(session):
    """
    Associa funções da biblioteca às atividades com parâmetros contextuais (RN07):
    - peso (pontuação)
    - dificuldade contextual
    - ordem de exibição
    - visibilidade dos casos de teste (públicos vs ocultos, RN15)
    """
    print("[6/8] Vinculando funcoes as atividades e configurando casos contextuais...")

    # Mapas de UUIDs para casos de teste de cada função
    # Atividade 1: Lista 1 (4 funções de 25 pontos cada = 100 pontos)
    af_1_soma = AtividadeFuncao(
        uuid="e0100000-0000-0000-0000-000000000001",
        atividade_uuid=ATV_001, funcao_uuid=F_SOMA, dificuldade="facil", peso=25.0, ordem=0
    )
    af_1_par = AtividadeFuncao(
        uuid="e0100000-0000-0000-0000-000000000002",
        atividade_uuid=ATV_001, funcao_uuid=F_PAR, dificuldade="facil", peso=25.0, ordem=1
    )
    af_1_maior = AtividadeFuncao(
        uuid="e0100000-0000-0000-0000-000000000003",
        atividade_uuid=ATV_001, funcao_uuid=F_MAIOR3, dificuldade="facil", peso=25.0, ordem=2
    )
    af_1_pot = AtividadeFuncao(
        uuid="e0100000-0000-0000-0000-000000000004",
        atividade_uuid=ATV_001, funcao_uuid=F_POT, dificuldade="facil", peso=25.0, ordem=3
    )

    # Atividade 2: Lista 2 (3 funções: 30 + 35 + 35 = 100 pontos)
    af_2_media = AtividadeFuncao(
        uuid="e0200000-0000-0000-0000-000000000001",
        atividade_uuid=ATV_002, funcao_uuid=F_MEDIA, dificuldade="medio", peso=30.0, ordem=0
    )
    af_2_maxel = AtividadeFuncao(
        uuid="e0200000-0000-0000-0000-000000000002",
        atividade_uuid=ATV_002, funcao_uuid=F_MAXEL, dificuldade="medio", peso=35.0, ordem=1
    )
    af_2_contar = AtividadeFuncao(
        uuid="e0200000-0000-0000-0000-000000000003",
        atividade_uuid=ATV_002, funcao_uuid=F_CONTAR, dificuldade="medio", peso=35.0, ordem=2
    )

    # Atividade 3: Prova 1 (2 funções: 40 + 60 = 100 pontos)
    af_3_fat = AtividadeFuncao(
        uuid="e0300000-0000-0000-0000-000000000001",
        atividade_uuid=ATV_003, funcao_uuid=F_FAT, dificuldade="medio", peso=40.0, ordem=0
    )
    af_3_fib = AtividadeFuncao(
        uuid="e0300000-0000-0000-0000-000000000002",
        atividade_uuid=ATV_003, funcao_uuid=F_FIB, dificuldade="medio", peso=60.0, ordem=1
    )

    # Atividade 4: Rascunho (50 + 50 = 100 pontos)
    af_4_mdc = AtividadeFuncao(
        uuid="e0400000-0000-0000-0000-000000000001",
        atividade_uuid=ATV_004, funcao_uuid=F_MDC, dificuldade="medio", peso=50.0, ordem=0
    )
    af_4_fib = AtividadeFuncao(
        uuid="e0400000-0000-0000-0000-000000000002",
        atividade_uuid=ATV_004, funcao_uuid=F_FIB, dificuldade="dificil", peso=50.0, ordem=1
    )

    associacoes = [
        af_1_soma, af_1_par, af_1_maior, af_1_pot,
        af_2_media, af_2_maxel, af_2_contar,
        af_3_fat, af_3_fib,
        af_4_mdc, af_4_fib,
    ]
    session.add_all(associacoes)
    await session.flush()

    # Configuração contextual de casos de teste (visível vs oculto)
    casos_contexto = [
        # Atividade 1 - soma_ate_n (3 visíveis, 1 oculto)
        AtividadeFuncaoCasoTeste(atividade_funcao_uuid=af_1_soma.uuid, caso_teste_uuid="d1010000-0000-0000-0000-000000000001", oculto=False),
        AtividadeFuncaoCasoTeste(atividade_funcao_uuid=af_1_soma.uuid, caso_teste_uuid="d1010000-0000-0000-0000-000000000002", oculto=False),
        AtividadeFuncaoCasoTeste(atividade_funcao_uuid=af_1_soma.uuid, caso_teste_uuid="d1010000-0000-0000-0000-000000000003", oculto=False),
        AtividadeFuncaoCasoTeste(atividade_funcao_uuid=af_1_soma.uuid, caso_teste_uuid="d1010000-0000-0000-0000-000000000004", oculto=True),

        # Atividade 1 - e_par (3 visíveis, 1 oculto)
        AtividadeFuncaoCasoTeste(atividade_funcao_uuid=af_1_par.uuid, caso_teste_uuid="d1020000-0000-0000-0000-000000000001", oculto=False),
        AtividadeFuncaoCasoTeste(atividade_funcao_uuid=af_1_par.uuid, caso_teste_uuid="d1020000-0000-0000-0000-000000000002", oculto=False),
        AtividadeFuncaoCasoTeste(atividade_funcao_uuid=af_1_par.uuid, caso_teste_uuid="d1020000-0000-0000-0000-000000000003", oculto=False),
        AtividadeFuncaoCasoTeste(atividade_funcao_uuid=af_1_par.uuid, caso_teste_uuid="d1020000-0000-0000-0000-000000000004", oculto=True),

        # Atividade 1 - maior_de_tres (3 visíveis, 1 oculto)
        AtividadeFuncaoCasoTeste(atividade_funcao_uuid=af_1_maior.uuid, caso_teste_uuid="d1030000-0000-0000-0000-000000000001", oculto=False),
        AtividadeFuncaoCasoTeste(atividade_funcao_uuid=af_1_maior.uuid, caso_teste_uuid="d1030000-0000-0000-0000-000000000002", oculto=False),
        AtividadeFuncaoCasoTeste(atividade_funcao_uuid=af_1_maior.uuid, caso_teste_uuid="d1030000-0000-0000-0000-000000000003", oculto=False),
        AtividadeFuncaoCasoTeste(atividade_funcao_uuid=af_1_maior.uuid, caso_teste_uuid="d1030000-0000-0000-0000-000000000004", oculto=True),

        # Atividade 1 - potencia (2 visíveis, 1 oculto)
        AtividadeFuncaoCasoTeste(atividade_funcao_uuid=af_1_pot.uuid, caso_teste_uuid="d1040000-0000-0000-0000-000000000001", oculto=False),
        AtividadeFuncaoCasoTeste(atividade_funcao_uuid=af_1_pot.uuid, caso_teste_uuid="d1040000-0000-0000-0000-000000000002", oculto=False),
        AtividadeFuncaoCasoTeste(atividade_funcao_uuid=af_1_pot.uuid, caso_teste_uuid="d1040000-0000-0000-0000-000000000003", oculto=True),

        # Atividade 2 - media_array (2 visíveis, 1 oculto)
        AtividadeFuncaoCasoTeste(atividade_funcao_uuid=af_2_media.uuid, caso_teste_uuid="d1060000-0000-0000-0000-000000000001", oculto=False),
        AtividadeFuncaoCasoTeste(atividade_funcao_uuid=af_2_media.uuid, caso_teste_uuid="d1060000-0000-0000-0000-000000000002", oculto=False),
        AtividadeFuncaoCasoTeste(atividade_funcao_uuid=af_2_media.uuid, caso_teste_uuid="d1060000-0000-0000-0000-000000000003", oculto=True),

        # Atividade 2 - maior_elemento (2 visíveis, 1 oculto)
        AtividadeFuncaoCasoTeste(atividade_funcao_uuid=af_2_maxel.uuid, caso_teste_uuid="d1070000-0000-0000-0000-000000000001", oculto=False),
        AtividadeFuncaoCasoTeste(atividade_funcao_uuid=af_2_maxel.uuid, caso_teste_uuid="d1070000-0000-0000-0000-000000000002", oculto=False),
        AtividadeFuncaoCasoTeste(atividade_funcao_uuid=af_2_maxel.uuid, caso_teste_uuid="d1070000-0000-0000-0000-000000000003", oculto=True),

        # Atividade 2 - contar_ocorrencias (2 visíveis, 1 oculto)
        AtividadeFuncaoCasoTeste(atividade_funcao_uuid=af_2_contar.uuid, caso_teste_uuid="d1080000-0000-0000-0000-000000000001", oculto=False),
        AtividadeFuncaoCasoTeste(atividade_funcao_uuid=af_2_contar.uuid, caso_teste_uuid="d1080000-0000-0000-0000-000000000002", oculto=False),
        AtividadeFuncaoCasoTeste(atividade_funcao_uuid=af_2_contar.uuid, caso_teste_uuid="d1080000-0000-0000-0000-000000000003", oculto=True),

        # Atividade 3 (Prova) - fatorial (2 visíveis, 2 ocultos para prova)
        AtividadeFuncaoCasoTeste(atividade_funcao_uuid=af_3_fat.uuid, caso_teste_uuid="d1050000-0000-0000-0000-000000000001", oculto=False),
        AtividadeFuncaoCasoTeste(atividade_funcao_uuid=af_3_fat.uuid, caso_teste_uuid="d1050000-0000-0000-0000-000000000002", oculto=False),
        AtividadeFuncaoCasoTeste(atividade_funcao_uuid=af_3_fat.uuid, caso_teste_uuid="d1050000-0000-0000-0000-000000000003", oculto=True),
        AtividadeFuncaoCasoTeste(atividade_funcao_uuid=af_3_fat.uuid, caso_teste_uuid="d1050000-0000-0000-0000-000000000004", oculto=True),

        # Atividade 3 (Prova) - fibonacci_n (2 visíveis, 2 ocultos)
        AtividadeFuncaoCasoTeste(atividade_funcao_uuid=af_3_fib.uuid, caso_teste_uuid="d1090000-0000-0000-0000-000000000001", oculto=False),
        AtividadeFuncaoCasoTeste(atividade_funcao_uuid=af_3_fib.uuid, caso_teste_uuid="d1090000-0000-0000-0000-000000000002", oculto=False),
        AtividadeFuncaoCasoTeste(atividade_funcao_uuid=af_3_fib.uuid, caso_teste_uuid="d1090000-0000-0000-0000-000000000003", oculto=True),
        AtividadeFuncaoCasoTeste(atividade_funcao_uuid=af_3_fib.uuid, caso_teste_uuid="d1090000-0000-0000-0000-000000000004", oculto=True),
    ]
    session.add_all(casos_contexto)
    await session.commit()
    print(f"      [ok] {len(associacoes)} associacoes N:N e {len(casos_contexto)} configuracoes contextuais de casos salvas.\n")


async def seed_submissoes_e_entregas(session):
    """
    Insere submissões realistas com histórico de tentativas preservado e
    entregas finais consolidadas (RN12 e RN14).
    """
    print("[7/8] Inserindo submissoes de alunos e entregas finais...")

    submissoes = [
        # ══════════════════════════════════════════════════════════════════
        # 1. PEDRO LACERDA — LISTA 1 (Completou 100% das 4 funções)
        # ══════════════════════════════════════════════════════════════════
        # 1.1 soma_ate_n (Tentativa 1 - 25/25)
        Submissao(
            uuid="f1000000-0000-0000-0000-000000000001",
            atividade_uuid=ATV_001,
            funcao_uuid=F_SOMA,
            aluno_uuid=U_ALUNO_PEDRO,
            codigo_submetido=C_SOMA_CORRETO,
            data_submissao=now - timedelta(days=5, hours=3),
            tentativa_numero=1,
            status="avaliado",
            nota=25.0,
            resultado_json=build_resultado_avaliado(
                casos=[
                    {"numero": 1, "status": "PASS", "expected": 1, "got": 1},
                    {"numero": 2, "status": "PASS", "expected": 10, "got": 10},
                    {"numero": 3, "status": "PASS", "expected": 55, "got": 55},
                    {"numero": 4, "status": "PASS", "expected": 1275, "got": 1275},
                ],
                nota=25.0, pontos_max=25.0,
            ),
        ),
        # 1.2 e_par (Tentativa 1 - falha no zero, nota 18.75/25)
        Submissao(
            uuid="f1000000-0000-0000-0000-000000000002",
            atividade_uuid=ATV_001,
            funcao_uuid=F_PAR,
            aluno_uuid=U_ALUNO_PEDRO,
            codigo_submetido=C_PAR_FALHA_ZERO,
            data_submissao=now - timedelta(days=5, hours=2),
            tentativa_numero=1,
            status="avaliado",
            nota=18.75,
            resultado_json=build_resultado_avaliado(
                casos=[
                    {"numero": 1, "status": "PASS", "expected": 1, "got": 1},
                    {"numero": 2, "status": "PASS", "expected": 0, "got": 0},
                    {"numero": 3, "status": "FAIL", "expected": 1, "got": 0},
                    {"numero": 4, "status": "PASS", "expected": 1, "got": 1},
                ],
                nota=18.75, pontos_max=25.0,
            ),
        ),
        # 1.2 e_par (Tentativa 2 - corrigido, nota 25/25)
        Submissao(
            uuid="f1000000-0000-0000-0000-000000000003",
            atividade_uuid=ATV_001,
            funcao_uuid=F_PAR,
            aluno_uuid=U_ALUNO_PEDRO,
            codigo_submetido=C_PAR_CORRETO,
            data_submissao=now - timedelta(days=5, hours=1),
            tentativa_numero=2,
            status="avaliado",
            nota=25.0,
            resultado_json=build_resultado_avaliado(
                casos=[
                    {"numero": 1, "status": "PASS", "expected": 1, "got": 1},
                    {"numero": 2, "status": "PASS", "expected": 0, "got": 0},
                    {"numero": 3, "status": "PASS", "expected": 1, "got": 1},
                    {"numero": 4, "status": "PASS", "expected": 1, "got": 1},
                ],
                nota=25.0, pontos_max=25.0,
            ),
        ),
        # 1.3 maior_de_tres (Tentativa 1 - 25/25)
        Submissao(
            uuid="f1000000-0000-0000-0000-000000000004",
            atividade_uuid=ATV_001,
            funcao_uuid=F_MAIOR3,
            aluno_uuid=U_ALUNO_PEDRO,
            codigo_submetido=C_MAIOR3_CORRETO,
            data_submissao=now - timedelta(days=4, hours=5),
            tentativa_numero=1,
            status="avaliado",
            nota=25.0,
            resultado_json=build_resultado_avaliado(
                casos=[
                    {"numero": 1, "status": "PASS", "expected": 7, "got": 7},
                    {"numero": 2, "status": "PASS", "expected": 10, "got": 10},
                    {"numero": 3, "status": "PASS", "expected": -3, "got": -3},
                    {"numero": 4, "status": "PASS", "expected": 42, "got": 42},
                ],
                nota=25.0, pontos_max=25.0,
            ),
        ),
        # 1.4 potencia (Tentativa 1 - 25/25)
        Submissao(
            uuid="f1000000-0000-0000-0000-000000000005",
            atividade_uuid=ATV_001,
            funcao_uuid=F_POT,
            aluno_uuid=U_ALUNO_PEDRO,
            codigo_submetido=C_POT_CORRETO,
            data_submissao=now - timedelta(days=4, hours=4),
            tentativa_numero=1,
            status="avaliado",
            nota=25.0,
            resultado_json=build_resultado_avaliado(
                casos=[
                    {"numero": 1, "status": "PASS", "expected": 8, "got": 8},
                    {"numero": 2, "status": "PASS", "expected": 1, "got": 1},
                    {"numero": 3, "status": "PASS", "expected": 81, "got": 81},
                ],
                nota=25.0, pontos_max=25.0,
            ),
        ),

        # ══════════════════════════════════════════════════════════════════
        # 2. JOÃO SILVA — LISTA 1 (Em andamento: tentou 3 funções, 1 com erro)
        # ══════════════════════════════════════════════════════════════════
        # 2.1 soma_ate_n (Tentativa 1 - parcial, nota 18.75/25)
        Submissao(
            uuid="f2000000-0000-0000-0000-000000000001",
            atividade_uuid=ATV_001,
            funcao_uuid=F_SOMA,
            aluno_uuid=U_ALUNO_JOAO,
            codigo_submetido=C_SOMA_PARCIAL,
            data_submissao=now - timedelta(days=3, hours=2),
            tentativa_numero=1,
            status="avaliado",
            nota=18.75,
            resultado_json=build_resultado_avaliado(
                casos=[
                    {"numero": 1, "status": "FAIL", "expected": 1, "got": 0},
                    {"numero": 2, "status": "PASS", "expected": 10, "got": 9},
                    {"numero": 3, "status": "PASS", "expected": 55, "got": 54},
                    {"numero": 4, "status": "PASS", "expected": 1275, "got": 1274},
                ],
                nota=18.75, pontos_max=25.0,
            ),
        ),
        # 2.2 e_par (Tentativa 1 - Erro de Compilação por sintaxe)
        Submissao(
            uuid="f2000000-0000-0000-0000-000000000002",
            atividade_uuid=ATV_001,
            funcao_uuid=F_PAR,
            aluno_uuid=U_ALUNO_JOAO,
            codigo_submetido=C_PAR_ERRO_SINTAXE,
            data_submissao=now - timedelta(days=3, hours=1),
            tentativa_numero=1,
            status="erro",
            nota=0.0,
            resultado_json=build_resultado_erro(
                "main.c:4:17: error: expected ';' before 'return'\n"
                "         return 1\n"
                "                 ^\n"
                "                 ;\n"
                "     return 0;\n"
            ),
        ),
        # 2.3 maior_de_tres (Tentativa 1 - correta 25/25)
        Submissao(
            uuid="f2000000-0000-0000-0000-000000000003",
            atividade_uuid=ATV_001,
            funcao_uuid=F_MAIOR3,
            aluno_uuid=U_ALUNO_JOAO,
            codigo_submetido=C_MAIOR3_CORRETO,
            data_submissao=now - timedelta(days=2, hours=4),
            tentativa_numero=1,
            status="avaliado",
            nota=25.0,
            resultado_json=build_resultado_avaliado(
                casos=[
                    {"numero": 1, "status": "PASS", "expected": 7, "got": 7},
                    {"numero": 2, "status": "PASS", "expected": 10, "got": 10},
                    {"numero": 3, "status": "PASS", "expected": -3, "got": -3},
                    {"numero": 4, "status": "PASS", "expected": 42, "got": 42},
                ],
                nota=25.0, pontos_max=25.0,
            ),
        ),

        # ══════════════════════════════════════════════════════════════════
        # 3. BEATRIZ LIMA — LISTA 1 (Completou 100% com nota máxima)
        # ══════════════════════════════════════════════════════════════════
        Submissao(
            uuid="f3000000-0000-0000-0000-000000000001",
            atividade_uuid=ATV_001, funcao_uuid=F_SOMA, aluno_uuid=U_ALUNO_BEA,
            codigo_submetido=C_SOMA_CORRETO, data_submissao=now - timedelta(days=4),
            tentativa_numero=1, status="avaliado", nota=25.0,
            resultado_json=build_resultado_avaliado(
                casos=[{"numero": i, "status": "PASS"} for i in range(1, 5)],
                nota=25.0, pontos_max=25.0
            ),
        ),
        Submissao(
            uuid="f3000000-0000-0000-0000-000000000002",
            atividade_uuid=ATV_001, funcao_uuid=F_PAR, aluno_uuid=U_ALUNO_BEA,
            codigo_submetido=C_PAR_CORRETO, data_submissao=now - timedelta(days=4),
            tentativa_numero=1, status="avaliado", nota=25.0,
            resultado_json=build_resultado_avaliado(
                casos=[{"numero": i, "status": "PASS"} for i in range(1, 5)],
                nota=25.0, pontos_max=25.0
            ),
        ),
        Submissao(
            uuid="f3000000-0000-0000-0000-000000000003",
            atividade_uuid=ATV_001, funcao_uuid=F_MAIOR3, aluno_uuid=U_ALUNO_BEA,
            codigo_submetido=C_MAIOR3_CORRETO, data_submissao=now - timedelta(days=4),
            tentativa_numero=1, status="avaliado", nota=25.0,
            resultado_json=build_resultado_avaliado(
                casos=[{"numero": i, "status": "PASS"} for i in range(1, 5)],
                nota=25.0, pontos_max=25.0
            ),
        ),
        Submissao(
            uuid="f3000000-0000-0000-0000-000000000004",
            atividade_uuid=ATV_001, funcao_uuid=F_POT, aluno_uuid=U_ALUNO_BEA,
            codigo_submetido=C_POT_CORRETO, data_submissao=now - timedelta(days=4),
            tentativa_numero=1, status="avaliado", nota=25.0,
            resultado_json=build_resultado_avaliado(
                casos=[{"numero": i, "status": "PASS"} for i in range(1, 4)],
                nota=25.0, pontos_max=25.0
            ),
        ),

        # ══════════════════════════════════════════════════════════════════
        # 4. PEDRO LACERDA — LISTA 2 (Em andamento: 2 resolvidas, 1 pendente)
        # ══════════════════════════════════════════════════════════════════
        Submissao(
            uuid="f1000000-0000-0000-0000-000000000006",
            atividade_uuid=ATV_002, funcao_uuid=F_MEDIA, aluno_uuid=U_ALUNO_PEDRO,
            codigo_submetido=C_MEDIA_CORRETO, data_submissao=now - timedelta(hours=18),
            tentativa_numero=1, status="avaliado", nota=30.0,
            resultado_json=build_resultado_avaliado(
                casos=[
                    {"numero": 1, "status": "PASS", "expected": 4.0, "got": 4.0},
                    {"numero": 2, "status": "PASS", "expected": 3.0, "got": 3.0},
                    {"numero": 3, "status": "PASS", "expected": 12.5, "got": 12.5},
                ],
                nota=30.0, pontos_max=30.0,
            ),
        ),
        Submissao(
            uuid="f1000000-0000-0000-0000-000000000007",
            atividade_uuid=ATV_002, funcao_uuid=F_MAXEL, aluno_uuid=U_ALUNO_PEDRO,
            codigo_submetido=C_MAXEL_CORRETO, data_submissao=now - timedelta(hours=17),
            tentativa_numero=1, status="avaliado", nota=35.0,
            resultado_json=build_resultado_avaliado(
                casos=[
                    {"numero": 1, "status": "PASS", "expected": 9, "got": 9},
                    {"numero": 2, "status": "PASS", "expected": -1, "got": -1},
                    {"numero": 3, "status": "PASS", "expected": 4, "got": 4},
                ],
                nota=35.0, pontos_max=35.0,
            ),
        ),

        # ══════════════════════════════════════════════════════════════════
        # 5. PEDRO LACERDA — PROVA 1 (Tentou fatorial)
        # ══════════════════════════════════════════════════════════════════
        Submissao(
            uuid="f1000000-0000-0000-0000-000000000008",
            atividade_uuid=ATV_003, funcao_uuid=F_FAT, aluno_uuid=U_ALUNO_PEDRO,
            codigo_submetido=C_FATORIAL_CORRETO, data_submissao=now - timedelta(minutes=30),
            tentativa_numero=1, status="avaliado", nota=40.0,
            resultado_json=build_resultado_avaliado(
                casos=[
                    {"numero": 1, "status": "PASS", "expected": 1, "got": 1},
                    {"numero": 2, "status": "PASS", "expected": 1, "got": 1},
                    {"numero": 3, "status": "PASS", "expected": 120, "got": 120},
                    {"numero": 4, "status": "PASS", "expected": 5040, "got": 5040},
                ],
                nota=40.0, pontos_max=40.0,
            ),
        ),
    ]
    session.add_all(submissoes)
    await session.commit()

    # ══════════════════════════════════════════════════════════════════
    # ENTREGAS FINAIS DE ATIVIDADES (RN14)
    # Pedro e Beatriz entregaram formalmente a Lista 1 com nota 100.0.
    # João ainda está em andamento (sem EntregaAtividade).
    # ══════════════════════════════════════════════════════════════════
    entregas = [
        EntregaAtividade(
            uuid="g1000000-0000-0000-0000-000000000001",
            aluno_uuid=U_ALUNO_PEDRO,
            atividade_uuid=ATV_001,
            status="entregue",
            nota_final=100.0,
            data_entrega=now - timedelta(days=4, hours=3),
        ),
        EntregaAtividade(
            uuid="g1000000-0000-0000-0000-000000000002",
            aluno_uuid=U_ALUNO_BEA,
            atividade_uuid=ATV_001,
            status="entregue",
            nota_final=100.0,
            data_entrega=now - timedelta(days=3, hours=22),
        ),
    ]
    session.add_all(entregas)
    await session.commit()
    print(f"      [ok] {len(submissoes)} submissoes e {len(entregas)} entregas finais salvas com sucesso.\n")


# ─────────────────────────────────────────────
# FLUXO PRINCIPAL
# ─────────────────────────────────────────────

async def main():
    print("=" * 65)
    print("      CODELAB — SEED E POPULAÇÃO COMPLETA DO BANCO DE DADOS")
    print("=" * 65 + "\n")

    # 1. Garante que migrações e schema estejam 100% atualizados
    print("[0/8] Inicializando conexao e sincronizando schema via migrador...")
    await init_db()
    print("      [ok] Schema de banco sincronizado e validado.\n")

    # 2. Executa as etapas ordenadas
    async with async_session() as session:
        await limpar_banco(session)
        await seed_usuarios(session)
        await seed_funcoes_biblioteca(session)
        await seed_casos_teste(session)
        await seed_atividades(session)
        await seed_associacoes_atividades_funcoes(session)
        await seed_submissoes_e_entregas(session)

    print("=" * 65)
    print("  [SUCESSO] BASE DE DADOS RESETADA E POPULADA COM EXCELÊNCIA!")
    print("=" * 65)
    print()
    print("CONTAS PARA TESTE E LOGIN (Senha padrao: 123456):")
    print("  Docentes:")
    print("    - ana.souza@universidade.br       (Profa. Dra. Ana Souza)")
    print("    - carlos.menezes@universidade.br  (Prof. Dr. Carlos Menezes)")
    print("  Alunos:")
    print("    - pedro.lacerda@aluno.universidade.br  (Pedro Lacerda - Lista 1 Entregue 100, Lista 2 Em andamento)")
    print("    - joao.silva@aluno.universidade.br     (João Silva - Lista 1 Em andamento com submissoes parciais)")
    print("    - beatriz.lima@aluno.universidade.br   (Beatriz Lima - Lista 1 Entregue 100)")
    print("    - lucas.fernandes@aluno.universidade.br(Lucas Fernandes - Sem submissoes)")
    print()
    print("ESTRUTURA CRIADA:")
    print(f"  - 4 Atividades:")
    print(f"      * Lista 1: Loops e Condicionais (UUID: {ATV_001}) - Publicada")
    print(f"      * Lista 2: Vetores em C (UUID: {ATV_002}) - Publicada")
    print(f"      * Prova 1: Avaliacao Cronometrada (UUID: {ATV_003}) - Publicada / Prova")
    print(f"      * Lista 3: Divisao e Conquista (UUID: {ATV_004}) - Rascunho")
    print(f"  - 10 Funcoes C na Biblioteca Central com 35 casos de teste canônicos")
    print(f"  - 11 Associacoes N:N Atividade-Funcao com pesos e casos ocultos/visiveis")
    print(f"  - 15 Submissoes avaliadas/com erro simulando comportamento real dos alunos")
    print(f"  - 2 Entregas finais de atividade (RN14)")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
