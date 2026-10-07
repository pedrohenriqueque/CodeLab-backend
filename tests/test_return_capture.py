"""Captura do return sem executar código submetido ou acessar Judge0 real."""
import unittest

from backend_v2.app.services.evaluation_service import EvaluationService
from backend_v2.app.services.gerador_service import MAX_CAPTURED_STRING_BYTES, gerar_programa_teste


class FakeExecutor:
    def __init__(self, records, *, status=3, noise="", terminated=True):
        self.records = records
        self.status = status
        self.noise = noise
        self.terminated = terminated
        self.calls = 0

    async def executar_codigo(self, source_code):
        self.calls += 1
        marker = "__CODELAB_RESULT_" + source_code.split("__CODELAB_RESULT_")[1].split("__")[0] + "__"
        output = self.noise + "\n" + "\n".join(f"{marker}CASE|{record}" for record in self.records)
        if self.terminated:
            output += "\n"
        return {"status": {"id": self.status}, "stdout": output}


class ReturnCaptureTests(unittest.IsolatedAsyncioTestCase):
    async def evaluate(self, tipo, executor, *, count=1):
        expected = {"int": 1, "long": 1, "float": 1.0, "double": 1.0, "bool": True, "char": "A", "string": "texto"}[tipo]
        return await EvaluationService(executor).avaliar(
            {"nome": "f", "tipo_retorno": tipo, "parametros": []},
            [{"entradas": [], "retorno_esperado": expected} for _ in range(count)],
            "/* código do aluno: execução simulada */",
        )

    async def test_captures_each_supported_return_type_including_falsy_values(self):
        for tipo, payload, expected in [
            ("int", "0", 0), ("long", "5000000003", 5_000_000_003),
            ("float", "1.25", 1.25), ("double", "1.23456789012345", 1.23456789012345),
            ("bool", "false", False), ("char", "x:0a", "\n"),
            ("string", "x:", ""), ("string", "null", None),
            ("string", "x:" + 'ação|"\n\\'.encode().hex(), 'ação|"\n\\'),
        ]:
            with self.subTest(tipo=tipo, payload=payload):
                executor = FakeExecutor([f"0|0|{payload}"])
                result = await self.evaluate(tipo, executor)
                self.assertFalse(result.technical_failure)
                self.assertEqual(result.case_results, (False,))
                self.assertEqual(result.case_returns[0].value, expected)
                self.assertEqual(result.case_returns[0].status, "DISPONIVEL")
                self.assertEqual(executor.calls, 1)

    async def test_prints_from_student_are_not_the_function_return(self):
        result = await self.evaluate("int", FakeExecutor(
            ["0|0|2"], noise='999\n__CODELAB_RESULT_wrong__CASE|0|1|999\nmensagem do aluno',
        ))
        self.assertEqual(result.case_returns[0].value, 2)
        self.assertEqual(result.passed_cases, 0)

    async def test_keeps_completed_cases_when_a_later_case_crashes_or_times_out(self):
        for status in [5, 7, 8, 11, 12]:
            with self.subTest(status=status):
                result = await self.evaluate("int", FakeExecutor(["0|1|1"], status=status), count=3)
                self.assertEqual(result.case_results, (True, False, False))
                self.assertEqual(result.passed_cases, 1)
                self.assertEqual([item.status for item in result.case_returns], ["DISPONIVEL", "ERRO_EXECUCAO", "NAO_EXECUTADO"])
                self.assertFalse(result.technical_failure)

    async def test_does_not_capture_an_unterminated_protocol_record(self):
        result = await self.evaluate("int", FakeExecutor(["0|1|123"], status=7, terminated=False))
        self.assertEqual(result.case_returns[0].status, "ERRO_EXECUCAO")
        self.assertEqual(result.passed_cases, 0)

    async def test_rejects_malformed_wrong_type_duplicate_and_out_of_order_records(self):
        for records in [["0|1|true"], ["0|1|NaN"], ["1|1|1"], ["0|1|1", "0|1|1"], ["0|2|1"], ["0|1"]]:
            with self.subTest(records=records):
                result = await self.evaluate("int", FakeExecutor(records))
                self.assertTrue(result.technical_failure)
                self.assertEqual(result.case_returns, ())

    async def test_rejects_invalid_string_encoding_or_oversized_wire_payload(self):
        for payload in ["x:zz", "x:f", "x:" + "aa" * (MAX_CAPTURED_STRING_BYTES + 1)]:
            result = await self.evaluate("string", FakeExecutor([f"0|1|{payload}"]))
            self.assertTrue(result.technical_failure)

    async def test_capture_limit_does_not_change_case_approval(self):
        result = await self.evaluate("string", FakeExecutor(["0|1|TRUNCATED"]))
        self.assertEqual(result.case_returns[0].status, "LIMITE_EXCEDIDO")
        self.assertEqual(result.passed_cases, 1)
        self.assertFalse(result.technical_failure)

    async def test_invalid_utf8_does_not_fabricate_a_replacement_character(self):
        result = await self.evaluate("string", FakeExecutor(["0|0|x:ff"]))
        self.assertEqual(result.case_returns[0].status, "NAO_INFORMADO")
        self.assertIsNone(result.case_returns[0].value)
        self.assertFalse(result.technical_failure)

    async def test_non_finite_numbers_are_represented_without_invalid_json(self):
        for value in ['"NaN"', '"Infinity"', '"-Infinity"']:
            result = await self.evaluate("double", FakeExecutor([f"0|0|{value}"]))
            self.assertEqual(result.case_returns[0].value, value.strip('"'))
            self.assertEqual(result.case_returns[0].status, "DISPONIVEL")

    async def test_compilation_error_and_judge_internal_error_do_not_have_return(self):
        result = await self.evaluate("int", FakeExecutor([], status=6))
        self.assertTrue(result.compilation_error)
        self.assertEqual(result.case_returns, ())
        result = await self.evaluate("int", FakeExecutor([], status=13))
        self.assertTrue(result.technical_failure)
        self.assertEqual(result.case_returns, ())

    def test_generated_c_calls_function_once_per_case_and_emits_return_by_type(self):
        for tipo, emitter in [
            ("int", 'printf("%d", got);'), ("long", 'printf("%ld", got);'),
            ("float", 'printf("%.9g", (double) got);'), ("double", 'printf("%.17g", (double) got);'),
            ("bool", 'fputs(got ? "true" : "false", stdout);'),
            ("char", 'printf("x:%02x", (unsigned int)(unsigned char) got);'),
            ("string", 'fputs("x:", stdout);'),
        ]:
            with self.subTest(tipo=tipo):
                expected = {"int": 1, "long": 1, "float": 1.0, "double": 1.0, "bool": True, "char": "A", "string": "texto"}[tipo]
                source = gerar_programa_teste(
                    {"nome": "f", "tipo_retorno": tipo, "parametros": []},
                    [{"entradas": [], "retorno_esperado": expected}], "/* código */",
                ).source_code
                self.assertEqual(source.count("got = f();"), 1)
                self.assertIn(emitter, source)
                self.assertIn('fflush(stdout);', source)

    def test_char_control_values_have_valid_c_literals(self):
        source = gerar_programa_teste(
            {"nome": "f", "tipo_retorno": "char", "parametros": []},
            [{"entradas": [], "retorno_esperado": "\n"}], "char f(void) { return '\\n'; }",
        ).source_code
        self.assertIn("char expected = '\\x0a';", source)
