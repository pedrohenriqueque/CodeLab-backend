import asyncio
import unittest

from backend_v2.app.integrations.judge0 import Judge0TechnicalFailure
from backend_v2.app.services.sandbox_service import executar_playground


class FakeExecutor:
    async def executar_codigo(self, codigo: str):
        return {
            "stdout": "Olá, CodeLab!\n",
            "stderr": "",
            "compile_output": "",
            "status": {"id": 3, "description": "Accepted"},
            "time": "0.003",
            "memory": 1024,
        }


class UnavailableExecutor:
    async def executar_codigo(self, codigo: str):
        raise Judge0TechnicalFailure("indisponível")


class SandboxServiceTests(unittest.TestCase):
    def test_returns_only_the_technical_execution_result(self):
        result = asyncio.run(executar_playground("int main(void) {}", FakeExecutor()))

        self.assertEqual(result["stdout"], "Olá, CodeLab!\n")
        self.assertEqual(result["status"], "Accepted")
        self.assertEqual(result["time"], "0.003")
        self.assertEqual(result["memory"], 1024)

    def test_preserves_technical_failure_for_the_route(self):
        with self.assertRaises(Judge0TechnicalFailure):
            asyncio.run(executar_playground("int main(void) {}", UnavailableExecutor()))
