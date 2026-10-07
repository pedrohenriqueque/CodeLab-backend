import unittest

from backend_v2.app.integrations.judge0 import Judge0TechnicalFailure
from backend_v2.app.services.evaluation_service import EvaluationService
from backend_v2.app.services.gerador_service import (
    UnsupportedCSignatureError,
    gerar_programa_teste,
)


class CGeneratorTests(unittest.TestCase):
    def test_generates_int_function_with_private_result_protocol(self):
        program = gerar_programa_teste(
            {
                "nome": "somar",
                "tipo_retorno": "int",
                "parametros": [{"nome": "a", "tipo": "int"}, {"nome": "b", "tipo": "int"}],
            },
            [{"entradas": [2, 3], "retorno_esperado": 5}],
            "int somar(int a, int b) { return a + b; }",
        )

        self.assertEqual(program.total_cases, 1)
        self.assertIn("int somar(int a, int b);", program.source_code)
        self.assertIn(program.result_marker, program.source_code)
        self.assertNotIn("expected=", program.source_code)
        self.assertIn('printf("\\n' + program.result_marker + 'CASE|0|%d|', program.source_code)
        self.assertIn('printf("%d", got);', program.source_code)
        self.assertIn('fflush(stdout);', program.source_code)

    def test_supports_booleans_and_vector_parameters_with_explicit_length(self):
        program = gerar_programa_teste(
            {
                "nome": "tem_positivo",
                "tipo_retorno": "bool",
                "parametros": [{"nome": "numeros", "tipo": "int[]"}, {"nome": "n", "tipo": "int"}],
            },
            [{"entradas": [[-1, 0, 2], 3], "retorno_esperado": True}],
            "bool tem_positivo(int numeros[], int n) { return n > 0 && numeros[n - 1] > 0; }",
        )

        self.assertIn("bool tem_positivo(int numeros[], int n);", program.source_code)
        self.assertIn("(int[]){-1, 0, 2}", program.source_code)
        self.assertIn("bool expected = true;", program.source_code)

    def test_supports_long_float_char_and_string_returns(self):
        examples = (
            (
                {"nome": "somarLongos", "tipo_retorno": "long", "parametros": [
                    {"nome": "a", "tipo": "long"}, {"nome": "b", "tipo": "long"},
                ]},
                [{"entradas": [5_000_000_000, 3], "retorno_esperado": 5_000_000_003}],
                "long somarLongos(long a, long b) { return a + b; }",
                "long somarLongos(long a, long b);",
                "long expected = 5000000003;",
            ),
            (
                {"nome": "dobrarFloat", "tipo_retorno": "float", "parametros": [
                    {"nome": "valor", "tipo": "float"},
                ]},
                [{"entradas": [1.5], "retorno_esperado": 3.0}],
                "float dobrarFloat(float valor) { return valor * 2.0f; }",
                "float dobrarFloat(float valor);",
                "fabs((double) got - (double) expected) <= 0.0001",
            ),
            (
                {"nome": "proximaLetra", "tipo_retorno": "char", "parametros": [
                    {"nome": "letra", "tipo": "char"},
                ]},
                [{"entradas": ["A"], "retorno_esperado": "B"}],
                "char proximaLetra(char letra) { return (char)(letra + 1); }",
                "char proximaLetra(char letra);",
                "char expected = 'B';",
            ),
            (
                {"nome": "ecoTexto", "tipo_retorno": "string", "parametros": [
                    {"nome": "texto", "tipo": "string"},
                ]},
                [{"entradas": ["CodeLab"], "retorno_esperado": "CodeLab"}],
                "const char *ecoTexto(const char *texto) { return texto; }",
                "const char * ecoTexto(const char * texto);",
                "strcmp(got, expected) == 0",
            ),
        )

        for function, cases, code, declaration, comparison in examples:
            with self.subTest(function=function["nome"]):
                program = gerar_programa_teste(function, cases, code)
                self.assertIn(declaration, program.source_code)
                self.assertIn(comparison, program.source_code)

    def test_rejects_unsupported_returns_and_invalid_case_shape(self):
        function = {"nome": "preencher", "tipo_retorno": "int[]", "parametros": []}
        with self.assertRaisesRegex(UnsupportedCSignatureError, "Retorno em vetor"):
            gerar_programa_teste(function, [], "")

        function = {"nome": "somar", "tipo_retorno": "int", "parametros": [{"nome": "a", "tipo": "int"}]}
        with self.assertRaisesRegex(UnsupportedCSignatureError, "Entradas incompatíveis"):
            gerar_programa_teste(function, [{"entradas": [], "retorno_esperado": 0}], "")

    def test_marker_changes_for_each_generated_program(self):
        function = {"nome": "identidade", "tipo_retorno": "int", "parametros": [{"nome": "a", "tipo": "int"}]}
        cases = [{"entradas": [1], "retorno_esperado": 1}]
        first = gerar_programa_teste(function, cases, "int identidade(int a) { return a; }")
        second = gerar_programa_teste(function, cases, "int identidade(int a) { return a; }")
        self.assertNotEqual(first.result_marker, second.result_marker)

    def test_evaluation_uses_fake_executor_and_does_not_return_source_or_cases(self):
        class FakeExecutor:
            async def executar_codigo(self, source_code):
                marker = source_code.split('__CODELAB_RESULT_')[1].split('__')[0]
                return {"status": {"id": 3}, "stdout": f"__CODELAB_RESULT_{marker}__CASE|0|1|4\n"}

        result = __import__("asyncio").run(EvaluationService(FakeExecutor()).avaliar(
            {"nome": "identidade", "tipo_retorno": "int", "parametros": [{"nome": "a", "tipo": "int"}]},
            [{"entradas": [4], "retorno_esperado": 4}],
            "int identidade(int a) { return a; }",
        ))
        self.assertEqual((result.passed_cases, result.total_cases, result.technical_failure), (1, 1, False))
        self.assertFalse(hasattr(result, "source_code"))
        self.assertEqual(result.case_returns[0].value, 4)

    def test_evaluation_keeps_judge0_outage_distinct_from_wrong_answer(self):
        class UnavailableExecutor:
            async def executar_codigo(self, source_code):
                raise Judge0TechnicalFailure("unavailable")

        result = __import__("asyncio").run(EvaluationService(UnavailableExecutor()).avaliar(
            {"nome": "identidade", "tipo_retorno": "int", "parametros": []},
            [{"entradas": [], "retorno_esperado": 4}],
            "int identidade(void) { return 4; }",
        ))
        self.assertTrue(result.technical_failure)
