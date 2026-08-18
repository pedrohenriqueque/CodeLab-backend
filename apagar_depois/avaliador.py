"""
Avaliador de submissões de código C.

Responsabilidades:
- Gerar programa de teste C a partir de uma função e seus casos
- Enviar para o Judge0
- Parsear o stdout no formato padronizado (CASE N PASS/FAIL)
- Calcular nota proporcional
- Retornar resultado estruturado para persistência
"""

import re
import logging
from gerador_judge0 import gerar_programa_teste
from judge0_client import Judge0Client

logger = logging.getLogger(__name__)


class AvaliadorExercicios:
    """Avaliador end-to-end de submissões de código C."""

    def __init__(self):
        self.judge0 = Judge0Client()

    def avaliar_submissao(self, funcao, casos_teste, codigo_aluno):
        """
        Avalia código do aluno contra uma função e seus casos de teste.

        Args:
            funcao: dict ou objeto Funcao com nome_funcao, parametros, retorno
            casos_teste: lista de dicts ou objetos CasoTeste
            codigo_aluno: string com código C do aluno

        Returns:
            dict com estrutura:
            {
                "nota": float,
                "pontos_maximo": int,
                "total_casos": int,
                "casos_passados": int,
                "casos": [
                    {
                        "numero": 1,
                        "status": "PASS" | "FAIL",
                        "expected": "120",   # só em FAIL
                        "got": "24",         # só em FAIL
                    },
                    ...
                ],
                "erro_compilacao": str | None,
                "erro_execucao": str | None,
                "tempo_ms": float,
                "memoria_kb": int,
                "codigo_gerado": str,
            }
        """
        pontos = funcao['pontos'] if isinstance(funcao, dict) else funcao.pontos

        try:
            # 1. Gerar código C completo
            logger.info("Gerando programa de teste...")
            codigo_completo, total_esperado = gerar_programa_teste(
                funcao, casos_teste, codigo_aluno
            )
            logger.info("Programa gerado: %d casos, %d bytes",
                        total_esperado, len(codigo_completo))

            # 2. Executar no Judge0
            logger.info("Enviando para Judge0...")
            resultado_judge0 = self.judge0.executar_codigo(codigo_completo)

            # 3. Extrair informações do Judge0
            status_id = resultado_judge0.get('status', {}).get('id', -1)
            stdout = resultado_judge0.get('stdout', '')
            stderr = resultado_judge0.get('stderr', '')
            compile_output = resultado_judge0.get('compile_output', '')

            tempo_ms = self._parse_tempo(resultado_judge0.get('time'))
            memoria_kb = self._parse_memoria(resultado_judge0.get('memory'))

            # 4. Verificar erros de compilação
            if status_id == 6:  # Compilation Error
                erro_amigavel = self._traduzir_erro_compilacao(compile_output)
                logger.warning("Erro de compilacao: %s", compile_output[:200])
                return {
                    'nota': 0.0,
                    'pontos_maximo': pontos,
                    'total_casos': total_esperado,
                    'casos_passados': 0,
                    'casos': [],
                    'erro_compilacao': erro_amigavel,
                    'erro_execucao': None,
                    'tempo_ms': tempo_ms,
                    'memoria_kb': memoria_kb,
                    'codigo_gerado': codigo_completo,
                }

            # 5. Verificar runtime error
            if status_id != 3:  # Não é Accepted
                logger.warning("Execucao com problema (status_id=%d): %s",
                               status_id, stderr[:200])
                # Ainda tentar parsear o stdout parcial
                casos = self._parsear_stdout(stdout)
                casos_passados = sum(1 for c in casos if c['status'] == 'PASS')

                return {
                    'nota': (casos_passados / total_esperado * pontos) if total_esperado > 0 else 0.0,
                    'pontos_maximo': pontos,
                    'total_casos': total_esperado,
                    'casos_passados': casos_passados,
                    'casos': casos,
                    'erro_compilacao': compile_output or None,
                    'erro_execucao': stderr or None,
                    'tempo_ms': tempo_ms,
                    'memoria_kb': memoria_kb,
                    'codigo_gerado': codigo_completo,
                }

            # 6. Parsear stdout (execução bem-sucedida)
            casos = self._parsear_stdout(stdout)
            casos_passados = sum(1 for c in casos if c['status'] == 'PASS')

            # Calcular nota proporcional
            nota = (casos_passados / total_esperado * pontos) if total_esperado > 0 else 0.0

            logger.info("Avaliacao concluida: %d/%d casos, nota=%.2f/%d",
                        casos_passados, total_esperado, nota, pontos)

            return {
                'nota': round(nota, 2),
                'pontos_maximo': pontos,
                'total_casos': total_esperado,
                'casos_passados': casos_passados,
                'casos': casos,
                'erro_compilacao': None,
                'erro_execucao': None,
                'tempo_ms': tempo_ms,
                'memoria_kb': memoria_kb,
                'codigo_gerado': codigo_completo,
            }

        except TimeoutError as e:
            logger.error("Timeout aguardando Judge0: %s", e)
            return self._resultado_erro(str(e), pontos, total_esperado if 'total_esperado' in dir() else 0)

        except Exception as e:
            logger.error("Erro inesperado na avaliacao: %s", e, exc_info=True)
            return self._resultado_erro(str(e), pontos, 0)

    def _parsear_stdout(self, stdout):
        """
        Parseia o stdout no formato padronizado.

        Formato esperado por linha:
            CASE 1 PASS
            CASE 2 FAIL expected=120 got=24
            RESULT 1/2

        Returns:
            lista de dicts com resultado de cada caso
        """
        casos = []

        if not stdout:
            return casos

        # Regex para CASE N PASS
        pass_pattern = re.compile(r'^CASE\s+(\d+)\s+PASS\s*$')
        # Regex para CASE N FAIL expected=X got=Y
        fail_pattern = re.compile(r'^CASE\s+(\d+)\s+FAIL\s+expected=(.+?)\s+got=(.+)\s*$')

        for line in stdout.strip().split('\n'):
            line = line.strip()

            match_pass = pass_pattern.match(line)
            if match_pass:
                casos.append({
                    'numero': int(match_pass.group(1)),
                    'status': 'PASS',
                })
                continue

            match_fail = fail_pattern.match(line)
            if match_fail:
                casos.append({
                    'numero': int(match_fail.group(1)),
                    'status': 'FAIL',
                    'expected': match_fail.group(2).strip(),
                    'got': match_fail.group(3).strip(),
                })
                continue

            # Ignorar linhas RESULT e outras
            if line.startswith('RESULT'):
                logger.debug("Linha RESULT: %s", line)

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
                "expected ';' before ')'",
                "[ERRO] Ponto-e-vírgula faltando: Faltou um ';' antes de fechar um parêntese ')'.",
            ),
            (
                "expected ';'",
                "[ERRO] Ponto-e-vírgula faltando: Faltou colocar um ';' no final de alguma instrução.",
            ),
            (
                "expected ')' before ';'",
                "[ERRO] Parêntese faltando: Faltou fechar um parêntese ')' em alguma expressão ou chamada de função.",
            ),
            (
                "expected ')'",
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
    def _parse_tempo(value):
        """Converte tempo do Judge0 (string em segundos) para milissegundos."""
        if value is None:
            return 0.0
        try:
            return round(float(value) * 1000, 2)
        except (ValueError, TypeError):
            return 0.0

    @staticmethod
    def _parse_memoria(value):
        """Converte memória do Judge0 para KB."""
        if value is None:
            return 0
        try:
            return int(value)
        except (ValueError, TypeError):
            return 0

    @staticmethod
    def _resultado_erro(mensagem, pontos, total_casos):
        """Retorna resultado padrão para erros."""
        return {
            'nota': 0.0,
            'pontos_maximo': pontos,
            'total_casos': total_casos,
            'casos_passados': 0,
            'casos': [],
            'erro_compilacao': None,
            'erro_execucao': mensagem,
            'tempo_ms': 0.0,
            'memoria_kb': 0,
            'codigo_gerado': None,
        }
