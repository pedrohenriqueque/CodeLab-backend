"""
Avaliador de submissões de código C (assíncrono).

Orquestra: geração de código → Judge0 → parsing → cálculo de nota.
"""

import re
import logging

from app.services.judge0_client import judge0_client
from app.services.gerador_service import gerar_programa_teste

logger = logging.getLogger(__name__)


class AvaliadorService:
    """Avaliador assíncrono end-to-end de submissões de código C."""

    async def avaliar(
        self,
        funcao: dict,
        casos_teste: list[dict],
        codigo_aluno: str,
    ) -> dict:
        """
        Avalia código do aluno contra uma função e seus casos de teste.

        Args:
            funcao: dict com nome_funcao, parametros, retorno, pontos
            casos_teste: lista de dicts com inputs, output_esperado
            codigo_aluno: código C do aluno

        Returns:
            dict estruturado com nota, casos, erros, etc.
        """
        pontos = funcao.get("pontos", 10)
        total_esperado = 0

        try:
            # 1. Gerar código C completo
            logger.info("Gerando programa de teste...")
            codigo_completo, total_esperado = gerar_programa_teste(
                funcao, casos_teste, codigo_aluno
            )
            logger.info("Programa gerado: %d casos, %d bytes",
                        total_esperado, len(codigo_completo))

            # 2. Executar no Judge0 (async)
            logger.info("Enviando para Judge0...")
            resultado_judge0 = await judge0_client.executar_codigo(codigo_completo)

            # 3. Extrair informações
            status_id = resultado_judge0.get("status", {}).get("id", -1)
            stdout = resultado_judge0.get("stdout", "")
            stderr = resultado_judge0.get("stderr", "")
            compile_output = resultado_judge0.get("compile_output", "")

            tempo_ms = self._parse_tempo(resultado_judge0.get("time"))
            memoria_kb = self._parse_memoria(resultado_judge0.get("memory"))

            # 4. Erro de compilação
            if status_id == 6:
                erro_amigavel = self._traduzir_erro_compilacao(compile_output)
                logger.warning("Erro de compilacao: %s", compile_output[:200])
                return self._build_result(
                    nota=0.0, pontos=pontos, total=total_esperado, passados=0,
                    casos=[], erro_compilacao=erro_amigavel,
                    tempo_ms=tempo_ms, memoria_kb=memoria_kb,
                    codigo_gerado=codigo_completo,
                )

            # 5. Parsear stdout
            casos = self._parsear_stdout(stdout)
            casos_passados = sum(1 for c in casos if c["status"] == "PASS")

            # 6. Calcular nota proporcional
            nota = (casos_passados / total_esperado * pontos) if total_esperado > 0 else 0.0

            logger.info("Avaliacao concluida: %d/%d casos, nota=%.2f/%s",
                        casos_passados, total_esperado, nota, pontos)

            return self._build_result(
                nota=round(nota, 2), pontos=pontos, total=total_esperado,
                passados=casos_passados, casos=casos,
                erro_compilacao=compile_output if status_id != 3 else None,
                erro_execucao=stderr if status_id != 3 else None,
                tempo_ms=tempo_ms, memoria_kb=memoria_kb,
                codigo_gerado=codigo_completo,
            )

        except TimeoutError as e:
            logger.error("Timeout aguardando Judge0: %s", e)
            return self._build_result(
                nota=0.0, pontos=pontos, total=total_esperado,
                passados=0, casos=[], erro_execucao=str(e),
            )

        except Exception as e:
            logger.error("Erro inesperado na avaliacao: %s", e, exc_info=True)
            return self._build_result(
                nota=0.0, pontos=pontos, total=total_esperado,
                passados=0, casos=[], erro_execucao=str(e),
            )

    def _parsear_stdout(self, stdout: str) -> list[dict]:
        """Parseia stdout no formato CASE N PASS / CASE N FAIL."""
        casos = []
        if not stdout:
            return casos

        pass_re = re.compile(r"^CASE\s+(\d+)\s+PASS\s*$")
        fail_re = re.compile(r"^CASE\s+(\d+)\s+FAIL\s+expected=(.+?)\s+got=(.+)\s*$")

        for line in stdout.strip().split("\n"):
            line = line.strip()

            m = pass_re.match(line)
            if m:
                casos.append({"numero": int(m.group(1)), "status": "PASS"})
                continue

            m = fail_re.match(line)
            if m:
                casos.append({
                    "numero": int(m.group(1)),
                    "status": "FAIL",
                    "expected": m.group(2).strip(),
                    "got": m.group(3).strip(),
                })

        return casos

    def _traduzir_erro_compilacao(self, erro_bruto: str) -> str:
        """Traduz mensagens comuns de erro do GCC para pt-BR.
        
        Coleta TODAS as dicas que se aplicam ao erro (pode haver mais de um problema)
        e retorna junto com o log original do compilador para referência.
        """
        if not erro_bruto:
            return erro_bruto

        # Regras de tradução: (texto_no_erro, dica_amigavel)
        # A ordem importa: erros mais específicos vêm primeiro.
        REGRAS = [
            (
                "expected declaration or statement at end of input",
                "[ERRO] Chave faltando: Você esqueceu de fechar uma chave '}' no final do seu código.",
            ),
            (
                "expected ';' before '}'",
                "[ERRO] Ponto-e-vírgula faltando: Faltou um ';' no final de alguma instrução antes de fechar a chave '}'.",
            ),
            (
                "expected \u2018;\u2019 before \u2018}\u2019",
                "[ERRO] Ponto-e-vírgula faltando: Faltou um ';' no final de alguma instrução antes de fechar a chave '}'.",
            ),
            (
                "expected ';' before ')'",
                "[ERRO] Ponto-e-vírgula faltando: Faltou um ';' antes de fechar um parêntese ')'.",
            ),
            (
                "expected \u2018;\u2019 before \u2018)\u2019",
                "[ERRO] Ponto-e-vírgula faltando: Faltou um ';' antes de fechar um parêntese ')'.",
            ),
            (
                "expected ';'",
                "[ERRO] Ponto-e-vírgula faltando: Faltou colocar um ';' no final de alguma instrução.",
            ),
            (
                "expected \u2018;\u2019",
                "[ERRO] Ponto-e-vírgula faltando: Faltou colocar um ';' no final de alguma instrução.",
            ),
            (
                "expected ')' before ';'",
                "[ERRO] Parêntese faltando: Faltou fechar um parêntese ')' em alguma expressão ou chamada de função.",
            ),
            (
                "expected \u2018)\u2019 before \u2018;\u2019",
                "[ERRO] Parêntese faltando: Faltou fechar um parêntese ')' em alguma expressão ou chamada de função.",
            ),
            (
                "expected ')'",
                "[ERRO] Parêntese faltando: Faltou fechar um parêntese ')' em alguma expressão.",
            ),
            (
                "expected \u2018)\u2019",
                "[ERRO] Parêntese faltando: Faltou fechar um parêntese ')' em alguma expressão.",
            ),
            (
                "missing terminating '\"' character",
                "[ERRO] Aspas não fechadas: Você abriu uma string com aspas duplas '\"' mas esqueceu de fechar.",
            ),
            (
                "missing terminating \"'\" character",
                "[ERRO] Aspas não fechadas: Você abriu um caractere com aspas simples \"'\" mas esqueceu de fechar.",
            ),
            (
                "undeclared (first use in this function)",
                "[ERRO] Variável não declarada: Você usou uma variável que não foi criada. Verifique o nome ou adicione a declaração (ex: int x;).",
            ),
            (
                "expected identifier or '(' before",
                "[ERRO] Erro de sintaxe: Erro de digitação próximo a um '(' ou ao nome de uma função/variável.",
            ),
            (
                "expected identifier or \u2018(\u2019 before",
                "[ERRO] Erro de sintaxe: Erro de digitação próximo a um '(' ou ao nome de uma função/variável.",
            ),
            (
                "too few arguments to function",
                "[ERRO] Argumentos faltando: Você chamou uma função passando menos argumentos do que ela precisa.",
            ),
            (
                "too many arguments to function",
                "[ERRO] Argumentos em excesso: Você passou mais argumentos do que a função espera.",
            ),
            (
                "return type does not match",
                "[ERRO] Tipo de retorno incorreto: O valor que você está retornando não é do tipo que a função declara.",
            ),
            (
                "incompatible types",
                "[ERRO] Tipos incompatíveis: Você tentou atribuir ou comparar valores de tipos diferentes (ex: int com float sem conversão).",
            ),
        ]

        dicas = []
        for padrao, mensagem in REGRAS:
            if padrao in erro_bruto:
                # Evitar dicas duplicadas para padrões sobrepostos
                if mensagem not in dicas:
                    dicas.append(mensagem)

        if dicas:
            cabecalho = "\n".join(dicas)
            return f"{cabecalho}\n\n[Erro Original do Compilador]:\n{erro_bruto}"
        return erro_bruto

    @staticmethod
    def _build_result(*, nota, pontos, total, passados, casos,
                      erro_compilacao=None, erro_execucao=None,
                      tempo_ms=0.0, memoria_kb=0, codigo_gerado=None):
        return {
            "nota": nota,
            "pontos_maximo": pontos,
            "total_casos": total,
            "casos_passados": passados,
            "casos": casos,
            "erro_compilacao": erro_compilacao,
            "erro_execucao": erro_execucao,
            "tempo_ms": tempo_ms,
            "memoria_kb": memoria_kb,
            "codigo_gerado": codigo_gerado,
        }

    @staticmethod
    def _parse_tempo(value) -> float:
        if value is None:
            return 0.0
        try:
            return round(float(value) * 1000, 2)
        except (ValueError, TypeError):
            return 0.0

    @staticmethod
    def _parse_memoria(value) -> int:
        if value is None:
            return 0
        try:
            return int(value)
        except (ValueError, TypeError):
            return 0


# Singleton
avaliador_service = AvaliadorService()
